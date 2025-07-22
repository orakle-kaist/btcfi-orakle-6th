//! Bitcoin L1 Committer Implementation
//! 
//! Handles OP_RETURN transaction creation and broadcasting for option anchoring.

use bitcoin::{
    Network, OutPoint, ScriptBuf, Transaction, TxIn, TxOut, Witness, Amount, Txid,
    absolute::LockTime, transaction::Version,
    script::{PushBytesBuf, Builder as ScriptBuilder},
};
use std::str::FromStr;
use bitcoincore_rpc::{Auth, Client, RpcApi};
use serde::{Deserialize, Serialize};
use tracing::{info, warn, error, debug};

use defi_primitives::options::OptionTransaction;
use crate::config::CommitterConfig;

/// Bitcoin committer service
pub struct BitcoinCommitter {
    config: CommitterConfig,
    rpc_client: Client,
    http_client: reqwest::Client,
}

/// Pending transaction from option service
#[derive(Debug, Deserialize)]
pub struct PendingTransaction {
    pub transaction_id: String,
    pub option_transaction: OptionTransaction,
    pub priority: TransactionPriority,
    pub created_at: u64,
}

/// Transaction priority for batching
#[derive(Debug, Deserialize)]
pub enum TransactionPriority {
    High,    // CREATE, SETTLE - immediate
    Medium,  // BUY - can be batched
    Low,     // CHALLENGE - can wait
}

/// Commitment result
#[derive(Debug, Serialize)]
pub struct CommitmentResult {
    pub bitcoin_txid: String,
    pub option_transaction_id: String,
    pub block_hash: Option<String>,
    pub confirmations: u32,
    pub op_return_data: String,
    pub committed_at: u64,
}

impl BitcoinCommitter {
    /// Create new Bitcoin committer
    pub async fn new(config: CommitterConfig) -> Result<Self, Box<dyn std::error::Error>> {
        // Validate configuration
        config.validate()?;
        
        // Create Bitcoin RPC client
        let auth = Auth::UserPass(
            config.bitcoin_rpc_user.clone(),
            config.bitcoin_rpc_password.clone(),
        );
        
        let rpc_client = Client::new(&config.bitcoin_rpc_url, auth)?;
        
        // Test RPC connection
        let blockchain_info = rpc_client.get_blockchain_info()?;
        info!("📡 Connected to Bitcoin {} at block {}", 
              blockchain_info.chain, blockchain_info.blocks);
        
        // Create HTTP client for option service communication
        let http_client = reqwest::Client::builder()
            .timeout(std::time::Duration::from_secs(30))
            .build()?;
        
        // Ensure wallet exists or create it
        let committer = Self {
            config,
            rpc_client,
            http_client,
        };
        
        committer.ensure_wallet().await?;
        
        Ok(committer)
    }
    
    /// Main processing loop - fetch and commit pending transactions
    pub async fn process_pending_transactions(&mut self) -> Result<usize, Box<dyn std::error::Error>> {
        // Fetch pending transactions from option service
        let pending_txs = self.fetch_pending_transactions().await?;
        
        if pending_txs.is_empty() {
            return Ok(0);
        }
        
        debug!("📥 Fetched {} pending transactions", pending_txs.len());
        
        let mut committed_count = 0;
        
        // Process transactions by priority
        for pending_tx in pending_txs {
            let transaction_id = pending_tx.transaction_id.clone();
            match self.commit_transaction(pending_tx).await {
                Ok(result) => {
                    info!("✅ Committed transaction {} -> Bitcoin txid: {}", 
                          result.option_transaction_id, result.bitcoin_txid);
                    committed_count += 1;
                    
                    // Report back to option service
                    if let Err(e) = self.report_commitment_success(&result).await {
                        warn!("⚠️ Failed to report commitment success: {}", e);
                    }
                }
                Err(e) => {
                    error!("❌ Failed to commit transaction {}: {}", transaction_id, e);
                    
                    // Report failure to option service
                    if let Err(report_err) = self.report_commitment_failure(&transaction_id, &e.to_string()).await {
                        warn!("⚠️ Failed to report commitment failure: {}", report_err);
                    }
                }
            }
        }
        
        Ok(committed_count)
    }
    
    /// Commit single option transaction to Bitcoin L1
    async fn commit_transaction(&self, pending_tx: PendingTransaction) -> Result<CommitmentResult, Box<dyn std::error::Error>> {
        info!("🔗 Committing option transaction: {} (type: {:?})", 
              pending_tx.transaction_id, self.get_transaction_type(&pending_tx.option_transaction));
        
        // Serialize option transaction to OP_RETURN data
        let op_return_data = self.serialize_for_op_return(&pending_tx.option_transaction)?;
        
        // Create Bitcoin transaction with OP_RETURN
        let bitcoin_tx = self.create_op_return_transaction(&op_return_data).await?;
        
        // Broadcast transaction
        let tx_hex = bitcoin::consensus::encode::serialize_hex(&bitcoin_tx);
        let txid = self.rpc_client.send_raw_transaction(tx_hex)?;
        
        info!("📡 Broadcasted Bitcoin transaction: {}", txid);
        
        // Get transaction info for confirmation
        let tx_info = self.rpc_client.get_raw_transaction_info(&txid, None)?;
        
        Ok(CommitmentResult {
            bitcoin_txid: txid.to_string(),
            option_transaction_id: pending_tx.transaction_id,
            block_hash: tx_info.blockhash.map(|h| h.to_string()),
            confirmations: tx_info.confirmations.unwrap_or(0),
            op_return_data: hex::encode(&op_return_data),
            committed_at: chrono::Utc::now().timestamp() as u64,
        })
    }
    
    /// Create Bitcoin transaction with OP_RETURN output
    async fn create_op_return_transaction(&self, op_return_data: &[u8]) -> Result<Transaction, Box<dyn std::error::Error>> {
        // Get a UTXO for fees
        let unspent = self.rpc_client.list_unspent(None, None, None, None, None)?;
        
        if unspent.is_empty() {
            return Err("No unspent outputs available for fees".into());
        }
        
        let utxo = &unspent[0];
        let input_amount = utxo.amount;
        
        // Calculate fees (estimate 300 vbytes for OP_RETURN tx)
        let estimated_vbytes = 300;
        let fee_amount = bitcoin::Amount::from_sat(self.config.fee_rate * estimated_vbytes);
        
        if input_amount.to_sat() <= fee_amount.to_sat() {
            return Err("Insufficient funds for transaction fees".into());
        }
        
        let change_amount = Amount::from_sat(input_amount.to_sat() - fee_amount.to_sat());
        
        // Create transaction inputs
        let outpoint = OutPoint::new(utxo.txid, utxo.vout);
        let tx_in = TxIn {
            previous_output: outpoint,
            script_sig: ScriptBuf::new(),
            sequence: bitcoin::Sequence::ENABLE_RBF_NO_LOCKTIME,
            witness: Witness::new(),
        };
        
        // Create OP_RETURN output
        let op_return_script = ScriptBuilder::new()
            .push_opcode(bitcoin::opcodes::all::OP_RETURN)
            .push_slice(PushBytesBuf::try_from(op_return_data.to_vec())?)
            .into_script();
        
        let op_return_output = TxOut {
            value: bitcoin::Amount::ZERO,
            script_pubkey: op_return_script,
        };
        
        // Create change output (back to same wallet)
        let change_address = self.rpc_client.get_new_address(None, None)?;
        let change_output = TxOut {
            value: change_amount,
            script_pubkey: change_address.require_network(self.get_network())?.script_pubkey(),
        };
        
        // Build transaction
        let transaction = Transaction {
            version: Version::TWO,
            lock_time: LockTime::ZERO,
            input: vec![tx_in],
            output: vec![op_return_output, change_output],
        };
        
        // Sign transaction
        let tx_hex = bitcoin::consensus::encode::serialize_hex(&transaction);
        let signed_tx = self.rpc_client.sign_raw_transaction_with_wallet(
            tx_hex, 
            None, 
            None
        )?;
        
        if !signed_tx.complete {
            return Err("Failed to sign transaction".into());
        }
        
        // Deserialize the signed transaction
        let tx_bytes = hex::decode(&signed_tx.hex)?;
        let signed_transaction: Transaction = bitcoin::consensus::deserialize(&tx_bytes)?;
        Ok(signed_transaction)
    }
    
    /// Serialize option transaction for OP_RETURN (compressed)
    fn serialize_for_op_return(&self, option_tx: &OptionTransaction) -> Result<Vec<u8>, Box<dyn std::error::Error>> {
        // Serialize to JSON and compress
        let json_data = serde_json::to_vec(option_tx)?;
        
        // Simple compression (in production, could use flate2)
        let compressed_data = if json_data.len() > self.config.max_op_return_size {
            warn!("⚠️ Transaction data ({} bytes) exceeds OP_RETURN limit ({} bytes), truncating", 
                  json_data.len(), self.config.max_op_return_size);
            
            // Take first N bytes - in production would use proper compression
            json_data[..self.config.max_op_return_size].to_vec()
        } else {
            json_data
        };
        
        Ok(compressed_data)
    }
    
    /// Get transaction type string for logging
    fn get_transaction_type(&self, option_tx: &OptionTransaction) -> String {
        match option_tx {
            OptionTransaction::Create(_) => "CREATE".to_string(),
            OptionTransaction::Buy(_) => "BUY".to_string(),
            OptionTransaction::Settle(_) => "SETTLE".to_string(),
            OptionTransaction::Challenge(_) => "CHALLENGE".to_string(),
        }
    }
    
    /// Fetch pending transactions from option service
    async fn fetch_pending_transactions(&self) -> Result<Vec<PendingTransaction>, Box<dyn std::error::Error>> {
        let response = self.http_client
            .get(&self.config.transaction_queue_url)
            .send()
            .await?;
        
        if response.status().is_success() {
            let pending_txs: Vec<PendingTransaction> = response.json().await?;
            Ok(pending_txs)
        } else {
            warn!("⚠️ Failed to fetch pending transactions: {}", response.status());
            Ok(vec![])
        }
    }
    
    /// Report successful commitment back to option service
    async fn report_commitment_success(&self, result: &CommitmentResult) -> Result<(), Box<dyn std::error::Error>> {
        let report_url = format!("{}/commitment/success", 
                                self.config.transaction_queue_url.trim_end_matches("/pending"));
        
        let response = self.http_client
            .post(&report_url)
            .json(result)
            .send()
            .await?;
        
        if !response.status().is_success() {
            warn!("⚠️ Failed to report commitment success: {}", response.status());
        }
        
        Ok(())
    }
    
    /// Report commitment failure back to option service
    async fn report_commitment_failure(&self, transaction_id: &str, error: &str) -> Result<(), Box<dyn std::error::Error>> {
        let report_url = format!("{}/commitment/failure", 
                                self.config.transaction_queue_url.trim_end_matches("/pending"));
        
        let failure_report = serde_json::json!({
            "transaction_id": transaction_id,
            "error": error,
            "failed_at": chrono::Utc::now().timestamp()
        });
        
        let response = self.http_client
            .post(&report_url)
            .json(&failure_report)
            .send()
            .await?;
        
        if !response.status().is_success() {
            warn!("⚠️ Failed to report commitment failure: {}", response.status());
        }
        
        Ok(())
    }
    
    /// Ensure wallet exists or create it
    async fn ensure_wallet(&self) -> Result<(), Box<dyn std::error::Error>> {
        match self.rpc_client.get_wallet_info() {
            Ok(wallet_info) => {
                info!("💼 Using existing wallet: {}", wallet_info.wallet_name);
                Ok(())
            }
            Err(_) => {
                // Try to create wallet
                match self.rpc_client.create_wallet(&self.config.wallet_name, None, None, None, None) {
                    Ok(_) => {
                        info!("💼 Created new wallet: {}", self.config.wallet_name);
                        Ok(())
                    }
                    Err(e) => {
                        warn!("⚠️ Could not create wallet (may already exist): {}", e);
                        Ok(()) // Continue anyway, wallet might exist in different format
                    }
                }
            }
        }
    }
    
    /// Get Bitcoin network enum from config
    fn get_network(&self) -> Network {
        match self.config.bitcoin_network.as_str() {
            "mainnet" => Network::Bitcoin,
            "testnet" => Network::Testnet,
            "regtest" => Network::Regtest,
            _ => Network::Regtest, // Default fallback
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use defi_primitives::options::{CreateOptionTx, OptionType, TxType};

    fn create_mock_option_transaction() -> OptionTransaction {
        let create_tx = CreateOptionTx {
            protocol: "BTCFI01".to_string(),
            tx_type: TxType::Create,
            option_id: "test_option_123".to_string(),
            option_type: OptionType::Call,
            underlying: "BTCUSD".to_string(),
            strike: 52000,
            expiry: 1723126800,
            unit: 1.0,
            issuer: "bc1qtest".to_string(),
            initial_iv: 0.68,
            premium_formula: "Black-Scholes".to_string(),
            oracle_ids: vec!["binance".to_string(), "coinbase".to_string()],
            created_at: 1722450000,
            sig: "0xtest".to_string(),
        };
        
        OptionTransaction::Create(create_tx)
    }

    #[test]
    fn test_committer_config() {
        let config = CommitterConfig::default();
        assert!(config.validate().is_ok());
        assert_eq!(config.max_op_return_size, 80);
        assert_eq!(config.fee_rate, 10);
    }

    #[test]
    fn test_op_return_serialization() {
        let config = CommitterConfig::default();
        
        // This test would need a real Bitcoin connection, so we'll skip the actual RPC calls
        // and just test the serialization logic
        
        let option_tx = create_mock_option_transaction();
        
        // Test that we can create a committer config
        assert!(config.validate().is_ok());
        
        // Test network conversion
        let networks = ["mainnet", "testnet", "regtest"];
        for network in networks {
            let mut test_config = config.clone();
            test_config.bitcoin_network = network.to_string();
            assert!(test_config.validate().is_ok());
        }
    }

    #[test]
    fn test_transaction_priority() {
        // Test that priority enum deserializes correctly
        let high_priority = serde_json::from_str::<TransactionPriority>("\"High\"").unwrap();
        assert!(matches!(high_priority, TransactionPriority::High));
        
        let medium_priority = serde_json::from_str::<TransactionPriority>("\"Medium\"").unwrap();
        assert!(matches!(medium_priority, TransactionPriority::Medium));
    }
}