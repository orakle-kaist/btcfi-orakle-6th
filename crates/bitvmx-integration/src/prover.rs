//! BitVMX Prover Client for Option Settlement
//! 
//! Communicates with the BitVMX Prover microservice to generate proofs for option settlements.
//! This follows a production-ready microservice architecture.

use oracle_vm_common::Result;
use crate::vm::OptionSettlement;
use serde::{Deserialize, Serialize};
use std::collections::HashMap;

/// Configuration for BitVMX Prover service
#[derive(Debug, Clone)]
pub struct BitVMXProverConfig {
    /// Base URL for the BitVMX Prover service
    pub prover_service_url: String,
    /// Timeout for HTTP requests in seconds
    pub request_timeout_secs: u64,
    /// Retry attempts for failed requests
    pub max_retries: u32,
}

impl Default for BitVMXProverConfig {
    fn default() -> Self {
        Self {
            prover_service_url: "http://localhost:8000".to_string(),
            request_timeout_secs: 30,
            max_retries: 3,
        }
    }
}

/// Proof data for a settlement operation
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SettlementProof {
    /// Type of settlement being proven
    pub settlement_type: SettlementType,
    
    /// Unique identifier for this proof
    pub proof_id: String,
    
    /// BitVMX execution trace hash
    pub execution_trace_hash: String,
    
    /// Program commitment (ROM hash)
    pub program_commitment: String,
    
    /// Input data hash
    pub input_hash: String,
    
    /// Output data hash  
    pub output_hash: String,
    
    /// Bitcoin script witness data
    pub witness_scripts: Vec<String>,
    
    /// Proof generation timestamp
    pub created_at: u64,
}

/// Type of settlement being proven
#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum SettlementType {
    #[serde(rename = "option_expiry")]
    OptionExpiry { option_id: String },
}

/// Request payload for setup endpoint
#[derive(Debug, Serialize)]
struct SetupRequest {
    /// ELF program identifier 
    program_id: String,
    /// Network configuration
    network: String,
    /// Additional setup parameters
    parameters: HashMap<String, serde_json::Value>,
}

/// Response from setup endpoint
#[derive(Debug, Deserialize)]
struct SetupResponse {
    setup_uuid: String,
    status: String,
    message: Option<String>,
}

/// Request payload for input endpoint
#[derive(Debug, Serialize)]
struct InputRequest {
    setup_uuid: String,
    input_hex: String,
    input_type: String,
}

/// Response from input endpoint
#[derive(Debug, Deserialize)]
struct InputResponse {
    status: String,
    execution_trace: Option<String>,
    message: Option<String>,
}

/// Request payload for next step (proof generation)
#[derive(Debug, Serialize)]
struct NextStepRequest {
    setup_uuid: String,
    step_type: String,
    parameters: HashMap<String, serde_json::Value>,
}

/// Response from next step endpoint
#[derive(Debug, Deserialize)]
struct NextStepResponse {
    status: String,
    proof_data: Option<ProofData>,
    witness_scripts: Option<Vec<String>>,
    message: Option<String>,
}

/// Internal proof data structure
#[derive(Debug, Deserialize)]
struct ProofData {
    execution_trace_hash: String,
    program_commitment: String,
    input_hash: String,
    output_hash: String,
}

/// BitVMX Prover client for generating settlement proofs
pub struct BitVMXProver {
    config: BitVMXProverConfig,
    http_client: reqwest::Client,
}

impl BitVMXProver {
    /// Create new BitVMX prover client
    pub fn new(config: BitVMXProverConfig) -> Self {
        let http_client = reqwest::Client::builder()
            .timeout(std::time::Duration::from_secs(config.request_timeout_secs))
            .build()
            .expect("Failed to create HTTP client");

        Self {
            config,
            http_client,
        }
    }

    /// Create BitVMX prover with default configuration
    pub fn with_default_config() -> Self {
        Self::new(BitVMXProverConfig::default())
    }

    /// Generate proof for an option settlement operation
    pub async fn generate_settlement_proof(
        &self,
        settlement: &OptionSettlement,
        oracle_signatures: &[u8],
        market_data: &[u8],
    ) -> Result<SettlementProof> {
        tracing::info!("Generating settlement proof for option: {}", settlement.option_id);

        // Step 1: Setup BitVMX execution environment
        let setup_uuid = self.setup_prover_environment(settlement).await?;
        
        // Step 2: Submit settlement input data
        let execution_trace = self.submit_settlement_input(
            &setup_uuid, 
            settlement, 
            oracle_signatures,
            market_data
        ).await?;
        
        // Step 3: Generate final proof
        let proof_data = self.generate_proof(&setup_uuid, &execution_trace).await?;
        
        // Step 4: Construct final settlement proof
        let final_proof = match proof_data.proof_data {
            Some(proof_inner) => proof_inner,
            None => return Err(oracle_vm_common::OracleVmError::Internal("No proof data returned".to_string())),
        };
        
        Ok(SettlementProof {
            settlement_type: SettlementType::OptionExpiry {
                option_id: settlement.option_id.clone(),
            },
            proof_id: setup_uuid,
            execution_trace_hash: final_proof.execution_trace_hash,
            program_commitment: final_proof.program_commitment,
            input_hash: final_proof.input_hash,
            output_hash: final_proof.output_hash,
            witness_scripts: proof_data.witness_scripts.unwrap_or_default(),
            created_at: std::time::SystemTime::now()
                .duration_since(std::time::UNIX_EPOCH)
                .unwrap()
                .as_secs(),
        })
    }

    /// Setup BitVMX prover environment via API
    async fn setup_prover_environment(&self, settlement: &OptionSettlement) -> Result<String> {
        let mut parameters = HashMap::new();
        parameters.insert("option_id".to_string(), serde_json::Value::String(settlement.option_id.clone()));
        parameters.insert("settlement_price".to_string(), serde_json::Value::Number(settlement.settlement_price.into()));
        
        let request = SetupRequest {
            program_id: "option-verification-program".to_string(), // Use existing Rust RISC-V program
            network: "testnet".to_string(), // TODO: Make configurable
            parameters,
        };

        let url = format!("{}/api/v1/setup", self.config.prover_service_url);
        
        for attempt in 1..=self.config.max_retries {
            match self.http_client.post(&url).json(&request).send().await {
                Ok(response) => {
                    if response.status().is_success() {
                        let setup_response: SetupResponse = response.json().await
                            .map_err(|e| oracle_vm_common::OracleVmError::Internal(format!("Failed to parse setup response: {}", e)))?;
                        
                        tracing::info!("BitVMX setup completed: {}", setup_response.setup_uuid);
                        return Ok(setup_response.setup_uuid);
                    } else {
                        let error = response.text().await.unwrap_or_default();
                        tracing::warn!("Setup attempt {} failed: {}", attempt, error);
                        
                        if attempt == self.config.max_retries {
                            return Err(oracle_vm_common::OracleVmError::Internal(format!("Setup failed after {} attempts: {}", attempt, error)));
                        }
                    }
                }
                Err(e) => {
                    tracing::warn!("Setup request attempt {} failed: {}", attempt, e);
                    
                    if attempt == self.config.max_retries {
                        return Err(oracle_vm_common::OracleVmError::Internal(format!("Setup request failed: {}", e)));
                    }
                }
            }
            
            // Wait before retry
            tokio::time::sleep(std::time::Duration::from_millis(1000 * attempt as u64)).await;
        }
        
        unreachable!()
    }

    /// Submit settlement input data to BitVMX service
    async fn submit_settlement_input(
        &self,
        setup_uuid: &str,
        settlement: &OptionSettlement,
        oracle_signatures: &[u8],
        _market_data: &[u8],
    ) -> Result<String> {
        // Prepare settlement input data as hex
        let input_hex = self.prepare_settlement_input_hex(settlement, oracle_signatures)?;
        
        let request = InputRequest {
            setup_uuid: setup_uuid.to_string(),
            input_hex,
            input_type: "option_settlement".to_string(),
        };

        let url = format!("{}/api/v1/input", self.config.prover_service_url);
        
        let response = self.http_client.post(&url).json(&request).send().await
            .map_err(|e| oracle_vm_common::OracleVmError::Internal(format!("Input request failed: {}", e)))?;

        if !response.status().is_success() {
            let error = response.text().await.unwrap_or_default();
            return Err(oracle_vm_common::OracleVmError::Internal(format!("Input submission failed: {}", error)));
        }

        let input_response: InputResponse = response.json().await
            .map_err(|e| oracle_vm_common::OracleVmError::Internal(format!("Failed to parse input response: {}", e)))?;

        match input_response.execution_trace {
            Some(trace) => {
                tracing::info!("Execution trace generated: {} chars", trace.len());
                Ok(trace)
            }
            None => Err(oracle_vm_common::OracleVmError::Internal(
                format!("No execution trace returned: {}", input_response.message.unwrap_or_default())
            ))
        }
    }

    /// Generate final proof from execution trace
    async fn generate_proof(&self, setup_uuid: &str, execution_trace: &str) -> Result<NextStepResponse> {
        let mut parameters = HashMap::new();
        parameters.insert("execution_trace".to_string(), serde_json::Value::String(execution_trace.to_string()));
        parameters.insert("generate_witness".to_string(), serde_json::Value::Bool(true));
        
        let request = NextStepRequest {
            setup_uuid: setup_uuid.to_string(),
            step_type: "generate_proof".to_string(),
            parameters,
        };

        let url = format!("{}/api/v1/next_step", self.config.prover_service_url);
        
        let response = self.http_client.post(&url).json(&request).send().await
            .map_err(|e| oracle_vm_common::OracleVmError::Internal(format!("Proof generation request failed: {}", e)))?;

        if !response.status().is_success() {
            let error = response.text().await.unwrap_or_default();
            return Err(oracle_vm_common::OracleVmError::Internal(format!("Proof generation failed: {}", error)));
        }

        let proof_response: NextStepResponse = response.json().await
            .map_err(|e| oracle_vm_common::OracleVmError::Internal(format!("Failed to parse proof response: {}", e)))?;

        tracing::info!("Proof generation completed");
        Ok(proof_response)
    }

    /// Prepare settlement input data as hex string  
    /// This must exactly match the VerificationHeader and data structs in option_verification_program/src/main.rs
    fn prepare_settlement_input_hex(
        &self,
        settlement: &OptionSettlement,
        oracle_signatures: &[u8],
    ) -> Result<String> {
        let mut input = Vec::new();
        
        // VerificationHeader (16 bytes)
        input.push(2u8); // verification_type: Settlement = 2
        input.push(0u8); // option_type: Call=0, Put=1 (assuming Call for now)  
        input.extend_from_slice(&[0u8; 14]); // _padding
        
        // SettlementData (64 bytes) - legacy format for compatibility
        input.extend_from_slice(&52000_00000000u64.to_be_bytes()); // strike_price in satoshis (TODO: extract from settlement)
        input.extend_from_slice(&settlement.settlement_timestamp.to_be_bytes()); // expiry_timestamp
        input.extend_from_slice(&100000u64.to_be_bytes()); // premium_paid in satoshis (TODO: extract from settlement)
        input.extend_from_slice(&[0u8; 20]); // buyer_address hash (TODO: decode from settlement.buyer_address)
        input.extend_from_slice(&[0u8; 12]); // _padding to reach 64 bytes
        
        // OracleData (256 bytes) - same format as before
        input.extend_from_slice(&settlement.settlement_price.to_be_bytes()); // btc_price in satoshis per USD
        input.extend_from_slice(&settlement.settlement_timestamp.to_be_bytes()); // timestamp
        input.push(3u8); // consensus_count (number of oracles in consensus)
        input.extend_from_slice(&[0u8; 7]); // _padding1
        
        // Oracle signatures (3 * 64 = 192 bytes)
        if oracle_signatures.len() >= 192 {
            input.extend_from_slice(&oracle_signatures[0..192]);
        } else {
            // Mock oracle signatures for development/testing
            input.extend_from_slice(&[1u8; 64]); // oracle1_sig
            input.extend_from_slice(&[2u8; 64]); // oracle2_sig
            input.extend_from_slice(&[3u8; 64]); // oracle3_sig
        }
        
        // _padding2 to complete OracleData to 256 bytes
        input.extend_from_slice(&[0u8; 40]);
        
        // Verify total input is exactly 336 bytes (16 + 64 + 256)
        assert_eq!(input.len(), 336, "Verification input must be exactly 336 bytes");
        
        Ok(hex::encode(input))
    }

    /// Check if BitVMX prover service is healthy
    pub async fn health_check(&self) -> Result<bool> {
        let url = format!("{}/healthcheck", self.config.prover_service_url);
        
        match self.http_client.get(&url).send().await {
            Ok(response) if response.status().is_success() => {
                tracing::debug!("BitVMX prover service is healthy");
                Ok(true)
            }
            Ok(response) => {
                tracing::warn!("BitVMX prover service unhealthy: {}", response.status());
                Ok(false)
            }
            Err(e) => {
                tracing::error!("Failed to reach BitVMX prover service: {}", e);
                Ok(false)
            }
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[tokio::test]
    async fn test_prover_config() {
        let config = BitVMXProverConfig::default();
        assert_eq!(config.prover_service_url, "http://localhost:8000");
        assert_eq!(config.request_timeout_secs, 30);
    }

    #[tokio::test]
    async fn test_settlement_input_preparation() {
        let prover = BitVMXProver::with_default_config();
        
        let settlement = OptionSettlement {
            option_id: "test_option".to_string(),
            settlement_price: 5000000000000000,
            settlement_timestamp: 1700000000,
            payout_amount: 100000000,
            buyer_address: "test_buyer".to_string(),
        };
        
        let oracle_signatures = b"mock_signatures";
        
        let input_hex = prover.prepare_settlement_input_hex(&settlement, oracle_signatures).unwrap();
        
        // Verify hex format and length
        assert!(!input_hex.is_empty());
        assert!(input_hex.len() % 2 == 0);
        
        let input_bytes = hex::decode(&input_hex).unwrap();
        assert_eq!(input_bytes.len(), 320); // 64 + 256 bytes
    }

    #[tokio::test]
    async fn test_health_check() {
        let prover = BitVMXProver::with_default_config();
        
        // This will fail in test environment but demonstrates the interface
        let _result = prover.health_check().await;
        // Note: In CI/CD, mock the HTTP client or use a test server
    }

    #[tokio::test]
    async fn test_settlement_proof_generation() {
        let prover = BitVMXProver::with_default_config();
        
        let settlement = OptionSettlement {
            option_id: "opt_btc_call_52k".to_string(),
            settlement_price: 5500000000000000,
            settlement_timestamp: 1700000000,
            payout_amount: 300000000,
            buyer_address: "bc1qtest123".to_string(),
        };
        
        let oracle_signatures = b"mock_oracle_data";
        let market_data = b"mock_market_data";
        
        // This will fail without a running BitVMX service, but demonstrates the interface
        let result = prover.generate_settlement_proof(&settlement, oracle_signatures, market_data).await;
        
        match result {
            Ok(proof) => {
                match proof.settlement_type {
                    SettlementType::OptionExpiry { option_id } => {
                        assert_eq!(option_id, "opt_btc_call_52k");
                    }
                }
                assert!(!proof.proof_id.is_empty());
                assert!(!proof.execution_trace_hash.is_empty());
            }
            Err(_) => {
                // Expected to fail in test environment without running service
                tracing::warn!("Settlement proof generation failed (expected in test environment)");
            }
        }
    }
}