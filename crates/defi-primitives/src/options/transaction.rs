//! Option transaction types and serialization

use serde::{Deserialize, Serialize};
use super::types::{OptionType, OptionStatus};

/// Protocol identifier for BTCFi options
pub const PROTOCOL_ID: &str = "BTCFI01";

/// Transaction types for option lifecycle
#[derive(Debug, Clone, Copy, PartialEq, Serialize, Deserialize)]
#[serde(rename_all = "UPPERCASE")]
pub enum TxType {
    /// Create new option product
    Create,
    /// Buy option
    Buy,
    /// Settle option at expiry
    Settle,
    /// Challenge oracle price or settlement
    Challenge,
}

/// Option creation transaction
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CreateOptionTx {
    pub protocol: String,
    pub tx_type: TxType,
    pub option_id: String,
    pub option_type: OptionType,
    pub underlying: String,
    pub strike: u64,
    pub expiry: u64,
    pub unit: f64,
    pub issuer: String,
    pub initial_iv: f64,
    pub premium_formula: String,
    pub oracle_ids: Vec<String>,
    pub created_at: u64,
    pub sig: String,
}

impl CreateOptionTx {
    pub fn new(
        option_id: String,
        option_type: OptionType,
        underlying: String,
        strike: u64,
        expiry: u64,
        issuer: String,
        initial_iv: f64,
        oracle_ids: Vec<String>,
        created_at: u64,
    ) -> Self {
        Self {
            protocol: PROTOCOL_ID.to_string(),
            tx_type: TxType::Create,
            option_id,
            option_type,
            underlying,
            strike,
            expiry,
            unit: 1.0,
            issuer,
            initial_iv,
            premium_formula: "Black-Scholes".to_string(),
            oracle_ids,
            created_at,
            sig: String::new(), // Will be filled by signing service
        }
    }
}

/// Option purchase transaction
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct BuyOptionTx {
    pub protocol: String,
    pub tx_type: TxType,
    pub option_id: String,
    pub buyer: String,
    pub buy_quantity: u64,
    pub premium_unit: f64,
    pub premium_paid: f64,
    pub buy_txid: String,
    pub pool_balance_snapshot: f64,
    pub timestamp: u64,
    pub sig: String,
}

impl BuyOptionTx {
    pub fn new(
        option_id: String,
        buyer: String,
        buy_quantity: u64,
        premium_unit: f64,
        buy_txid: String,
        pool_balance: f64,
        timestamp: u64,
    ) -> Self {
        let premium_paid = buy_quantity as f64 * premium_unit;
        Self {
            protocol: PROTOCOL_ID.to_string(),
            tx_type: TxType::Buy,
            option_id,
            buyer,
            buy_quantity,
            premium_unit,
            premium_paid,
            buy_txid,
            pool_balance_snapshot: pool_balance,
            timestamp,
            sig: String::new(),
        }
    }
}

/// Option settlement transaction
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SettleOptionTx {
    pub protocol: String,
    pub tx_type: TxType,
    pub option_id: String,
    pub buyer: String,
    pub settle_quantity: u64,
    pub settle_price: u64,
    pub settle_timestamp: u64,
    pub settle_pnl: f64,
    pub oracle_proof: String,
    pub bitvmx_proof: String,
    pub pool_balance_snapshot: f64,
    pub settle_status: String,
    pub sig: String,
}

impl SettleOptionTx {
    pub fn new(
        option_id: String,
        buyer: String,
        settle_quantity: u64,
        settle_price: u64,
        settle_pnl: f64,
        oracle_proof: String,
        bitvmx_proof: String,
        pool_balance: f64,
        timestamp: u64,
    ) -> Self {
        Self {
            protocol: PROTOCOL_ID.to_string(),
            tx_type: TxType::Settle,
            option_id,
            buyer,
            settle_quantity,
            settle_price,
            settle_timestamp: timestamp,
            settle_pnl,
            oracle_proof,
            bitvmx_proof,
            pool_balance_snapshot: pool_balance,
            settle_status: "PAID".to_string(),
            sig: String::new(),
        }
    }
}

/// Challenge transaction for disputes
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ChallengeTx {
    pub protocol: String,
    pub tx_type: TxType,
    pub option_id: String,
    pub challenge_by: String,
    pub challenge_type: ChallengeType,
    pub challenge_proof: String,
    pub timestamp: u64,
    pub sig: String,
}

/// Types of challenges
#[derive(Debug, Clone, Copy, PartialEq, Serialize, Deserialize)]
#[serde(rename_all = "SCREAMING_SNAKE_CASE")]
pub enum ChallengeType {
    OraclePrice,
    SettlementCalculation,
    ProofValidity,
}

impl ChallengeTx {
    pub fn new(
        option_id: String,
        challenger: String,
        challenge_type: ChallengeType,
        proof: String,
        timestamp: u64,
    ) -> Self {
        Self {
            protocol: PROTOCOL_ID.to_string(),
            tx_type: TxType::Challenge,
            option_id,
            challenge_by: challenger,
            challenge_type,
            challenge_proof: proof,
            timestamp,
            sig: String::new(),
        }
    }
}

/// Unified option transaction enum
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(untagged)]
pub enum OptionTransaction {
    Create(CreateOptionTx),
    Buy(BuyOptionTx),
    Settle(SettleOptionTx),
    Challenge(ChallengeTx),
}

/// Serialization for Bitcoin OP_RETURN
pub mod op_return {
    use super::*;
    
    /// Maximum OP_RETURN size in Bitcoin
    pub const MAX_OP_RETURN_SIZE: usize = 80;
    
    /// Serialize transaction to OP_RETURN format
    /// Returns the serialized data and optional continuation chunks
    pub fn serialize_for_op_return(tx: &OptionTransaction) -> Result<Vec<Vec<u8>>, String> {
        // Convert to JSON
        let json = serde_json::to_string(tx)
            .map_err(|e| format!("JSON serialization failed: {}", e))?;
        
        // Compress using zlib
        let compressed = compress_data(json.as_bytes())?;
        
        // Split into chunks if needed
        let chunks = split_into_chunks(&compressed, MAX_OP_RETURN_SIZE);
        
        Ok(chunks)
    }
    
    /// Deserialize from OP_RETURN chunks
    pub fn deserialize_from_op_return(chunks: Vec<Vec<u8>>) -> Result<OptionTransaction, String> {
        // Remove chunk headers and combine data
        let combined: Vec<u8> = chunks.into_iter()
            .map(|chunk| {
                if chunk.len() >= 2 && chunk[0] == 0xBF {
                    chunk[2..].to_vec() // Skip marker and index
                } else {
                    chunk
                }
            })
            .flatten()
            .collect();
        
        // Decompress
        let decompressed = decompress_data(&combined)?;
        
        // Parse JSON
        let tx = serde_json::from_slice(&decompressed)
            .map_err(|e| format!("JSON deserialization failed: {}", e))?;
        
        Ok(tx)
    }
    
    fn compress_data(data: &[u8]) -> Result<Vec<u8>, String> {
        use flate2::write::ZlibEncoder;
        use flate2::Compression;
        use std::io::Write;
        
        let mut encoder = ZlibEncoder::new(Vec::new(), Compression::best());
        encoder.write_all(data)
            .map_err(|e| format!("Compression failed: {}", e))?;
        encoder.finish()
            .map_err(|e| format!("Compression finish failed: {}", e))
    }
    
    fn decompress_data(data: &[u8]) -> Result<Vec<u8>, String> {
        use flate2::read::ZlibDecoder;
        use std::io::Read;
        
        let mut decoder = ZlibDecoder::new(data);
        let mut decompressed = Vec::new();
        decoder.read_to_end(&mut decompressed)
            .map_err(|e| format!("Decompression failed: {}", e))?;
        Ok(decompressed)
    }
    
    fn split_into_chunks(data: &[u8], chunk_size: usize) -> Vec<Vec<u8>> {
        data.chunks(chunk_size - 2) // Reserve 2 bytes for chunk header
            .enumerate()
            .map(|(i, chunk)| {
                let mut result = Vec::with_capacity(chunk.len() + 2);
                result.push(0xBF); // BTCFi marker
                result.push(i as u8); // Chunk index
                result.extend_from_slice(chunk);
                result
            })
            .collect()
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use super::op_return::*;
    
    #[test]
    fn test_create_option_tx_serialization() {
        let tx = CreateOptionTx::new(
            "0xabc123".to_string(),
            OptionType::Call,
            "BTCUSD".to_string(),
            52000,
            1723126800,
            "bc1q...".to_string(),
            0.68,
            vec!["binance".to_string(), "coinbase".to_string()],
            1722450000,
        );
        
        let json = serde_json::to_string(&tx).unwrap();
        assert!(json.contains("BTCFI01"));
        assert!(json.contains("CREATE"));
    }
    
    #[test]
    fn test_option_transaction_enum_serialization() {
        let create_tx = CreateOptionTx::new(
            "0xabc123".to_string(),
            OptionType::Call,
            "BTCUSD".to_string(),
            52000,
            1723126800,
            "bc1q...".to_string(),
            0.68,
            vec!["binance".to_string()],
            1722450000,
        );
        
        let tx = OptionTransaction::Create(create_tx);
        let json = serde_json::to_string(&tx).unwrap();
        let deserialized: OptionTransaction = serde_json::from_str(&json).unwrap();
        
        match deserialized {
            OptionTransaction::Create(create) => {
                assert_eq!(create.option_id, "0xabc123");
            }
            _ => panic!("Wrong transaction type"),
        }
    }
    
    #[test]
    fn test_op_return_serialization() {
        let buy_tx = BuyOptionTx::new(
            "0xabc123".to_string(),
            "bc1q_buyer".to_string(),
            2,
            0.00121,
            "0x99ffee".to_string(),
            52.10,
            1722512100,
        );
        
        let tx = OptionTransaction::Buy(buy_tx);
        
        // Test serialization
        let chunks = serialize_for_op_return(&tx).unwrap();
        assert!(!chunks.is_empty());
        
        // Each chunk should start with BTCFi marker
        for chunk in &chunks {
            assert_eq!(chunk[0], 0xBF); // BTCFi marker
        }
        
        // Test deserialization
        let deserialized = deserialize_from_op_return(chunks).unwrap();
        match deserialized {
            OptionTransaction::Buy(buy) => {
                assert_eq!(buy.option_id, "0xabc123");
                assert_eq!(buy.buy_quantity, 2);
            }
            _ => panic!("Wrong transaction type after deserialization"),
        }
    }
    
    #[test]
    fn test_all_transaction_types() {
        // Test CREATE
        let create_tx = CreateOptionTx::new(
            "opt001".to_string(),
            OptionType::Put,
            "BTCUSD".to_string(),
            48000,
            1723126800,
            "vault123".to_string(),
            0.75,
            vec!["binance".to_string(), "kraken".to_string()],
            1722450000,
        );
        assert_eq!(create_tx.tx_type, TxType::Create);
        
        // Test BUY
        let buy_tx = BuyOptionTx::new(
            "opt001".to_string(),
            "user123".to_string(),
            5,
            0.002,
            "txid123".to_string(),
            100.5,
            1722512100,
        );
        assert_eq!(buy_tx.premium_paid, 0.01); // 5 * 0.002
        
        // Test SETTLE
        let settle_tx = SettleOptionTx::new(
            "opt001".to_string(),
            "user123".to_string(),
            5,
            50000,
            0.1,
            "oracle_proof".to_string(),
            "bitvmx_proof".to_string(),
            99.9,
            1723126800,
        );
        assert_eq!(settle_tx.settle_status, "PAID");
        
        // Test CHALLENGE
        let challenge_tx = ChallengeTx::new(
            "opt001".to_string(),
            "challenger".to_string(),
            ChallengeType::OraclePrice,
            "fraud_proof".to_string(),
            1723130000,
        );
        assert_eq!(challenge_tx.challenge_type, ChallengeType::OraclePrice);
    }
}