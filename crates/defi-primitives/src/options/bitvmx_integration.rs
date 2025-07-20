//! BitVMX Integration for Option Verification
//! 
//! Handles communication with BitVMX protocol services for option lifecycle verification

use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use tracing::{info, error, debug};
use super::transaction::CreateOptionTx;

/// BitVMX Protocol Client for communication with Python services
pub struct BitVMXClient {
    prover_url: String,
    verifier_url: String,
    client: reqwest::Client,
}

/// BitVMX Setup Request for new option product
#[derive(Debug, Serialize)]
pub struct BitVMXSetupRequest {
    pub option_id: String,
    pub option_type: String,
    pub strike: u64,
    pub expiry: u64,
    pub verification_type: String,
    pub program_binary: String, // Base64 encoded RISC-V binary
}

/// BitVMX Setup Response from protocol
#[derive(Debug, Deserialize)]
pub struct BitVMXSetupResponse {
    pub success: bool,
    pub program_hash: String,
    pub prover_public_keys: Option<BitVMXPublicKeys>,
    pub verifier_public_keys: Option<BitVMXPublicKeys>,
    pub protocol_id: String,
    pub error_message: Option<String>,
}

/// BitVMX Public Keys for protocol participants
#[derive(Debug, Deserialize)]
pub struct BitVMXPublicKeys {
    pub keys: Vec<String>,
    pub commitment_hash: String,
}

/// BitVMX Verification Request
#[derive(Debug, Serialize)]
pub struct BitVMXVerificationRequest {
    pub protocol_id: String,
    pub input_data: String, // Hex encoded input
    pub expected_output: String, // Hex encoded expected output
}

/// BitVMX Verification Response
#[derive(Debug, Deserialize)]
pub struct BitVMXVerificationResponse {
    pub valid: bool,
    pub execution_trace_hash: String,
    pub proof_data: Option<String>,
    pub challenge_data: Option<String>,
}

impl BitVMXClient {
    /// Create new BitVMX client
    pub fn new() -> Self {
        Self {
            prover_url: "http://localhost:8081".to_string(),
            verifier_url: "http://localhost:8080".to_string(),
            client: reqwest::Client::new(),
        }
    }

    /// Create BitVMX client with custom URLs
    pub fn with_urls(prover_url: String, verifier_url: String) -> Self {
        Self {
            prover_url,
            verifier_url,
            client: reqwest::Client::new(),
        }
    }

    /// Setup BitVMX protocol for new option product
    pub async fn setup_option_protocol(
        &self,
        create_tx: &CreateOptionTx,
    ) -> Result<BitVMXSetupResponse, String> {
        info!("🔧 Setting up BitVMX protocol for option: {}", create_tx.option_id);

        // Load verification program binary
        let program_binary = self.load_verification_program().await?;

        let setup_request = BitVMXSetupRequest {
            option_id: create_tx.option_id.clone(),
            option_type: format!("{:?}", create_tx.option_type),
            strike: create_tx.strike,
            expiry: create_tx.expiry,
            verification_type: "ProductCreation".to_string(),
            program_binary,
        };

        debug!("Sending setup request to prover: {}", self.prover_url);

        let response = self.client
            .post(&format!("{}/v1/setup", self.prover_url))
            .json(&setup_request)
            .send()
            .await
            .map_err(|e| format!("Failed to send setup request: {}", e))?;

        if !response.status().is_success() {
            return Err(format!("Setup request failed with status: {}", response.status()));
        }

        let setup_response: BitVMXSetupResponse = response
            .json()
            .await
            .map_err(|e| format!("Failed to parse setup response: {}", e))?;

        if setup_response.success {
            info!("✅ BitVMX protocol setup successful: {}", setup_response.program_hash);
        } else {
            error!("❌ BitVMX protocol setup failed: {:?}", setup_response.error_message);
        }

        Ok(setup_response)
    }

    /// Verify option transaction using BitVMX
    pub async fn verify_transaction(
        &self,
        protocol_id: &str,
        input_data: &[u8],
        expected_output: &[u8],
    ) -> Result<BitVMXVerificationResponse, String> {
        info!("🔍 Verifying transaction with BitVMX protocol: {}", protocol_id);

        let verification_request = BitVMXVerificationRequest {
            protocol_id: protocol_id.to_string(),
            input_data: hex::encode(input_data),
            expected_output: hex::encode(expected_output),
        };

        debug!("Sending verification request to verifier: {}", self.verifier_url);

        let response = self.client
            .post(&format!("{}/v1/verify", self.verifier_url))
            .json(&verification_request)
            .send()
            .await
            .map_err(|e| format!("Failed to send verification request: {}", e))?;

        if !response.status().is_success() {
            return Err(format!("Verification request failed with status: {}", response.status()));
        }

        let verification_response: BitVMXVerificationResponse = response
            .json()
            .await
            .map_err(|e| format!("Failed to parse verification response: {}", e))?;

        if verification_response.valid {
            info!("✅ BitVMX verification successful");
        } else {
            info!("❌ BitVMX verification failed");
        }

        Ok(verification_response)
    }

    /// Check if BitVMX services are running
    pub async fn health_check(&self) -> Result<bool, String> {
        debug!("Checking BitVMX services health");

        // Check prover health
        let prover_health = self.client
            .get(&format!("{}/health", self.prover_url))
            .send()
            .await;

        // Check verifier health  
        let verifier_health = self.client
            .get(&format!("{}/health", self.verifier_url))
            .send()
            .await;

        match (prover_health, verifier_health) {
            (Ok(p), Ok(v)) if p.status().is_success() && v.status().is_success() => {
                info!("✅ BitVMX services are healthy");
                Ok(true)
            }
            _ => {
                error!("❌ BitVMX services are not available");
                Ok(false)
            }
        }
    }

    /// Load compiled RISC-V verification program
    async fn load_verification_program(&self) -> Result<String, String> {
        // Path to compiled option verification program
        let program_path = "../option_verification_program/target/riscv32imc-unknown-none-elf/release/option_verification_program";
        
        match tokio::fs::read(program_path).await {
            Ok(binary) => {
                info!("📁 Loaded verification program: {} bytes", binary.len());
                Ok(base64::encode(binary))
            }
            Err(e) => {
                error!("Failed to load verification program: {}", e);
                // Return a placeholder for testing
                info!("Using placeholder program binary for testing");
                Ok(base64::encode(b"placeholder_risc_v_program"))
            }
        }
    }

    /// Generate BitVMX program commitment hash
    pub async fn generate_program_hash(
        &self,
        create_tx: &CreateOptionTx,
    ) -> Result<String, String> {
        // For now, generate a deterministic hash based on transaction data
        // In production, this would be the actual BitVMX program commitment
        
        let program_input = format!(
            "option_id={},type={:?},strike={},expiry={}",
            create_tx.option_id,
            create_tx.option_type,
            create_tx.strike,
            create_tx.expiry
        );

        use std::collections::hash_map::DefaultHasher;
        use std::hash::{Hash, Hasher};
        
        let mut hasher = DefaultHasher::new();
        program_input.hash(&mut hasher);
        let hash = format!("bitvmx_{:016x}", hasher.finish());

        info!("🔑 Generated BitVMX program hash: {}", hash);
        Ok(hash)
    }
}

impl Default for BitVMXClient {
    fn default() -> Self {
        Self::new()
    }
}

/// BitVMX Option Verification Engine
pub struct BitVMXOptionVerifier {
    client: BitVMXClient,
    active_protocols: HashMap<String, String>, // option_id -> protocol_id
}

impl BitVMXOptionVerifier {
    /// Create new BitVMX option verifier
    pub fn new() -> Self {
        Self {
            client: BitVMXClient::new(),
            active_protocols: HashMap::new(),
        }
    }

    /// Register new option product with BitVMX protocol
    pub async fn register_option_product(
        &mut self,
        create_tx: &CreateOptionTx,
    ) -> Result<String, String> {
        info!("📝 Registering option product with BitVMX: {}", create_tx.option_id);

        // Check if BitVMX services are available
        if !self.client.health_check().await? {
            return Err("BitVMX services are not available".to_string());
        }

        // Setup BitVMX protocol
        let setup_response = self.client.setup_option_protocol(create_tx).await?;

        if !setup_response.success {
            return Err(format!("BitVMX setup failed: {:?}", setup_response.error_message));
        }

        // Store protocol mapping
        self.active_protocols.insert(
            create_tx.option_id.clone(),
            setup_response.protocol_id.clone(),
        );

        info!("✅ Option product registered with BitVMX protocol: {}", setup_response.protocol_id);
        Ok(setup_response.program_hash)
    }

    /// Verify option purchase transaction
    pub async fn verify_purchase(
        &self,
        option_id: &str,
        purchase_data: &[u8],
    ) -> Result<bool, String> {
        let protocol_id = self.active_protocols.get(option_id)
            .ok_or_else(|| format!("No BitVMX protocol found for option: {}", option_id))?;

        // Expected output for valid purchase (simplified)
        let expected_output = b"purchase_valid";

        let verification = self.client
            .verify_transaction(protocol_id, purchase_data, expected_output)
            .await?;

        Ok(verification.valid)
    }

    /// Verify option settlement transaction
    pub async fn verify_settlement(
        &self,
        option_id: &str,
        settlement_data: &[u8],
    ) -> Result<bool, String> {
        let protocol_id = self.active_protocols.get(option_id)
            .ok_or_else(|| format!("No BitVMX protocol found for option: {}", option_id))?;

        // Expected output for valid settlement (simplified)
        let expected_output = b"settlement_valid";

        let verification = self.client
            .verify_transaction(protocol_id, settlement_data, expected_output)
            .await?;

        Ok(verification.valid)
    }

    /// Get active protocol count
    pub fn active_protocol_count(&self) -> usize {
        self.active_protocols.len()
    }
}

impl Default for BitVMXOptionVerifier {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::options::{OptionType, TxType};

    #[tokio::test]
    async fn test_bitvmx_client_creation() {
        let client = BitVMXClient::new();
        assert_eq!(client.prover_url, "http://localhost:8081");
        assert_eq!(client.verifier_url, "http://localhost:8080");
    }

    #[test]
    fn test_bitvmx_verifier_creation() {
        let verifier = BitVMXOptionVerifier::new();
        assert_eq!(verifier.active_protocol_count(), 0);
    }

    #[tokio::test]
    async fn test_program_hash_generation() {
        let client = BitVMXClient::new();
        
        let create_tx = CreateOptionTx {
            protocol: "BTCFI01".to_string(),
            tx_type: TxType::Create,
            option_id: "test_option".to_string(),
            option_type: OptionType::Call,
            underlying: "BTCUSD".to_string(),
            strike: 50000,
            expiry: 1723126800,
            unit: 1.0,
            issuer: "test_issuer".to_string(),
            initial_iv: 0.5,
            premium_formula: "Black-Scholes".to_string(),
            oracle_ids: vec!["test_oracle".to_string()],
            created_at: 1723040400,
            sig: "test_sig".to_string(),
        };

        let hash = client.generate_program_hash(&create_tx).await.unwrap();
        assert!(hash.starts_with("bitvmx_"));
        assert_eq!(hash.len(), 23); // "bitvmx_" + 16 hex chars
    }
}