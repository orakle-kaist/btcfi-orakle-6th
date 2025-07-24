//! Bitcoin OP_RETURN anchoring for option registration - BTCFi Protocol v2
//! 
//! Based on Price Anchoring Branch's exact data schema
//! 28 bytes total: TX Type (1) + Option ID (6) + Option Type (1) + Strike (8) + Expiry (8) + Unit (4)

use anyhow::Result;
use bitcoin::{Network, ScriptBuf, opcodes::all::OP_RETURN, blockdata::script::Builder};
use serde::{Deserialize, Serialize};
use crate::simple_contract::SimpleOption;
use oracle_vm_common::types::OptionType;
use sha2::{Sha256, Digest};

/// BTCFi Protocol Transaction Types
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
#[repr(u8)]
pub enum TxType {
    Create = 0x00,
    Buy = 0x01,
    Settle = 0x02,
    Challenge = 0x03,
}

/// BTCFi CREATE transaction data (28 bytes)
#[derive(Debug, Clone)]
pub struct CreateOptionAnchorData {
    pub tx_type: TxType,          // 1 byte
    pub option_id: [u8; 6],       // 6 bytes (hash of option ID string)
    pub option_type: u8,          // 1 byte (0=Call, 1=Put)
    pub strike_sats: u64,         // 8 bytes (big-endian, USD to satoshi conversion)
    pub expiry: u64,              // 8 bytes (big-endian, Unix timestamp)
    pub unit: f32,                // 4 bytes (IEEE 754 float, typically 1.0)
}

impl CreateOptionAnchorData {
    /// Create from SimpleOption with proper conversions
    pub fn from_option(option: &SimpleOption) -> Self {
        // Generate 6-byte option ID hash
        let mut hasher = Sha256::new();
        hasher.update(option.option_id.as_bytes());
        let hash = hasher.finalize();
        let mut option_id = [0u8; 6];
        option_id.copy_from_slice(&hash[0..6]);

        // Convert USD cents to satoshis
        // Price in cents -> Price in USD -> Price in BTC -> Price in satoshis
        // For example: 5000000 cents = $50,000 USD
        // At BTC = $50,000, 1 USD = 0.00002 BTC = 2000 sats
        // So $50,000 = 1 BTC = 100,000,000 sats
        let strike_sats = option.strike_price as u64 * 100_000_000 / 100; // cents to sats

        // Convert block height to Unix timestamp (approximate)
        // Assuming ~10 minutes per block
        let current_time = chrono::Utc::now().timestamp() as u64;
        let blocks_in_future = option.expiry_height as u64;
        let expiry = current_time + (blocks_in_future * 600); // 600 seconds per block

        Self {
            tx_type: TxType::Create,
            option_id,
            option_type: match option.option_type {
                OptionType::Call => 0,
                OptionType::Put => 1,
            },
            strike_sats,
            expiry,
            unit: 1.0,
        }
    }

    /// Encode to exact 28-byte format for OP_RETURN
    pub fn encode(&self) -> Vec<u8> {
        let mut data = Vec::with_capacity(28);
        
        // TX Type (1 byte)
        data.push(self.tx_type as u8);
        
        // Option ID (6 bytes)
        data.extend_from_slice(&self.option_id);
        
        // Option Type (1 byte)
        data.push(self.option_type);
        
        // Strike (8 bytes, big-endian)
        data.extend_from_slice(&self.strike_sats.to_be_bytes());
        
        // Expiry (8 bytes, big-endian)
        data.extend_from_slice(&self.expiry.to_be_bytes());
        
        // Unit (4 bytes, IEEE 754 float, big-endian)
        data.extend_from_slice(&self.unit.to_be_bytes());
        
        assert_eq!(data.len(), 28, "CREATE data must be exactly 28 bytes");
        data
    }

    /// Decode from 28-byte OP_RETURN data
    pub fn decode(data: &[u8]) -> Result<Self> {
        if data.len() != 28 {
            return Err(anyhow::anyhow!("CREATE data must be exactly 28 bytes, got {}", data.len()));
        }

        let tx_type = match data[0] {
            0x00 => TxType::Create,
            0x01 => TxType::Buy,
            0x02 => TxType::Settle,
            0x03 => TxType::Challenge,
            _ => return Err(anyhow::anyhow!("Invalid TX type: {}", data[0])),
        };

        if tx_type != TxType::Create {
            return Err(anyhow::anyhow!("Expected CREATE transaction, got {:?}", tx_type));
        }

        let mut option_id = [0u8; 6];
        option_id.copy_from_slice(&data[1..7]);

        let option_type = data[7];
        if option_type > 1 {
            return Err(anyhow::anyhow!("Invalid option type: {}", option_type));
        }

        let strike_sats = u64::from_be_bytes([
            data[8], data[9], data[10], data[11],
            data[12], data[13], data[14], data[15],
        ]);

        let expiry = u64::from_be_bytes([
            data[16], data[17], data[18], data[19],
            data[20], data[21], data[22], data[23],
        ]);

        let unit = f32::from_be_bytes([data[24], data[25], data[26], data[27]]);

        Ok(Self {
            tx_type,
            option_id,
            option_type,
            strike_sats,
            expiry,
            unit,
        })
    }

    /// Convert strike from satoshis to USD
    pub fn strike_usd(&self) -> f64 {
        // Reverse the conversion: sats -> BTC -> USD
        (self.strike_sats as f64 * 100.0) / 100_000_000.0
    }

    /// Format option ID as hex string
    pub fn option_id_hex(&self) -> String {
        hex::encode(&self.option_id).to_uppercase()
    }
}

/// Enhanced Bitcoin anchoring service with BTCFi protocol support
pub struct BitcoinAnchoringServiceV2 {
    network: Network,
    node_url: String,
    rpc_user: String,
    rpc_password: String,
}

impl BitcoinAnchoringServiceV2 {
    /// Create new anchoring service
    pub fn new(network: Network, node_url: String, rpc_user: String, rpc_password: String) -> Self {
        Self {
            network,
            node_url,
            rpc_user,
            rpc_password,
        }
    }

    /// Create for regtest with standard credentials
    pub fn regtest() -> Self {
        Self {
            network: Network::Regtest,
            node_url: "localhost:18443".to_string(),
            rpc_user: "test".to_string(),
            rpc_password: "test".to_string(),
        }
    }

    /// Anchor option data on-chain using BTCFi protocol
    pub async fn anchor_option(&self, option: &SimpleOption) -> Result<String> {
        // Create BTCFi CREATE anchor data
        let anchor_data = CreateOptionAnchorData::from_option(option);
        let encoded_data = anchor_data.encode();

        log::info!(
            "Anchoring option {} with BTCFi CREATE protocol: {} bytes",
            option.option_id,
            encoded_data.len()
        );

        // Send transaction via bitcoin-cli
        let txid = self.send_op_return_transaction(&encoded_data).await?;
        
        log::info!(
            "Option {} anchored on-chain: txid = {}",
            option.option_id,
            txid
        );

        Ok(txid)
    }

    /// Send OP_RETURN transaction via bitcoin-cli
    async fn send_op_return_transaction(&self, data: &[u8]) -> Result<String> {
        let hex_data = hex::encode(data);
        
        // Get a change address
        let change_addr_output = std::process::Command::new("bitcoin-cli")
            .args(&[
                "-regtest",
                "-rpcuser", &self.rpc_user,
                "-rpcpassword", &self.rpc_password,
                "-rpcconnect", &self.node_url,
                "getnewaddress",
                "option_change",
            ])
            .output()?;

        if !change_addr_output.status.success() {
            return Err(anyhow::anyhow!("Failed to get change address: {}", 
                String::from_utf8_lossy(&change_addr_output.stderr)));
        }

        let change_address = String::from_utf8(change_addr_output.stdout)?.trim().to_string();

        // Create raw transaction with OP_RETURN and change output
        let outputs = format!(
            r#"{{"data":"{}","{}":0.001}}"#,
            hex_data,
            change_address
        );

        let create_output = std::process::Command::new("bitcoin-cli")
            .args(&[
                "-regtest",
                "-rpcuser", &self.rpc_user,
                "-rpcpassword", &self.rpc_password,
                "-rpcconnect", &self.node_url,
                "createrawtransaction",
                "[]",
                &outputs,
            ])
            .output()?;

        if !create_output.status.success() {
            return Err(anyhow::anyhow!("Failed to create raw transaction: {}", 
                String::from_utf8_lossy(&create_output.stderr)));
        }

        let raw_tx = String::from_utf8(create_output.stdout)?.trim().to_string();

        // Fund, sign, and send in sequence
        let funded_tx = self.fund_transaction(&raw_tx)?;
        let signed_tx = self.sign_transaction(&funded_tx)?;
        let txid = self.broadcast_transaction(&signed_tx)?;

        Ok(txid)
    }

    fn fund_transaction(&self, raw_tx: &str) -> Result<String> {
        let output = std::process::Command::new("bitcoin-cli")
            .args(&[
                "-regtest",
                "-rpcuser", &self.rpc_user,
                "-rpcpassword", &self.rpc_password,
                "-rpcconnect", &self.node_url,
                "fundrawtransaction",
                raw_tx,
            ])
            .output()?;

        if !output.status.success() {
            return Err(anyhow::anyhow!("Failed to fund transaction: {}", 
                String::from_utf8_lossy(&output.stderr)));
        }

        let result: serde_json::Value = serde_json::from_slice(&output.stdout)?;
        Ok(result["hex"].as_str().unwrap().to_string())
    }

    fn sign_transaction(&self, funded_tx: &str) -> Result<String> {
        let output = std::process::Command::new("bitcoin-cli")
            .args(&[
                "-regtest",
                "-rpcuser", &self.rpc_user,
                "-rpcpassword", &self.rpc_password,
                "-rpcconnect", &self.node_url,
                "signrawtransactionwithwallet",
                funded_tx,
            ])
            .output()?;

        if !output.status.success() {
            return Err(anyhow::anyhow!("Failed to sign transaction: {}", 
                String::from_utf8_lossy(&output.stderr)));
        }

        let result: serde_json::Value = serde_json::from_slice(&output.stdout)?;
        if !result["complete"].as_bool().unwrap_or(false) {
            return Err(anyhow::anyhow!("Transaction signing incomplete"));
        }
        
        Ok(result["hex"].as_str().unwrap().to_string())
    }

    fn broadcast_transaction(&self, signed_tx: &str) -> Result<String> {
        let output = std::process::Command::new("bitcoin-cli")
            .args(&[
                "-regtest",
                "-rpcuser", &self.rpc_user,
                "-rpcpassword", &self.rpc_password,
                "-rpcconnect", &self.node_url,
                "sendrawtransaction",
                signed_tx,
            ])
            .output()?;

        if !output.status.success() {
            return Err(anyhow::anyhow!("Failed to broadcast transaction: {}", 
                String::from_utf8_lossy(&output.stderr)));
        }

        Ok(String::from_utf8(output.stdout)?.trim().to_string())
    }

    /// Verify and decode option anchor from transaction
    pub async fn verify_anchor(&self, txid: &str) -> Result<CreateOptionAnchorData> {
        let output = std::process::Command::new("bitcoin-cli")
            .args(&[
                "-regtest",
                "-rpcuser", &self.rpc_user,
                "-rpcpassword", &self.rpc_password,
                "-rpcconnect", &self.node_url,
                "getrawtransaction",
                txid,
                "true",
            ])
            .output()?;

        if !output.status.success() {
            return Err(anyhow::anyhow!("Failed to get transaction: {}", 
                String::from_utf8_lossy(&output.stderr)));
        }

        let tx_data: serde_json::Value = serde_json::from_slice(&output.stdout)?;
        
        // Find OP_RETURN output
        let vout = tx_data["vout"].as_array()
            .ok_or_else(|| anyhow::anyhow!("No outputs in transaction"))?;

        for output in vout {
            if let Some(script_type) = output["scriptPubKey"]["type"].as_str() {
                if script_type == "nulldata" {
                    // Found OP_RETURN output
                    let hex_data = output["scriptPubKey"]["hex"].as_str()
                        .ok_or_else(|| anyhow::anyhow!("No hex in OP_RETURN output"))?;
                    
                    // Decode hex and extract data (skip OP_RETURN prefix)
                    let decoded = hex::decode(hex_data)?;
                    if decoded.len() >= 30 && decoded[0] == 0x6a && decoded[1] == 0x1c {
                        // 0x6a = OP_RETURN, 0x1c = 28 (data length)
                        let op_return_data = &decoded[2..30];
                        return CreateOptionAnchorData::decode(op_return_data);
                    }
                }
            }
        }

        Err(anyhow::anyhow!("No valid BTCFi CREATE data found in transaction"))
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_btcfi_create_encoding() {
        let mut option = SimpleOption {
            option_id: "BTCCALL52000D_7".to_string(),
            option_type: OptionType::Call,
            strike_price: 52000_00, // $52,000 in cents
            quantity: 100_000_000,  // 1 BTC
            premium_paid: 0,
            expiry_height: 1008,    // ~7 days
            status: crate::simple_contract::OptionStatus::Active,
            user_id: "test".to_string(),
        };

        let anchor = CreateOptionAnchorData::from_option(&option);
        let encoded = anchor.encode();
        
        // Verify exact 28 bytes
        assert_eq!(encoded.len(), 28);
        
        // Verify TX type
        assert_eq!(encoded[0], 0x00); // CREATE
        
        // Verify option type
        assert_eq!(encoded[7], 0x00); // CALL
        
        // Decode and verify
        let decoded = CreateOptionAnchorData::decode(&encoded).unwrap();
        assert_eq!(decoded.tx_type as u8, TxType::Create as u8);
        assert_eq!(decoded.option_type, 0);
        assert_eq!(decoded.unit, 1.0);
        
        // Test PUT option
        option.option_type = OptionType::Put;
        let put_anchor = CreateOptionAnchorData::from_option(&option);
        let put_encoded = put_anchor.encode();
        assert_eq!(put_encoded[7], 0x01); // PUT
    }

    #[test]
    fn test_strike_price_conversion() {
        let option = SimpleOption {
            option_id: "TEST".to_string(),
            option_type: OptionType::Call,
            strike_price: 50000_00, // $50,000 in cents
            quantity: 100_000_000,
            premium_paid: 0,
            expiry_height: 1000,
            status: crate::simple_contract::OptionStatus::Active,
            user_id: "test".to_string(),
        };

        let anchor = CreateOptionAnchorData::from_option(&option);
        
        // Verify strike conversion
        assert_eq!(anchor.strike_usd(), 50000.0);
        
        // Verify encoding maintains precision
        let encoded = anchor.encode();
        let decoded = CreateOptionAnchorData::decode(&encoded).unwrap();
        assert_eq!(decoded.strike_usd(), 50000.0);
    }
}