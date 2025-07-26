//! BitVMX-based Option Registration System
//! 
//! This module implements option registration using BitVMX protocol
//! to ensure verifiable computation and on-chain anchoring.

use anyhow::Result;
use bitcoin::{Transaction, TxOut, Script, Network};
use bitcoin::blockdata::opcodes::all::OP_RETURN;
use bitcoin::blockdata::script::Builder;
use serde::{Deserialize, Serialize};
use sha2::{Sha256, Digest};
use oracle_vm_common::types::OptionType;
use crate::bitcoin_anchoring_v2::{CreateOptionAnchorData, TxType};

/// BitVMX Option Registration Input
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct BitVMXOptionInput {
    pub option_type: OptionType,
    pub strike_price: u64,      // USD cents
    pub quantity: u64,          // satoshis
    pub expiry_timestamp: u64,  // Unix timestamp
    pub issuer: String,
    pub premium: u64,           // satoshis
    pub oracle_sources: Vec<String>,
}

/// BitVMX Option Registration Output
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct BitVMXOptionOutput {
    pub option_id: [u8; 6],
    pub registration_hash: [u8; 32],
    pub btcfi_data: CreateOptionAnchorData,
    pub validation_result: bool,
}

/// BitVMX Option Registry
pub struct BitVMXOptionRegistry {
    network: Network,
    bitvmx_executor: BitVMXExecutor,
}

/// BitVMX Executor for option registration
pub struct BitVMXExecutor {
    cpu_path: String,
    program_path: String,
}

impl BitVMXExecutor {
    pub fn new() -> Self {
        Self {
            cpu_path: "bitvmx_protocol/BitVMX-CPU".to_string(),
            program_path: "bitvmx_protocol/programs/option_registration.elf".to_string(),
        }
    }

    /// Execute option registration in BitVMX
    pub async fn execute_registration(&self, input: &BitVMXOptionInput) -> Result<BitVMXRegistrationProof> {
        // Step 1: Prepare input for RISC-V program
        let input_bytes = self.encode_input(input)?;
        
        // Step 2: Execute in BitVMX-CPU
        let execution_result = self.run_bitvmx_cpu(&input_bytes).await?;
        
        // Step 3: Generate Hash Chain proof
        let hash_chain = self.generate_hash_chain(&execution_result)?;
        
        // Step 4: Create registration proof
        let proof = BitVMXRegistrationProof {
            input_hash: self.hash_input(input),
            execution_trace: execution_result.trace,
            hash_chain,
            final_state: execution_result.final_state,
            output: execution_result.output,
        };
        
        Ok(proof)
    }

    /// Encode option input for RISC-V program
    fn encode_input(&self, input: &BitVMXOptionInput) -> Result<Vec<u8>> {
        let mut encoded = Vec::new();
        
        // Encode according to BitVMX input format
        encoded.extend_from_slice(&(input.option_type as u32).to_le_bytes());
        encoded.extend_from_slice(&input.strike_price.to_le_bytes());
        encoded.extend_from_slice(&input.quantity.to_le_bytes());
        encoded.extend_from_slice(&input.expiry_timestamp.to_le_bytes());
        encoded.extend_from_slice(&input.premium.to_le_bytes());
        
        // Add issuer hash (32 bytes)
        let mut hasher = Sha256::new();
        hasher.update(input.issuer.as_bytes());
        encoded.extend_from_slice(&hasher.finalize());
        
        // Add oracle sources count and hashes
        encoded.extend_from_slice(&(input.oracle_sources.len() as u32).to_le_bytes());
        for oracle in &input.oracle_sources {
            let mut hasher = Sha256::new();
            hasher.update(oracle.as_bytes());
            encoded.extend_from_slice(&hasher.finalize()[0..8]); // 8 bytes per oracle
        }
        
        Ok(encoded)
    }

    /// Run BitVMX-CPU with the encoded input
    async fn run_bitvmx_cpu(&self, input: &[u8]) -> Result<BitVMXExecutionResult> {
        use std::process::Command;
        use std::io::Write;
        use std::fs;
        
        // Write input to temporary file
        let input_file = format!("{}/temp_input_{}.bin", self.cpu_path, uuid::Uuid::new_v4());
        fs::write(&input_file, input)?;
        
        // Execute BitVMX-CPU emulator
        let output = Command::new("cargo")
            .current_dir(&self.cpu_path)
            .args(&[
                "run",
                "--release",
                "-p",
                "emulator",
                "execute",
                "--elf",
                "../programs/option_registration.elf",
                "--input-file",
                &input_file,
                "--trace",
                "--witness",
            ])
            .output()?;
        
        if !output.status.success() {
            return Err(anyhow::anyhow!("BitVMX execution failed: {}", 
                String::from_utf8_lossy(&output.stderr)));
        }
        
        // Parse execution result
        let stdout = String::from_utf8(output.stdout)?;
        let result = self.parse_execution_output(&stdout)?;
        
        // Clean up
        fs::remove_file(&input_file).ok();
        
        Ok(result)
    }

    /// Generate Hash Chain from execution trace
    fn generate_hash_chain(&self, result: &BitVMXExecutionResult) -> Result<HashChain> {
        let mut chain = HashChain {
            steps: Vec::new(),
            final_hash: [0u8; 32],
        };
        
        let mut prev_hash = [0u8; 32];
        let checkpoint_interval = result.trace.len() / 10; // 10 checkpoints
        
        for (i, state) in result.trace.iter().enumerate() {
            let mut hasher = Sha256::new();
            hasher.update(&prev_hash);
            hasher.update(state);
            let hash = hasher.finalize();
            
            if i % checkpoint_interval == 0 || i == result.trace.len() - 1 {
                chain.steps.push(HashChainStep {
                    step_number: i as u32,
                    state_hash: hash.into(),
                });
            }
            
            prev_hash = hash.into();
        }
        
        chain.final_hash = prev_hash;
        Ok(chain)
    }

    /// Parse BitVMX execution output
    fn parse_execution_output(&self, output: &str) -> Result<BitVMXExecutionResult> {
        // Parse the structured output from BitVMX-CPU
        let lines: Vec<&str> = output.lines().collect();
        let mut trace = Vec::new();
        let mut final_state = Vec::new();
        let mut output_data = Vec::new();
        
        let mut section = "";
        for line in lines {
            if line.starts_with("=== TRACE ===") {
                section = "trace";
            } else if line.starts_with("=== FINAL STATE ===") {
                section = "state";
            } else if line.starts_with("=== OUTPUT ===") {
                section = "output";
            } else if line.starts_with("===") {
                section = "";
            } else if !line.trim().is_empty() {
                match section {
                    "trace" => {
                        if let Ok(bytes) = hex::decode(line.trim()) {
                            trace.push(bytes);
                        }
                    }
                    "state" => {
                        if let Ok(bytes) = hex::decode(line.trim()) {
                            final_state.extend(bytes);
                        }
                    }
                    "output" => {
                        if let Ok(bytes) = hex::decode(line.trim()) {
                            output_data.extend(bytes);
                        }
                    }
                    _ => {}
                }
            }
        }
        
        Ok(BitVMXExecutionResult {
            trace,
            final_state,
            output: output_data,
        })
    }

    /// Hash the input for commitment
    fn hash_input(&self, input: &BitVMXOptionInput) -> [u8; 32] {
        let mut hasher = Sha256::new();
        hasher.update(&serde_json::to_vec(input).unwrap());
        hasher.finalize().into()
    }
}

/// BitVMX execution result
#[derive(Debug, Clone)]
struct BitVMXExecutionResult {
    trace: Vec<Vec<u8>>,
    final_state: Vec<u8>,
    output: Vec<u8>,
}

/// Hash Chain for BitVMX proof
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct HashChain {
    pub steps: Vec<HashChainStep>,
    pub final_hash: [u8; 32],
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct HashChainStep {
    pub step_number: u32,
    pub state_hash: [u8; 32],
}

/// BitVMX Registration Proof
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct BitVMXRegistrationProof {
    pub input_hash: [u8; 32],
    pub execution_trace: Vec<Vec<u8>>,
    pub hash_chain: HashChain,
    pub final_state: Vec<u8>,
    pub output: Vec<u8>,
}

impl BitVMXOptionRegistry {
    pub fn new(network: Network) -> Self {
        Self {
            network,
            bitvmx_executor: BitVMXExecutor::new(),
        }
    }

    /// Register option using BitVMX protocol
    pub async fn register_option(&self, input: BitVMXOptionInput) -> Result<(String, BitVMXRegistrationProof)> {
        // Step 1: Execute registration in BitVMX
        let proof = self.bitvmx_executor.execute_registration(&input).await?;
        
        // Step 2: Create BTCFi anchor data from output
        let anchor_data = self.create_anchor_data(&input, &proof)?;
        
        // Step 3: Create pre-signed transaction graph
        let tx_graph = self.create_transaction_graph(&anchor_data, &proof)?;
        
        // Step 4: Broadcast registration transaction
        let txid = self.broadcast_registration(&tx_graph).await?;
        
        Ok((txid, proof))
    }

    /// Create BTCFi anchor data from BitVMX output
    fn create_anchor_data(&self, input: &BitVMXOptionInput, proof: &BitVMXRegistrationProof) -> Result<CreateOptionAnchorData> {
        // Extract option ID from proof output
        let mut option_id = [0u8; 6];
        option_id.copy_from_slice(&proof.output[0..6]);
        
        // Convert to BTCFi format
        let anchor_data = CreateOptionAnchorData {
            tx_type: TxType::Create,
            option_id,
            option_type: match input.option_type {
                OptionType::Call => 0,
                OptionType::Put => 1,
            },
            strike_sats: (input.strike_price as u64 * 100_000_000) / 100,
            expiry: input.expiry_timestamp,
            unit: (input.quantity as f32) / 100_000_000.0,
        };
        
        Ok(anchor_data)
    }

    /// Create pre-signed transaction graph
    fn create_transaction_graph(&self, anchor_data: &CreateOptionAnchorData, proof: &BitVMXRegistrationProof) -> Result<BitVMXTransactionGraph> {
        let mut graph = BitVMXTransactionGraph::new();
        
        // Create registration transaction with OP_RETURN
        let registration_tx = self.create_registration_transaction(anchor_data, proof)?;
        graph.add_transaction("registration", registration_tx);
        
        // Create challenge transactions (pre-signed)
        let challenge_txs = self.create_challenge_transactions(proof)?;
        for (i, tx) in challenge_txs.iter().enumerate() {
            graph.add_transaction(&format!("challenge_{}", i), tx.clone());
        }
        
        Ok(graph)
    }

    /// Create registration transaction with BitVMX proof and BTCFi data
    fn create_registration_transaction(&self, anchor_data: &CreateOptionAnchorData, proof: &BitVMXRegistrationProof) -> Result<Transaction> {
        use bitcoin::Transaction;
        
        // Create OP_RETURN output with both BitVMX hash and BTCFi data
        let mut op_return_data = Vec::new();
        
        // BitVMX final hash (32 bytes)
        op_return_data.extend_from_slice(&proof.hash_chain.final_hash);
        
        // BTCFi option data (28 bytes)
        op_return_data.extend_from_slice(&anchor_data.encode());
        
        // Total: 60 bytes (within 80 byte OP_RETURN limit)
        
        let op_return_script = Builder::new()
            .push_opcode(OP_RETURN)
            .push_slice(&op_return_data)
            .into_script();
        
        // Create transaction (funding will be added later)
        let tx = Transaction {
            version: 2,
            lock_time: bitcoin::PackedLockTime::ZERO,
            input: vec![], // Will be filled by wallet
            output: vec![
                TxOut {
                    value: 0,
                    script_pubkey: op_return_script,
                },
            ],
        };
        
        Ok(tx)
    }

    /// Create challenge transactions for dispute resolution
    fn create_challenge_transactions(&self, proof: &BitVMXRegistrationProof) -> Result<Vec<Transaction>> {
        let mut transactions = Vec::new();
        
        // Create N-ary search challenge transactions
        let search_depth = (proof.execution_trace.len() as f64).log2().ceil() as usize;
        
        for level in 0..search_depth {
            let challenge_tx = self.create_challenge_tx_for_level(proof, level)?;
            transactions.push(challenge_tx);
        }
        
        Ok(transactions)
    }

    /// Create a challenge transaction for a specific search level
    fn create_challenge_tx_for_level(&self, proof: &BitVMXRegistrationProof, level: usize) -> Result<Transaction> {
        // This creates pre-signed transactions for the N-ary search protocol
        // Each transaction commits to a specific range of the execution trace
        
        let range_size = proof.execution_trace.len() / (4_usize.pow(level as u32));
        let checkpoint_hash = &proof.hash_chain.steps[level].state_hash;
        
        let challenge_script = Builder::new()
            .push_opcode(OP_RETURN)
            .push_slice(b"CHALLENGE")
            .push_int(level as i64)
            .push_slice(checkpoint_hash)
            .into_script();
        
        let tx = Transaction {
            version: 2,
            lock_time: bitcoin::PackedLockTime::ZERO,
            input: vec![], // Will reference funding UTXO
            output: vec![
                TxOut {
                    value: 0,
                    script_pubkey: challenge_script,
                },
            ],
        };
        
        Ok(tx)
    }

    /// Broadcast the registration transaction
    async fn broadcast_registration(&self, graph: &BitVMXTransactionGraph) -> Result<String> {
        // Get the registration transaction
        let reg_tx = graph.get_transaction("registration")
            .ok_or_else(|| anyhow::anyhow!("Registration transaction not found"))?;
        
        // In production, this would:
        // 1. Fund the transaction
        // 2. Sign it
        // 3. Broadcast to Bitcoin network
        
        // For now, we'll use bitcoin-cli
        let hex = bitcoin::consensus::encode::serialize_hex(reg_tx);
        
        let output = std::process::Command::new("bitcoin-cli")
            .args(&[
                "-regtest",
                "-rpcuser=test", 
                "-rpcpassword=test",
                "sendrawtransaction",
                &hex,
            ])
            .output()?;
        
        if !output.status.success() {
            return Err(anyhow::anyhow!("Failed to broadcast: {}", 
                String::from_utf8_lossy(&output.stderr)));
        }
        
        let txid = String::from_utf8(output.stdout)?.trim().to_string();
        Ok(txid)
    }
}

/// BitVMX Transaction Graph for pre-signed transactions
#[derive(Debug, Clone)]
pub struct BitVMXTransactionGraph {
    transactions: std::collections::HashMap<String, Transaction>,
}

impl BitVMXTransactionGraph {
    pub fn new() -> Self {
        Self {
            transactions: std::collections::HashMap::new(),
        }
    }
    
    pub fn add_transaction(&mut self, name: &str, tx: Transaction) {
        self.transactions.insert(name.to_string(), tx);
    }
    
    pub fn get_transaction(&self, name: &str) -> Option<&Transaction> {
        self.transactions.get(name)
    }
}

/// Integration with SimpleContractManager
impl crate::simple_contract::SimpleContractManager {
    /// Create option with BitVMX registration
    pub async fn create_option_with_bitvmx(
        &mut self,
        option_type: OptionType,
        strike_price: u64,
        quantity: u64,
        premium: u64,
        expiry_timestamp: u64,
        user_id: String,
    ) -> Result<(String, String, BitVMXRegistrationProof)> {
        // Create BitVMX input
        let bitvmx_input = BitVMXOptionInput {
            option_type,
            strike_price,
            quantity,
            expiry_timestamp,
            issuer: user_id.clone(),
            premium,
            oracle_sources: vec![
                "binance".to_string(),
                "coinbase".to_string(),
                "kraken".to_string(),
            ],
        };
        
        // Register with BitVMX
        let registry = BitVMXOptionRegistry::new(bitcoin::Network::Regtest);
        let (txid, proof) = registry.register_option(bitvmx_input).await?;
        
        // Extract option ID from proof
        let mut option_id_bytes = [0u8; 6];
        option_id_bytes.copy_from_slice(&proof.output[0..6]);
        let option_id = hex::encode(option_id_bytes);
        
        // Create option in local state
        let expiry_height = self.estimate_block_height(expiry_timestamp);
        self.create_option(
            option_id.clone(),
            option_type,
            strike_price,
            quantity,
            premium,
            expiry_height,
            user_id,
        )?;
        
        Ok((option_id, txid, proof))
    }
    
    fn estimate_block_height(&self, timestamp: u64) -> u32 {
        // Estimate block height from timestamp
        // Assuming 10 minutes per block
        let current_time = chrono::Utc::now().timestamp() as u64;
        let blocks_in_future = (timestamp - current_time) / 600;
        800_000 + blocks_in_future as u32 // Approximate current height
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    
    #[test]
    fn test_bitvmx_input_encoding() {
        let input = BitVMXOptionInput {
            option_type: OptionType::Call,
            strike_price: 50000_00, // $50,000
            quantity: 10_000_000,   // 0.1 BTC
            expiry_timestamp: 1735689600,
            issuer: "user123".to_string(),
            premium: 100_000,       // 0.001 BTC
            oracle_sources: vec!["binance".to_string()],
        };
        
        let executor = BitVMXExecutor::new();
        let encoded = executor.encode_input(&input).unwrap();
        
        // Verify encoding
        assert!(encoded.len() > 0);
        assert_eq!(&encoded[0..4], &0u32.to_le_bytes()); // Call option = 0
    }
}