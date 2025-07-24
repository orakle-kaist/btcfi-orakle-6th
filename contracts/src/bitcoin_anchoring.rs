//! Bitcoin OP_RETURN anchoring for option registration
//! 
//! This module handles on-chain anchoring of option data using Bitcoin's OP_RETURN
//! Based on Price Anchoring Branch implementation

use anyhow::Result;
use bitcoin::{
    Address, Network, Transaction, TxOut, ScriptBuf, Txid,
    blockdata::script::Builder, opcodes::all::OP_RETURN
};
use serde::{Deserialize, Serialize};
use crate::simple_contract::SimpleOption;
use oracle_vm_common::types::OptionType;

/// OP_RETURN data schema for option registration
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct OptionAnchorData {
    pub option_type: u8,      // 0 = Call, 1 = Put
    pub strike_price: u64,    // USD cents
    pub expiry: u64,          // Unix timestamp
}

impl OptionAnchorData {
    /// Create from SimpleOption
    pub fn from_option(option: &SimpleOption) -> Self {
        Self {
            option_type: match option.option_type {
                OptionType::Call => 0,
                OptionType::Put => 1,
            },
            strike_price: option.strike_price,
            expiry: option.expiry_height as u64, // Convert block height to timestamp in production
        }
    }

    /// Encode to compact format for OP_RETURN
    /// Format: "CREATE:{type}:{strike}:{expiry}"
    pub fn encode(&self) -> Vec<u8> {
        let data = format!(
            "CREATE:{}:{}:{}", 
            self.option_type,
            self.strike_price,
            self.expiry
        );
        data.into_bytes()
    }

    /// Decode from OP_RETURN data
    pub fn decode(data: &[u8]) -> Result<Self> {
        let data_str = String::from_utf8(data.to_vec())?;
        let parts: Vec<&str> = data_str.split(':').collect();
        
        if parts.len() != 4 || parts[0] != "CREATE" {
            return Err(anyhow::anyhow!("Invalid anchor data format"));
        }

        Ok(Self {
            option_type: parts[1].parse()?,
            strike_price: parts[2].parse()?,
            expiry: parts[3].parse()?,
        })
    }
}

/// Bitcoin anchoring service for options
pub struct BitcoinAnchoringService {
    network: Network,
    node_url: String,
    rpc_user: String,
    rpc_password: String,
}

impl BitcoinAnchoringService {
    /// Create new anchoring service
    pub fn new(network: Network, node_url: String, rpc_user: String, rpc_password: String) -> Self {
        Self {
            network,
            node_url,
            rpc_user,
            rpc_password,
        }
    }

    /// Create for regtest
    pub fn regtest() -> Self {
        Self {
            network: Network::Regtest,
            node_url: "http://localhost:18443".to_string(),
            rpc_user: "test".to_string(),
            rpc_password: "test".to_string(),
        }
    }

    /// Anchor option data on-chain
    pub async fn anchor_option(&self, option: &SimpleOption) -> Result<String> {
        // Create anchor data
        let anchor_data = OptionAnchorData::from_option(option);
        let encoded_data = anchor_data.encode();

        // Check data size (Bitcoin OP_RETURN limit is 80 bytes)
        if encoded_data.len() > 80 {
            return Err(anyhow::anyhow!("Anchor data too large: {} bytes", encoded_data.len()));
        }

        // Create OP_RETURN script
        let op_return_script = Builder::new()
            .push_opcode(OP_RETURN)
            .push_slice(&encoded_data)
            .into_script();

        // Send transaction via RPC
        let txid = self.send_op_return_transaction(&encoded_data).await?;
        
        log::info!(
            "Option {} anchored on-chain: txid = {}, data = {:?}",
            option.option_id,
            txid,
            String::from_utf8_lossy(&encoded_data)
        );

        Ok(txid)
    }

    /// Send OP_RETURN transaction via Bitcoin RPC
    async fn send_op_return_transaction(&self, data: &[u8]) -> Result<String> {
        // Use bitcoin-cli for simplicity in testing
        let hex_data = hex::encode(data);
        
        // Create raw transaction with OP_RETURN output
        let create_cmd = std::process::Command::new("bitcoin-cli")
            .args(&[
                &format!("-{}", if self.network == Network::Regtest { "regtest" } else { "testnet" }),
                "-rpcuser", &self.rpc_user,
                "-rpcpassword", &self.rpc_password,
                "-rpcconnect", &self.node_url.replace("http://", "").replace(":18443", ""),
                "createrawtransaction",
                "[]",
                &format!(r#"{{"data":"{}"}}"#, hex_data),
            ])
            .output()?;

        if !create_cmd.status.success() {
            return Err(anyhow::anyhow!("Failed to create raw transaction: {}", 
                String::from_utf8_lossy(&create_cmd.stderr)));
        }

        let raw_tx = String::from_utf8(create_cmd.stdout)?.trim().to_string();

        // Fund the transaction
        let fund_cmd = std::process::Command::new("bitcoin-cli")
            .args(&[
                &format!("-{}", if self.network == Network::Regtest { "regtest" } else { "testnet" }),
                "-rpcuser", &self.rpc_user,
                "-rpcpassword", &self.rpc_password,
                "-rpcconnect", &self.node_url.replace("http://", "").replace(":18443", ""),
                "fundrawtransaction",
                &raw_tx,
            ])
            .output()?;

        if !fund_cmd.status.success() {
            return Err(anyhow::anyhow!("Failed to fund transaction: {}", 
                String::from_utf8_lossy(&fund_cmd.stderr)));
        }

        let funded_result: serde_json::Value = serde_json::from_slice(&fund_cmd.stdout)?;
        let funded_hex = funded_result["hex"].as_str()
            .ok_or_else(|| anyhow::anyhow!("No hex in fund result"))?;

        // Sign the transaction
        let sign_cmd = std::process::Command::new("bitcoin-cli")
            .args(&[
                &format!("-{}", if self.network == Network::Regtest { "regtest" } else { "testnet" }),
                "-rpcuser", &self.rpc_user,
                "-rpcpassword", &self.rpc_password,
                "-rpcconnect", &self.node_url.replace("http://", "").replace(":18443", ""),
                "signrawtransactionwithwallet",
                funded_hex,
            ])
            .output()?;

        if !sign_cmd.status.success() {
            return Err(anyhow::anyhow!("Failed to sign transaction: {}", 
                String::from_utf8_lossy(&sign_cmd.stderr)));
        }

        let signed_result: serde_json::Value = serde_json::from_slice(&sign_cmd.stdout)?;
        let signed_hex = signed_result["hex"].as_str()
            .ok_or_else(|| anyhow::anyhow!("No hex in sign result"))?;

        // Send the transaction
        let send_cmd = std::process::Command::new("bitcoin-cli")
            .args(&[
                &format!("-{}", if self.network == Network::Regtest { "regtest" } else { "testnet" }),
                "-rpcuser", &self.rpc_user,
                "-rpcpassword", &self.rpc_password,
                "-rpcconnect", &self.node_url.replace("http://", "").replace(":18443", ""),
                "sendrawtransaction",
                signed_hex,
            ])
            .output()?;

        if !send_cmd.status.success() {
            return Err(anyhow::anyhow!("Failed to send transaction: {}", 
                String::from_utf8_lossy(&send_cmd.stderr)));
        }

        let txid = String::from_utf8(send_cmd.stdout)?.trim().to_string();
        Ok(txid)
    }

    /// Verify option anchor on-chain
    pub async fn verify_anchor(&self, txid: &str) -> Result<OptionAnchorData> {
        // Get transaction from Bitcoin node
        let get_tx_cmd = std::process::Command::new("bitcoin-cli")
            .args(&[
                &format!("-{}", if self.network == Network::Regtest { "regtest" } else { "testnet" }),
                "-rpcuser", &self.rpc_user,
                "-rpcpassword", &self.rpc_password,
                "-rpcconnect", &self.node_url.replace("http://", "").replace(":18443", ""),
                "getrawtransaction",
                txid,
                "true", // verbose
            ])
            .output()?;

        if !get_tx_cmd.status.success() {
            return Err(anyhow::anyhow!("Failed to get transaction: {}", 
                String::from_utf8_lossy(&get_tx_cmd.stderr)));
        }

        let tx_data: serde_json::Value = serde_json::from_slice(&get_tx_cmd.stdout)?;
        
        // Find OP_RETURN output
        let vout = tx_data["vout"].as_array()
            .ok_or_else(|| anyhow::anyhow!("No outputs in transaction"))?;

        for output in vout {
            if let Some(script_type) = output["scriptPubKey"]["type"].as_str() {
                if script_type == "nulldata" {
                    // Found OP_RETURN output
                    let hex_data = output["scriptPubKey"]["hex"].as_str()
                        .ok_or_else(|| anyhow::anyhow!("No hex in OP_RETURN output"))?;
                    
                    // Decode hex and remove OP_RETURN prefix (0x6a + length byte)
                    let decoded = hex::decode(hex_data)?;
                    if decoded.len() > 2 && decoded[0] == 0x6a {
                        let data_len = decoded[1] as usize;
                        if decoded.len() >= 2 + data_len {
                            let op_return_data = &decoded[2..2+data_len];
                            return OptionAnchorData::decode(op_return_data);
                        }
                    }
                }
            }
        }

        Err(anyhow::anyhow!("No OP_RETURN output found in transaction"))
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_option_anchor_encoding() {
        let anchor = OptionAnchorData {
            option_type: 0, // Call
            strike_price: 50000_00, // $50,000
            expiry: 1735689600, // 2025-01-01
        };

        let encoded = anchor.encode();
        let decoded = OptionAnchorData::decode(&encoded).unwrap();

        assert_eq!(decoded.option_type, anchor.option_type);
        assert_eq!(decoded.strike_price, anchor.strike_price);
        assert_eq!(decoded.expiry, anchor.expiry);
    }

    #[test]
    fn test_data_size_limit() {
        let anchor = OptionAnchorData {
            option_type: 1, // Put
            strike_price: 999999999999, // Large number
            expiry: 9999999999,
        };

        let encoded = anchor.encode();
        assert!(encoded.len() <= 80, "Encoded data exceeds OP_RETURN limit");
    }
}