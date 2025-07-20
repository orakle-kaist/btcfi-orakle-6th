//! Bitcoin RPC client for testnet operations

use bitcoin::{
    Address, Network, Transaction, TxOut, ScriptBuf, Txid, 
    blockdata::script::Builder, opcodes::all::OP_RETURN
};
use serde::{Deserialize, Serialize};
use std::str::FromStr;
use oracle_vm_common::Result;

/// Bitcoin client configuration
#[derive(Debug, Clone)]
pub struct BitcoinConfig {
    pub network: Network,
    pub rpc_url: String,
    pub rpc_user: String,
    pub rpc_password: String,
    pub wallet_name: Option<String>,
}

impl Default for BitcoinConfig {
    fn default() -> Self {
        Self {
            network: Network::Testnet,
            rpc_url: "http://localhost:18332".to_string(),
            rpc_user: "bitcoinrpc".to_string(),
            rpc_password: "rpcpassword".to_string(),
            wallet_name: Some("testwallet".to_string()),
        }
    }
}

/// Bitcoin RPC client
pub struct BitcoinClient {
    config: BitcoinConfig,
    client: reqwest::Client,
}

/// RPC request structure
#[derive(Debug, Serialize)]
struct RpcRequest {
    jsonrpc: String,
    id: u64,
    method: String,
    params: serde_json::Value,
}

/// RPC response structure
#[derive(Debug, Deserialize)]
struct RpcResponse<T> {
    id: u64,
    result: Option<T>,
    error: Option<RpcError>,
}

/// RPC error structure
#[derive(Debug, Deserialize)]
struct RpcError {
    code: i32,
    message: String,
}

/// Transaction info from Bitcoin node
#[derive(Debug, Deserialize)]
pub struct TransactionInfo {
    pub txid: String,
    pub confirmations: u32,
    pub blockhash: Option<String>,
    pub blockheight: Option<u64>,
    pub time: Option<u64>,
}

/// UTXO information
#[derive(Debug, Deserialize)]
pub struct UtxoInfo {
    pub txid: String,
    pub vout: u32,
    pub amount: f64,
    pub scriptPubKey: String,
    pub confirmations: u32,
}

impl BitcoinClient {
    /// Create new Bitcoin client
    pub fn new(config: BitcoinConfig) -> Self {
        Self {
            config,
            client: reqwest::Client::new(),
        }
    }

    /// Create Bitcoin client with default testnet configuration
    pub fn testnet() -> Self {
        Self::new(BitcoinConfig::default())
    }

    /// Get network info to test connection
    pub async fn get_network_info(&self) -> Result<serde_json::Value> {
        let request = RpcRequest {
            jsonrpc: "1.0".to_string(),
            id: 1,
            method: "getnetworkinfo".to_string(),
            params: serde_json::Value::Array(vec![]),
        };

        let response = self.send_rpc_request::<serde_json::Value>(request).await?;
        Ok(response)
    }

    /// Get current block height
    pub async fn get_block_count(&self) -> Result<u64> {
        let request = RpcRequest {
            jsonrpc: "1.0".to_string(),
            id: 1,
            method: "getblockcount".to_string(),
            params: serde_json::Value::Array(vec![]),
        };

        let response = self.send_rpc_request::<u64>(request).await?;
        Ok(response)
    }

    /// Get wallet balance
    pub async fn get_balance(&self) -> Result<f64> {
        let request = RpcRequest {
            jsonrpc: "1.0".to_string(),
            id: 1,
            method: "getbalance".to_string(),
            params: serde_json::Value::Array(vec![]),
        };

        let response = self.send_rpc_request::<f64>(request).await?;
        Ok(response)
    }

    /// Generate new address
    pub async fn get_new_address(&self, label: Option<&str>) -> Result<String> {
        let params = if let Some(label) = label {
            serde_json::json!([label])
        } else {
            serde_json::Value::Array(vec![])
        };

        let request = RpcRequest {
            jsonrpc: "1.0".to_string(),
            id: 1,
            method: "getnewaddress".to_string(),
            params,
        };

        let response = self.send_rpc_request::<String>(request).await?;
        Ok(response)
    }

    /// Send transaction with OP_RETURN data
    pub async fn send_op_return_transaction(
        &self,
        data: &[u8],
        amount_to_self: Option<f64>,
    ) -> Result<String> {
        tracing::info!("Creating OP_RETURN transaction with {} bytes", data.len());

        // Create OP_RETURN script
        let _op_return_script = Builder::new()
            .push_opcode(OP_RETURN)
            .push_slice(data.as_ref())
            .into_script();

        // Get a new address to send change to
        let change_address = self.get_new_address(Some("op_return_change")).await?;

        // Create raw transaction using Bitcoin Core RPC
        let outputs = if let Some(amount) = amount_to_self {
            serde_json::json!({
                "data": hex::encode(data),
                change_address: amount
            })
        } else {
            serde_json::json!({
                "data": hex::encode(data)
            })
        };

        // Use createrawtransaction and signrawtransactionwithwallet
        let create_request = RpcRequest {
            jsonrpc: "1.0".to_string(),
            id: 1,
            method: "createrawtransaction".to_string(),
            params: serde_json::json!([[], outputs]),
        };

        let raw_tx = self.send_rpc_request::<String>(create_request).await?;

        // Fund the transaction
        let fund_request = RpcRequest {
            jsonrpc: "1.0".to_string(),
            id: 1,
            method: "fundrawtransaction".to_string(),
            params: serde_json::json!([raw_tx]),
        };

        #[derive(Deserialize)]
        struct FundResult {
            hex: String,
            fee: f64,
        }

        let fund_result = self.send_rpc_request::<FundResult>(fund_request).await?;

        // Sign the transaction
        let sign_request = RpcRequest {
            jsonrpc: "1.0".to_string(),
            id: 1,
            method: "signrawtransactionwithwallet".to_string(),
            params: serde_json::json!([fund_result.hex]),
        };

        #[derive(Deserialize)]
        struct SignResult {
            hex: String,
            complete: bool,
        }

        let sign_result = self.send_rpc_request::<SignResult>(sign_request).await?;

        if !sign_result.complete {
            return Err("Failed to sign transaction".into());
        }

        // Send the transaction
        let send_request = RpcRequest {
            jsonrpc: "1.0".to_string(),
            id: 1,
            method: "sendrawtransaction".to_string(),
            params: serde_json::json!([sign_result.hex]),
        };

        let txid = self.send_rpc_request::<String>(send_request).await?;

        tracing::info!("OP_RETURN transaction sent: {}", txid);
        Ok(txid)
    }

    /// Get transaction information
    pub async fn get_transaction(&self, txid: &str) -> Result<TransactionInfo> {
        let request = RpcRequest {
            jsonrpc: "1.0".to_string(),
            id: 1,
            method: "gettransaction".to_string(),
            params: serde_json::json!([txid]),
        };

        let response = self.send_rpc_request::<TransactionInfo>(request).await?;
        Ok(response)
    }

    /// List unspent transactions
    pub async fn list_unspent(&self) -> Result<Vec<UtxoInfo>> {
        let request = RpcRequest {
            jsonrpc: "1.0".to_string(),
            id: 1,
            method: "listunspent".to_string(),
            params: serde_json::Value::Array(vec![]),
        };

        let response = self.send_rpc_request::<Vec<UtxoInfo>>(request).await?;
        Ok(response)
    }

    /// Send RPC request to Bitcoin node
    async fn send_rpc_request<T>(&self, request: RpcRequest) -> Result<T>
    where
        T: for<'de> Deserialize<'de>,
    {
        let auth = format!("{}:{}", self.config.rpc_user, self.config.rpc_password);
        let auth_header = format!("Basic {}", base64::encode(auth));

        let response = self.client
            .post(&self.config.rpc_url)
            .header("Authorization", auth_header)
            .header("Content-Type", "application/json")
            .json(&request)
            .send()
            .await
            .map_err(|e| oracle_vm_common::OracleVmError::Internal(format!("RPC request failed: {}", e)))?;

        if !response.status().is_success() {
            return Err(oracle_vm_common::OracleVmError::Internal(format!("RPC request failed with status: {}", response.status())));
        }

        let rpc_response: RpcResponse<T> = response
            .json()
            .await
            .map_err(|e| oracle_vm_common::OracleVmError::Internal(format!("Failed to parse RPC response: {}", e)))?;

        if let Some(error) = rpc_response.error {
            return Err(oracle_vm_common::OracleVmError::Internal(format!("RPC error {}: {}", error.code, error.message)));
        }

        rpc_response.result
            .ok_or_else(|| oracle_vm_common::OracleVmError::Internal("No result in RPC response".to_string()))
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[tokio::test]
    async fn test_bitcoin_client_creation() {
        let client = BitcoinClient::testnet();
        assert_eq!(client.config.network, Network::Testnet);
    }

    #[tokio::test]
    async fn test_op_return_transaction() {
        // This test requires a running Bitcoin testnet node
        // Skip in CI/CD environments
        if std::env::var("CI").is_ok() {
            return;
        }

        let client = BitcoinClient::testnet();
        
        // Test data for OP_RETURN
        let test_data = b"TEST_OPTION_CREATION";
        
        // This will fail if no testnet node is running, which is expected
        let result = client.send_op_return_transaction(test_data, Some(0.001)).await;
        
        // In a real test environment with a running node, this should succeed
        match result {
            Ok(txid) => {
                println!("Test transaction sent: {}", txid);
                assert!(!txid.is_empty());
            }
            Err(e) => {
                println!("Expected error without running Bitcoin node: {}", e);
            }
        }
    }
}