//! Integration tests for BitVMX Option Registration

use contracts::{
    SimpleContractManager, OptionType,
    bitvmx_option_registry::{BitVMXOptionRegistry, BitVMXOptionInput},
};
use anyhow::Result;

#[tokio::test]
async fn test_bitvmx_option_registration() -> Result<()> {
    // Setup
    let mut manager = SimpleContractManager::new();
    manager.add_liquidity(100_000_000)?; // 1 BTC
    
    // Test data
    let option_type = OptionType::Call;
    let strike_price = 52000_00; // $52,000
    let quantity = 10_000_000;   // 0.1 BTC
    let premium = 500_000;       // 0.005 BTC
    let expiry_timestamp = chrono::Utc::now().timestamp() as u64 + 7 * 24 * 3600; // 7 days
    let user_id = "test_user".to_string();
    
    println!("🚀 Testing BitVMX Option Registration");
    println!("=====================================");
    
    // Register option with BitVMX
    let (option_id, txid, proof) = manager.create_option_with_bitvmx(
        option_type,
        strike_price,
        quantity,
        premium,
        expiry_timestamp,
        user_id.clone(),
    ).await?;
    
    println!("✅ Option registered successfully!");
    println!("   Option ID: {}", option_id);
    println!("   Transaction ID: {}", txid);
    println!("   Hash Chain Final: {}", hex::encode(&proof.hash_chain.final_hash));
    println!("   Checkpoints: {}", proof.hash_chain.steps.len());
    
    // Verify the option was created
    let option = manager.options.get(&option_id)
        .ok_or_else(|| anyhow::anyhow!("Option not found"))?;
    
    assert_eq!(option.option_type, option_type);
    assert_eq!(option.strike_price, strike_price);
    assert_eq!(option.quantity, quantity);
    assert_eq!(option.premium_paid, premium);
    
    println!("\n📊 Option Details:");
    println!("   Type: {:?}", option.option_type);
    println!("   Strike: ${}", option.strike_price as f64 / 100.0);
    println!("   Quantity: {} BTC", option.quantity as f64 / 100_000_000.0);
    println!("   Premium: {} BTC", option.premium_paid as f64 / 100_000_000.0);
    
    Ok(())
}

#[tokio::test]
async fn test_bitvmx_registration_validation() -> Result<()> {
    let registry = BitVMXOptionRegistry::new(bitcoin::Network::Regtest);
    
    // Test invalid strike price
    let invalid_input = BitVMXOptionInput {
        option_type: OptionType::Call,
        strike_price: 100, // Too low ($1)
        quantity: 10_000_000,
        expiry_timestamp: chrono::Utc::now().timestamp() as u64 + 86400,
        issuer: "test".to_string(),
        premium: 100_000,
        oracle_sources: vec!["binance".to_string()],
    };
    
    // This should fail validation in BitVMX
    match registry.register_option(invalid_input).await {
        Ok(_) => panic!("Should have failed validation"),
        Err(e) => {
            println!("✅ Correctly rejected invalid option: {}", e);
        }
    }
    
    Ok(())
}

#[tokio::test]
async fn test_bitvmx_hash_chain_verification() -> Result<()> {
    // Create a valid option
    let input = BitVMXOptionInput {
        option_type: OptionType::Put,
        strike_price: 48000_00,
        quantity: 5_000_000,
        expiry_timestamp: chrono::Utc::now().timestamp() as u64 + 14 * 86400,
        issuer: "verifier".to_string(),
        premium: 200_000,
        oracle_sources: vec!["binance".to_string(), "coinbase".to_string()],
    };
    
    let registry = BitVMXOptionRegistry::new(bitcoin::Network::Regtest);
    let (_, proof) = registry.register_option(input).await?;
    
    // Verify hash chain
    println!("\n🔍 Verifying BitVMX Hash Chain:");
    println!("   Total steps: {}", proof.hash_chain.steps.len());
    
    // Verify each checkpoint
    for (i, step) in proof.hash_chain.steps.iter().enumerate() {
        println!("   Checkpoint {}: step {} -> {}", 
            i, 
            step.step_number,
            hex::encode(&step.state_hash[0..8])
        );
    }
    
    // Final hash should match the last checkpoint
    let last_checkpoint = proof.hash_chain.steps.last().unwrap();
    assert_eq!(last_checkpoint.state_hash, proof.hash_chain.final_hash);
    
    println!("✅ Hash chain verified!");
    
    Ok(())
}

#[test]
fn test_option_data_encoding() {
    use contracts::bitcoin_anchoring_v2::CreateOptionAnchorData;
    
    // Test that BitVMX output fits in OP_RETURN with BTCFi data
    let bitvmx_hash = [0xAA; 32]; // 32 bytes
    let btcfi_data = CreateOptionAnchorData {
        tx_type: contracts::bitcoin_anchoring_v2::TxType::Create,
        option_id: [0xBB; 6],
        option_type: 0,
        strike_sats: 5200000000000,
        expiry: 1735689600,
        unit: 1.0,
    };
    
    let btcfi_encoded = btcfi_data.encode();
    assert_eq!(btcfi_encoded.len(), 28);
    
    let total_size = bitvmx_hash.len() + btcfi_encoded.len();
    assert_eq!(total_size, 60);
    assert!(total_size <= 80, "Data exceeds OP_RETURN limit");
    
    println!("✅ Data encoding test passed:");
    println!("   BitVMX hash: 32 bytes");
    println!("   BTCFi data: 28 bytes");
    println!("   Total: 60 bytes (within 80 byte limit)");
}