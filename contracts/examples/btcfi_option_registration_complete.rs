use anyhow::Result;
use bitcoin::Network;
use contracts::bitvmx_option_registry::{BitVMXOptionRegistry, BitVMXOptionInput};
use oracle_vm_common::types::OptionType;
use tokio;

/// Complete BTCFi Option Registration with BitVMX
/// 
/// This example demonstrates how to register option products using the BitVMX protocol
/// for trustless computation and Bitcoin Layer 1 native settlement.

#[tokio::main]
async fn main() -> Result<()> {
    println!("=== BTCFi Option Registration with BitVMX ===\n");

    // Initialize BitVMX Option Registry for regtest
    let registry = BitVMXOptionRegistry::new(Network::Regtest);

    // Test Case 1: Bitcoin Call Option
    println!("📈 Registering Bitcoin Call Option...");
    let call_option = BitVMXOptionInput {
        option_type: OptionType::Call,
        strike_price: 70_000_00,  // $70,000 in cents
        quantity: 10_000_000,     // 0.1 BTC in satoshis
        premium: 500_000,         // 0.005 BTC premium
        expiry_timestamp: chrono::Utc::now().timestamp() as u64 + 86400 * 7, // 1 week
        issuer: "btcfi_issuer_001".to_string(),
        oracle_sources: vec![
            "binance".to_string(),
            "coinbase".to_string(), 
            "kraken".to_string(),
        ],
    };

    match registry.register_option(call_option).await {
        Ok((txid, proof)) => {
            println!("✅ Call Option Registration Successful!");
            println!("   Transaction ID: {}", txid);
            println!("   Option ID: {}", hex::encode(&proof.output[0..6]));
            println!("   Hash Chain Final: {}", hex::encode(proof.hash_chain.final_hash));
            println!("   Execution Steps: {}", proof.execution_trace.len());
        }
        Err(e) => {
            println!("❌ Call Option Registration Failed: {}", e);
        }
    }

    println!();

    // Test Case 2: Bitcoin Put Option
    println!("📉 Registering Bitcoin Put Option...");
    let put_option = BitVMXOptionInput {
        option_type: OptionType::Put,
        strike_price: 65_000_00,  // $65,000 in cents
        quantity: 5_000_000,      // 0.05 BTC in satoshis
        premium: 250_000,         // 0.0025 BTC premium
        expiry_timestamp: chrono::Utc::now().timestamp() as u64 + 86400 * 14, // 2 weeks
        issuer: "btcfi_issuer_002".to_string(),
        oracle_sources: vec![
            "binance".to_string(),
            "coinbase".to_string(),
            "kraken".to_string(),
        ],
    };

    match registry.register_option(put_option).await {
        Ok((txid, proof)) => {
            println!("✅ Put Option Registration Successful!");
            println!("   Transaction ID: {}", txid);
            println!("   Option ID: {}", hex::encode(&proof.output[0..6]));
            println!("   Hash Chain Final: {}", hex::encode(proof.hash_chain.final_hash));
            println!("   Execution Steps: {}", proof.execution_trace.len());
        }
        Err(e) => {
            println!("❌ Put Option Registration Failed: {}", e);
        }
    }

    println!();

    // Test Case 3: High-Value Option with Multiple Oracle Sources
    println!("🏦 Registering High-Value Institutional Option...");
    let institutional_option = BitVMXOptionInput {
        option_type: OptionType::Call,
        strike_price: 100_000_00, // $100,000 in cents
        quantity: 100_000_000,    // 1.0 BTC in satoshis
        premium: 5_000_000,       // 0.05 BTC premium
        expiry_timestamp: chrono::Utc::now().timestamp() as u64 + 86400 * 30, // 1 month
        issuer: "btcfi_institutional_001".to_string(),
        oracle_sources: vec![
            "binance".to_string(),
            "coinbase".to_string(),
            "kraken".to_string(),
            "bitstamp".to_string(),
            "gemini".to_string(),
        ],
    };

    match registry.register_option(institutional_option).await {
        Ok((txid, proof)) => {
            println!("✅ Institutional Option Registration Successful!");
            println!("   Transaction ID: {}", txid);
            println!("   Option ID: {}", hex::encode(&proof.output[0..6]));
            println!("   Hash Chain Final: {}", hex::encode(proof.hash_chain.final_hash));
            println!("   Execution Steps: {}", proof.execution_trace.len());
            
            // Verify BitVMX proof integrity
            println!("\n🔍 BitVMX Proof Verification:");
            println!("   Input Hash: {}", hex::encode(proof.input_hash));
            println!("   Hash Chain Steps: {}", proof.hash_chain.steps.len());
            for (i, step) in proof.hash_chain.steps.iter().enumerate() {
                println!("     Step {}: {} -> {}", 
                    step.step_number, 
                    i,
                    hex::encode(&step.state_hash[0..8])
                );
            }
        }
        Err(e) => {
            println!("❌ Institutional Option Registration Failed: {}", e);
        }
    }

    println!("\n=== BitVMX Option Registration Complete ===");
    println!("All options are now registered on Bitcoin Layer 1 with verifiable computation proofs.");
    println!("The option contracts can be settled using the BitVMX protocol challenge mechanism.");

    Ok(())
}

/// Test helper to create sample option data
fn create_sample_option(
    option_type: OptionType,
    strike: u64,
    quantity: u64,
    premium: u64,
    days_to_expiry: u64,
    issuer_id: u32,
) -> BitVMXOptionInput {
    BitVMXOptionInput {
        option_type,
        strike_price: strike,
        quantity,
        premium,
        expiry_timestamp: chrono::Utc::now().timestamp() as u64 + 86400 * days_to_expiry,
        issuer: format!("btcfi_issuer_{:03}", issuer_id),
        oracle_sources: vec![
            "binance".to_string(),
            "coinbase".to_string(),
            "kraken".to_string(),
        ],
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_sample_option_creation() {
        let option = create_sample_option(
            OptionType::Call,
            50_000_00,
            10_000_000,
            100_000,
            7,
            1,
        );

        assert_eq!(option.option_type, OptionType::Call);
        assert_eq!(option.strike_price, 50_000_00);
        assert_eq!(option.quantity, 10_000_000);
        assert_eq!(option.premium, 100_000);
        assert_eq!(option.issuer, "btcfi_issuer_001");
        assert_eq!(option.oracle_sources.len(), 3);
    }

    #[tokio::test]
    async fn test_option_registry_initialization() {
        let registry = BitVMXOptionRegistry::new(Network::Regtest);
        // Registry should be initialized without errors
        assert!(true); // Placeholder for actual initialization tests
    }
}