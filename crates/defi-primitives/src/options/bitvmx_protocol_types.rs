use serde::{Deserialize, Serialize};
use std::collections::HashMap;

/// Official BitVMX Protocol Setup Properties (matches Python DTO)
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct BitVMXProtocolSetupProperties {
    pub setup_uuid: String,
    pub funding_amount_of_satoshis: u64,
    pub step_fees_satoshis: u64,
    pub funding_tx_id: String,
    pub funding_index: u32,
    pub prover_destination_address: String,
    pub verifier_destination_address: String,
    pub prover_signature_public_key: String,
    pub verifier_signature_public_key: String,
    pub seed_unspendable_public_key: String,
    pub prover_destroyed_public_key: String,
    pub verifier_destroyed_public_key: String,
    pub bitvmx_protocol_properties: BitVMXProtocolProperties,
    pub bitvmx_transactions: Option<BitVMXTransactions>,
    pub execution_trace: Option<ExecutionTrace>,
}

/// BitVMX Protocol Properties (core parameters)
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct BitVMXProtocolProperties {
    pub max_amount_of_steps: u64,
    pub amount_of_input_words: u32,
    pub amount_of_bits_wrong_step_search: u32,
    pub amount_of_bits_per_digit_checksum: u32,
    pub amount_of_nibbles_hash_with_checksum: u32,
}

/// BitVMX Transactions (all protocol transactions as hex strings)
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct BitVMXTransactions {
    // Core protocol transactions
    pub funding_tx: String,                           // Hex-encoded Bitcoin transaction
    pub hash_result_tx: String,                       // Hash result revelation
    pub trigger_protocol_tx: String,                  // Protocol initiation
    
    // Search phase transactions
    pub search_hash_tx_list: Vec<String>,             // Hash search iterations
    pub search_choice_tx_list: Vec<String>,           // Choice search iterations
    
    // Execution phase transactions  
    pub trace_tx: String,                             // Execution trace
    pub trigger_execution_challenge_tx: String,       // Challenge trigger
    pub execution_challenge_tx: String,               // Actual challenge
    
    // Challenge transactions
    pub trigger_equivocation_tx: String,              // Equivocation trigger
    pub trigger_wrong_hash_challenge_tx: String,      // Wrong hash challenge
    pub trigger_wrong_program_counter_challenge_tx: String, // Wrong PC challenge
    
    // Read operations
    pub read_search_hash_tx_list: Vec<String>,        // Read search hashes
    pub read_search_equivocation_tx_list: Vec<String>, // Read equivocations
    pub read_search_choice_tx_list: Vec<String>,      // Read search choices
    pub read_trace_tx: String,                        // Read trace
    pub trigger_read_challenge_tx: String,            // Read challenge trigger
}

/// Execution Trace Data (matches Python ExecutionTraceDTO)
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ExecutionTrace {
    // Memory reads
    pub read_1_address: String,      // First read memory address (hex)
    pub read_1_value: String,        // First read value (hex)
    pub read_1_last_step: String,    // Last modification step (hex)
    
    pub read_2_address: String,      // Second read memory address (hex)
    pub read_2_value: String,        // Second read value (hex)
    pub read_2_last_step: String,    // Last modification step (hex)
    
    // Program counter and instruction
    pub opcode: String,              // RISC-V instruction opcode (hex)
    pub read_pc_address: String,     // Program counter address (hex)
    pub read_micro: String,          // Micro-operation data (hex)
    
    // Memory writes  
    pub write_address: String,       // Write memory address (hex)
    pub write_value: String,         // Written value (hex)
    pub write_pc_address: String,    // New program counter (hex)
    pub write_micro: String,         // Write micro-operation (hex)
}

/// BitVMX Prover Data (matches Python ProverDTO)
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct BitVMXProverData {
    pub setup_uuid: String,
    pub protocol_properties: BitVMXProtocolProperties,
    pub transactions: BitVMXTransactions,
    pub signatures: HashMap<String, String>, // Transaction signatures
    pub execution_result: u32,               // 0 = SUCCESS, 1 = FAILED
    pub execution_steps: u64,
    pub program_hash: String,
}

/// BitVMX Verifier Data (matches Python VerifierDTO) 
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct BitVMXVerifierData {
    pub setup_uuid: String,
    pub protocol_properties: BitVMXProtocolProperties,
    pub public_keys: HashMap<String, String>,
    pub verification_result: u32,            // 0 = SUCCESS, 1 = FAILED
    pub challenge_detected: bool,
    pub dispute_step: Option<u64>,
}

impl Default for BitVMXProtocolProperties {
    fn default() -> Self {
        Self {
            max_amount_of_steps: 10000,
            amount_of_input_words: 2,
            amount_of_bits_wrong_step_search: 4,
            amount_of_bits_per_digit_checksum: 4,
            amount_of_nibbles_hash_with_checksum: 64,
        }
    }
}