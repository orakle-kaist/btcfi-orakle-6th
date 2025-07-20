//! BitVMX Protocol Client
//! 
//! Client for communicating with the BitVMX Python protocol service.
//! This handles the complete fraud-proof protocol for option settlement.

use serde::{Deserialize, Serialize};
use reqwest::Client;
use std::collections::HashMap;
use crate::error::{BitVMXError, Result};

/// BitVMX Protocol Client
pub struct BitVMXProtocolClient {
    /// HTTP client for API calls
    client: Client,
    
    /// Prover service URL
    prover_url: String,
    
    /// Verifier service URL  
    verifier_url: String,
    
    /// Current protocol session ID
    session_id: Option<String>,
}

/// Setup request for initializing BitVMX protocol
#[derive(Debug, Serialize)]
pub struct SetupRequest {
    /// Prover's Bitcoin public key
    pub prover_public_key: String,
    
    /// Verifier's Bitcoin public key
    pub verifier_public_key: String,
    
    /// RISC-V program ELF file name
    pub program_elf: String,
    
    /// Maximum number of execution steps
    pub max_steps: u64,
    
    /// Funding amount in satoshis
    pub funding_amount: u64,
    
    /// Option-specific parameters
    pub option_params: OptionParameters,
}

/// Option parameters for settlement
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct OptionParameters {
    pub option_id: String,
    pub strike_price: u64,      // USD * 1e8
    pub option_type: String,    // "CALL" or "PUT"
    pub expiry_timestamp: u64,
    pub max_payout: u64,        // satoshis
}

/// Settlement input data
#[derive(Debug, Serialize)]
pub struct SettlementInput {
    pub oracle_price: u64,      // USD * 1e8
    pub strike_price: u64,      // USD * 1e8
    pub option_type: u64,       // 1=CALL, 2=PUT
    pub expiry_timestamp: u64,
    pub current_timestamp: u64,
    pub max_payout: u64,
    pub oracle_count: u64,
    pub oracle_signatures: Vec<u8>,
}

/// Setup response from BitVMX protocol
#[derive(Debug, Deserialize)]
pub struct SetupResponse {
    pub session_id: String,
    pub status: String,
    pub message: Option<String>,
    pub transactions: Option<PreSignedTransactions>,
}

/// Pre-signed transaction chain
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PreSignedTransactions {
    pub funding_tx: String,
    pub hash_result_tx: String,
    pub trigger_protocol_tx: String,
    pub search_txs: Vec<String>,
    pub trace_txs: Vec<String>,
    pub challenge_txs: HashMap<String, String>,
}

/// Input setting response
#[derive(Debug, Deserialize)]
pub struct InputResponse {
    pub status: String,
    pub input_hash: Option<String>,
    pub execution_result: Option<ExecutionResult>,
}

/// Execution result from RISC-V program
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ExecutionResult {
    pub payout_amount: u64,
    pub intrinsic_value: u64,
    pub is_exercisable: bool,
    pub error_code: u64,
    pub execution_trace_hash: String,
}

/// Next step response
#[derive(Debug, Deserialize)]
pub struct NextStepResponse {
    pub status: String,
    pub step_type: String,
    pub message: Option<String>,
    pub transaction_id: Option<String>,
    pub is_complete: bool,
}

impl BitVMXProtocolClient {
    /// Create new BitVMX protocol client
    pub fn new(prover_url: String, verifier_url: String) -> Self {
        Self {
            client: Client::new(),
            prover_url,
            verifier_url,
            session_id: None,
        }
    }
    
    /// Initialize BitVMX protocol setup
    pub async fn setup_protocol(&mut self, setup: SetupRequest) -> Result<PreSignedTransactions> {
        tracing::info!(
            "Setting up BitVMX protocol for option: {}",
            setup.option_params.option_id
        );
        
        // Step 1: Initialize prover
        let prover_setup: SetupResponse = self.call_prover_api("/api/v1/setup/fund/", &setup).await?;
        
        // Step 2: Initialize verifier  
        let _verifier_setup: SetupResponse = self.call_verifier_api("/api/v1/setup/fund/", &setup).await?;
        
        // Step 3: Get session ID
        self.session_id = Some(prover_setup.session_id.clone());
        
        // Step 4: Return pre-signed transactions
        prover_setup.transactions.ok_or_else(|| {
            BitVMXError::ProverError("No transactions in setup response".to_string())
        })
    }
    
    /// Execute settlement with oracle data
    pub async fn execute_settlement(
        &self,
        settlement_input: SettlementInput,
    ) -> Result<ExecutionResult> {
        tracing::info!("Executing BitVMX settlement with oracle price: {}", settlement_input.oracle_price);
        
        // Step 1: Set input data
        let input_data = self.serialize_settlement_input(&settlement_input)?;
        let input_response = self.set_input(input_data).await?;
        
        // Step 2: Execute the program
        let execution_result = input_response.execution_result.ok_or_else(|| {
            BitVMXError::ProverError("No execution result from input".to_string())
        })?;
        
        tracing::info!(
            "Settlement executed: payout={} sats, exercisable={}",
            execution_result.payout_amount,
            execution_result.is_exercisable
        );
        
        Ok(execution_result)
    }
    
    /// Start the verification protocol (if disputed)
    pub async fn start_verification(&self) -> Result<String> {
        tracing::info!("Starting BitVMX verification protocol");
        
        let response = self.call_prover_api::<(), NextStepResponse>("/api/v1/next_step", &()).await?;
        
        if response.step_type != "trigger_protocol" {
            return Err(BitVMXError::ProverError(
                format!("Expected trigger_protocol, got: {}", response.step_type)
            ));
        }
        
        response.transaction_id.ok_or_else(|| {
            BitVMXError::ProverError("No transaction ID in verification response".to_string())
        })
    }
    
    /// Handle challenge from verifier
    pub async fn handle_challenge(&self, challenge_type: &str) -> Result<String> {
        tracing::info!("Handling BitVMX challenge: {}", challenge_type);
        
        let challenge_data = HashMap::from([("challenge_type", challenge_type)]);
        let response = self.call_prover_api::<HashMap<&str, &str>, NextStepResponse>(
            "/api/v1/next_step", 
            &challenge_data
        ).await?;
        
        response.transaction_id.ok_or_else(|| {
            BitVMXError::ProverError("No transaction ID in challenge response".to_string())
        })
    }
    
    /// Get protocol status
    pub async fn get_status(&self) -> Result<ProtocolStatus> {
        let response = self.call_prover_api::<(), StatusResponse>("/api/v1/status", &()).await?;
        
        Ok(ProtocolStatus {
            session_id: self.session_id.clone(),
            current_step: response.current_step,
            is_complete: response.is_complete,
            winner: response.winner,
            final_result: response.final_result,
        })
    }
    
    // Helper methods
    
    async fn call_prover_api<T: Serialize, R: for<'de> Deserialize<'de>>(
        &self,
        endpoint: &str,
        payload: &T,
    ) -> Result<R> {
        let url = format!("{}{}", self.prover_url, endpoint);
        
        let response = self.client
            .post(&url)
            .json(payload)
            .send()
            .await?;
            
        if !response.status().is_success() {
            return Err(BitVMXError::NetworkError(
                format!("API call failed: {}", response.status())
            ));
        }
        
        let result = response.json::<R>().await?;
        Ok(result)
    }
    
    async fn call_verifier_api<T: Serialize, R: for<'de> Deserialize<'de>>(
        &self,
        endpoint: &str,
        payload: &T,
    ) -> Result<R> {
        let url = format!("{}{}", self.verifier_url, endpoint);
        
        let response = self.client
            .post(&url)
            .json(payload)
            .send()
            .await?;
            
        if !response.status().is_success() {
            return Err(BitVMXError::NetworkError(
                format!("Verifier API call failed: {}", response.status())
            ));
        }
        
        let result = response.json::<R>().await?;
        Ok(result)
    }
    
    async fn set_input(&self, input_data: Vec<u8>) -> Result<InputResponse> {
        let payload = HashMap::from([
            ("input", hex::encode(&input_data))
        ]);
        
        self.call_prover_api("/api/v1/input", &payload).await
    }
    
    fn serialize_settlement_input(&self, input: &SettlementInput) -> Result<Vec<u8>> {
        // Convert SettlementInput to binary format expected by option verification program
        // Must match the VerificationHeader and data structs in option_verification_program/src/main.rs
        let mut data = Vec::new();
        
        // VerificationHeader (16 bytes)
        data.push(2u8); // verification_type: Settlement = 2
        data.push(if input.option_type == 1 { 0 } else { 1 }); // option_type: 0=Call, 1=Put
        data.extend_from_slice(&[0u8; 14]); // _padding
        
        // SettlementData (64 bytes) - legacy format for compatibility
        data.extend_from_slice(&input.strike_price.to_be_bytes()); // strike_price (big endian)
        data.extend_from_slice(&input.expiry_timestamp.to_be_bytes()); // expiry_timestamp
        data.extend_from_slice(&100000u64.to_be_bytes()); // premium_paid (placeholder)
        data.extend_from_slice(&[0u8; 20]); // buyer_address (placeholder)
        data.extend_from_slice(&[0u8; 12]); // padding to reach 64 bytes
        
        // OracleData (256 bytes) - same format as before
        data.extend_from_slice(&input.oracle_price.to_be_bytes()); // btc_price (big endian)
        data.extend_from_slice(&input.current_timestamp.to_be_bytes()); // timestamp
        data.push(input.oracle_count as u8); // consensus_count
        data.extend_from_slice(&[0u8; 7]); // padding1
        
        // Oracle signatures (3 * 64 = 192 bytes)
        let mut signatures = input.oracle_signatures.clone();
        signatures.resize(192, 0); // Resize to exactly 192 bytes for 3 signatures
        data.extend_from_slice(&signatures);
        
        // Padding to complete OracleData to 256 bytes
        data.extend_from_slice(&[0u8; 40]); // padding2
        
        // Ensure total input is exactly 336 bytes (16 + 64 + 256)
        data.resize(336, 0);
        
        Ok(data)
    }
}

/// Protocol status
#[derive(Debug)]
pub struct ProtocolStatus {
    pub session_id: Option<String>,
    pub current_step: String,
    pub is_complete: bool,
    pub winner: Option<String>,
    pub final_result: Option<ExecutionResult>,
}

/// Status response
#[derive(Debug, Deserialize)]
struct StatusResponse {
    current_step: String,
    is_complete: bool,
    winner: Option<String>,
    final_result: Option<ExecutionResult>,
}

/// BitVMX Protocol Manager - High-level interface
pub struct BitVMXProtocolManager {
    /// Protocol client
    client: BitVMXProtocolClient,
    
    /// Current protocol sessions
    sessions: HashMap<String, ProtocolSession>,
}

/// Protocol session for an option
#[derive(Debug)]
pub struct ProtocolSession {
    pub option_id: String,
    pub session_id: String,
    pub pre_signed_txs: PreSignedTransactions,
    pub status: SessionStatus,
}

#[derive(Debug)]
pub enum SessionStatus {
    Setup,
    InputSet,
    Executing,
    Challenging,
    Complete(ExecutionResult),
    Failed(String),
}

impl BitVMXProtocolManager {
    /// Create new protocol manager
    pub fn new() -> Self {
        Self {
            client: BitVMXProtocolClient::new(
                "http://localhost:8000".to_string(), // Prover
                "http://localhost:8001".to_string(), // Verifier
            ),
            sessions: HashMap::new(),
        }
    }
    
    /// Create pre-signed settlement for option purchase
    pub async fn create_presigned_settlement(
        &mut self,
        option_id: String,
        option_params: OptionParameters,
        prover_pubkey: String,
        verifier_pubkey: String,
    ) -> Result<PreSignedTransactions> {
        tracing::info!("Creating pre-signed settlement for option: {}", option_id);
        
        let setup = SetupRequest {
            prover_public_key: prover_pubkey,
            verifier_public_key: verifier_pubkey,
            program_elf: "option-verification-program".to_string(), // Compiled from /option_verification_program
            max_steps: 1000000,
            funding_amount: option_params.max_payout,
            option_params: option_params.clone(),
        };
        
        let pre_signed_txs = self.client.setup_protocol(setup).await?;
        
        // Store session
        let session = ProtocolSession {
            option_id: option_id.clone(),
            session_id: self.client.session_id.clone().unwrap(),
            pre_signed_txs: pre_signed_txs.clone(),
            status: SessionStatus::Setup,
        };
        
        self.sessions.insert(option_id, session);
        
        Ok(pre_signed_txs)
    }
    
    /// Execute option settlement
    pub async fn execute_option_settlement(
        &mut self,
        option_id: String,
        oracle_price: u64,
        oracle_signatures: Vec<u8>,
    ) -> Result<ExecutionResult> {
        let session = self.sessions.get_mut(&option_id).ok_or_else(|| {
            BitVMXError::ProverError(format!("No session found for option: {}", option_id))
        })?;
        
        // Get option parameters from session
        let option_params = match &session.pre_signed_txs {
            txs => {
                // In real implementation, extract from pre-signed transactions
                OptionParameters {
                    option_id: option_id.clone(),
                    strike_price: 5200000000000u64, // Placeholder
                    option_type: "CALL".to_string(),
                    expiry_timestamp: chrono::Utc::now().timestamp() as u64,
                    max_payout: 100000000u64,
                }
            }
        };
        
        let settlement_input = SettlementInput {
            oracle_price,
            strike_price: option_params.strike_price,
            option_type: if option_params.option_type == "CALL" { 1 } else { 2 },
            expiry_timestamp: option_params.expiry_timestamp,
            current_timestamp: chrono::Utc::now().timestamp() as u64,
            max_payout: option_params.max_payout,
            oracle_count: 3, // Assuming 3 oracles
            oracle_signatures,
        };
        
        let result = self.client.execute_settlement(settlement_input).await?;
        
        // Update session status
        session.status = SessionStatus::Complete(result.clone());
        
        Ok(result)
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    
    #[tokio::test]
    async fn test_bitvmx_protocol_client() {
        // This test would require running BitVMX services
        // For now, just test the data structures
        
        let option_params = OptionParameters {
            option_id: "BTC_CALL_52K_7D".to_string(),
            strike_price: 5200000000000u64,
            option_type: "CALL".to_string(),
            expiry_timestamp: 1640995200,
            max_payout: 100000000u64,
        };
        
        assert_eq!(option_params.option_id, "BTC_CALL_52K_7D");
        assert_eq!(option_params.option_type, "CALL");
    }
}