//! Configuration for Bitcoin Committer

use serde::{Deserialize, Serialize};
use std::env;

/// Configuration for Bitcoin L1 committer
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CommitterConfig {
    /// Bitcoin network (mainnet, testnet, regtest)
    pub bitcoin_network: String,
    
    /// Bitcoin RPC endpoint
    pub bitcoin_rpc_url: String,
    
    /// Bitcoin RPC username
    pub bitcoin_rpc_user: String,
    
    /// Bitcoin RPC password
    pub bitcoin_rpc_password: String,
    
    /// Wallet name for transactions
    pub wallet_name: String,
    
    /// Fee rate in sats/vbyte
    pub fee_rate: u64,
    
    /// Maximum OP_RETURN data size (bytes)
    pub max_op_return_size: usize,
    
    /// Queue polling interval (seconds)
    pub polling_interval_secs: u64,
    
    /// Maximum transactions per batch
    pub max_batch_size: usize,
    
    /// Option transaction queue endpoint
    pub transaction_queue_url: String,
}

impl CommitterConfig {
    /// Load configuration from environment variables or defaults
    pub fn load() -> Result<Self, Box<dyn std::error::Error>> {
        Ok(Self {
            bitcoin_network: env::var("BITCOIN_NETWORK")
                .unwrap_or_else(|_| "regtest".to_string()),
            
            bitcoin_rpc_url: env::var("BITCOIN_RPC_URL")
                .unwrap_or_else(|_| "http://localhost:18443".to_string()),
            
            bitcoin_rpc_user: env::var("BITCOIN_RPC_USER")
                .unwrap_or_else(|_| "bitcoin".to_string()),
            
            bitcoin_rpc_password: env::var("BITCOIN_RPC_PASSWORD")
                .unwrap_or_else(|_| "password".to_string()),
            
            wallet_name: env::var("BITCOIN_WALLET_NAME")
                .unwrap_or_else(|_| "committer".to_string()),
            
            fee_rate: env::var("BITCOIN_FEE_RATE")
                .unwrap_or_else(|_| "10".to_string())
                .parse()
                .unwrap_or(10),
            
            max_op_return_size: env::var("MAX_OP_RETURN_SIZE")
                .unwrap_or_else(|_| "80".to_string())
                .parse()
                .unwrap_or(80),
            
            polling_interval_secs: env::var("POLLING_INTERVAL_SECS")
                .unwrap_or_else(|_| "30".to_string())
                .parse()
                .unwrap_or(30),
            
            max_batch_size: env::var("MAX_BATCH_SIZE")
                .unwrap_or_else(|_| "10".to_string())
                .parse()
                .unwrap_or(10),
            
            transaction_queue_url: env::var("TRANSACTION_QUEUE_URL")
                .unwrap_or_else(|_| "http://localhost:8080/api/v1/transactions/pending".to_string()),
        })
    }
    
    /// Validate configuration
    pub fn validate(&self) -> Result<(), String> {
        if self.max_op_return_size > 80 {
            return Err("OP_RETURN size cannot exceed 80 bytes".to_string());
        }
        
        if self.fee_rate == 0 {
            return Err("Fee rate must be greater than 0".to_string());
        }
        
        if !["mainnet", "testnet", "regtest"].contains(&self.bitcoin_network.as_str()) {
            return Err("Invalid Bitcoin network".to_string());
        }
        
        Ok(())
    }
}

impl Default for CommitterConfig {
    fn default() -> Self {
        Self {
            bitcoin_network: "regtest".to_string(),
            bitcoin_rpc_url: "http://localhost:18443".to_string(),
            bitcoin_rpc_user: "bitcoin".to_string(),
            bitcoin_rpc_password: "password".to_string(),
            wallet_name: "committer".to_string(),
            fee_rate: 10,
            max_op_return_size: 80,
            polling_interval_secs: 30,
            max_batch_size: 10,
            transaction_queue_url: "http://localhost:8080/api/v1/transactions/pending".to_string(),
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_default_config() {
        let config = CommitterConfig::default();
        assert_eq!(config.bitcoin_network, "regtest");
        assert_eq!(config.max_op_return_size, 80);
        assert!(config.validate().is_ok());
    }

    #[test]
    fn test_config_validation() {
        let mut config = CommitterConfig::default();
        
        // Test invalid OP_RETURN size
        config.max_op_return_size = 100;
        assert!(config.validate().is_err());
        
        // Test invalid fee rate
        config.max_op_return_size = 80;
        config.fee_rate = 0;
        assert!(config.validate().is_err());
        
        // Test invalid network
        config.fee_rate = 10;
        config.bitcoin_network = "invalid".to_string();
        assert!(config.validate().is_err());
        
        // Test valid config
        config.bitcoin_network = "testnet".to_string();
        assert!(config.validate().is_ok());
    }
}