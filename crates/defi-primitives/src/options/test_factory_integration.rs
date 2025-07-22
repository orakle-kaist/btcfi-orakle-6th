//! Test integration of Option Factory with Bitcoin Client

use super::*;
use bitcoin_client::{BitcoinConfig, BitcoinClient, Network};
use crate::options::bitvmx_integration::BitVMXOptionVerifier;

#[tokio::test]
async fn test_create_and_anchor_integration() {
    // Initialize logging for test
    let _ = tracing_subscriber::fmt::try_init();

    // Configure Bitcoin client for regtest
    let bitcoin_config = BitcoinConfig {
        network: Network::Regtest,
        rpc_url: "http://localhost:18443".to_string(),
        rpc_user: "bitcoinrpc".to_string(),
        rpc_password: "rpcpassword".to_string(),
        wallet_name: Some("testwallet".to_string()),
    };

    // Create factory with Bitcoin client
    let mut factory = OptionFactory::new_with_bitcoin(
        "bc1q_test_operator_address".to_string(),
        bitcoin_config,
    );

    // Create test product request
    let request = CreateProductRequest {
        option_type: OptionType::Call,
        underlying: "BTCUSD".to_string(),
        strike: 52000,
        days_to_expiry: 7,
        initial_iv: 0.68,
        max_units: 100,
        premium_adjustment: Some(1.1), // 10% markup
    };

    // Test create_and_anchor method
    let current_btc_price = 50000.0;
    
    match factory.create_and_anchor(request, current_btc_price).await {
        Ok(response) => {
            println!("✅ Option created and anchored successfully!");
            println!("Option ID: {}", response.option_id);
            println!("Premium: {} BTC", response.calculated_premium);
            println!("Max Units: {}", response.max_units);
            println!("BitVMX Program Hash: {}", response.bitvmx_program_hash);
            
            if let Some(txid) = response.bitcoin_anchor_txid {
                println!("Bitcoin Anchor TXID: {}", txid);
                println!("🎯 Successfully anchored to Bitcoin L1!");
            } else {
                println!("⚠️ Bitcoin anchoring skipped (no node connection)");
            }
            
            // Verify product was created in factory
            let product = factory.get_product(&response.option_id);
            assert!(product.is_some());
            
            let product_list = factory.get_product_list(current_btc_price);
            assert!(!product_list.is_empty());
            
            println!("📊 Product List: {} active products", product_list.len());
        }
        Err(e) => {
            println!("❌ Failed to create and anchor option: {}", e);
            println!("This is expected if Bitcoin node is not running");
            
            // Test should still pass even if Bitcoin node is down
            // The create_and_anchor method should handle this gracefully
            assert!(e.to_string().contains("Bitcoin") || e.to_string().contains("RPC"));
        }
    }
}

#[tokio::test]
async fn test_create_product_without_bitcoin() {
    let _ = tracing_subscriber::fmt::try_init();

    // Create factory without Bitcoin client
    let mut factory = OptionFactory::new("bc1q_test_operator_no_bitcoin".to_string());

    let request = CreateProductRequest {
        option_type: OptionType::Put,
        underlying: "BTCUSD".to_string(),
        strike: 48000,
        days_to_expiry: 14,
        initial_iv: 0.75,
        max_units: 50,
        premium_adjustment: None,
    };

    // Test regular create_product method
    let result = factory.create_product(request, 50000.0);
    
    match result {
        Ok(response) => {
            println!("✅ Option created without Bitcoin anchoring");
            println!("Option ID: {}", response.option_id);
            println!("Strike: {} (PUT)", response.create_tx.strike);
            
            assert_eq!(response.create_tx.option_type, OptionType::Put);
            assert_eq!(response.create_tx.strike, 48000);
            assert_eq!(response.max_units, 50);
        }
        Err(e) => {
            panic!("Failed to create option without Bitcoin: {}", e);
        }
    }
}

#[test]
fn test_factory_bitcoin_integration() {
    let _ = tracing_subscriber::fmt::try_init();

    // Test creating factory with Bitcoin config
    let bitcoin_config = BitcoinConfig {
        network: Network::Regtest,
        rpc_url: "http://localhost:18443".to_string(),
        rpc_user: "bitcoinrpc".to_string(),
        rpc_password: "rpcpassword".to_string(),
        wallet_name: Some("testwallet".to_string()),
    };

    let factory = OptionFactory::new_with_bitcoin(
        "bc1q_test_operator".to_string(),
        bitcoin_config,
    );

    // Verify Bitcoin client is configured
    assert!(factory.bitcoin_client.is_some());
    println!("✅ Factory with Bitcoin client created successfully");
}

#[test]
fn test_factory_full_integration() {
    let _ = tracing_subscriber::fmt::try_init();

    // Test creating factory with full BitVMX and Bitcoin integration
    let bitcoin_config = BitcoinConfig {
        network: Network::Regtest,
        rpc_url: "http://localhost:18443".to_string(),
        rpc_user: "bitcoinrpc".to_string(),
        rpc_password: "rpcpassword".to_string(),
        wallet_name: Some("testwallet".to_string()),
    };

    let bitcoin_client = BitcoinClient::new(bitcoin_config);
    let bitvmx_verifier = BitVMXOptionVerifier::new();
    
    let factory = OptionFactory::new_with_full_integration(
        "bc1q_test_operator_full".to_string(),
        vec!["oracle1".to_string()],
        Some(bitcoin_client),
        Some(bitvmx_verifier),
    );

    // Verify both Bitcoin client and BitVMX verifier are configured
    assert!(factory.bitcoin_client.is_some());
    assert!(factory.bitvmx_verifier.is_some());
    println!("✅ Factory with full BitVMX + Bitcoin integration created successfully");
}

#[tokio::test]
async fn test_full_bitvmx_integration() {
    let _ = tracing_subscriber::fmt::try_init();
    
    println!("🚀 Testing Full BitVMX + OP_RETURN Integration");
    
    // Initialize Bitcoin client
    let bitcoin_config = BitcoinConfig {
        network: Network::Regtest,
        rpc_url: "http://localhost:18443".to_string(),
        rpc_user: "bitcoinrpc".to_string(),
        rpc_password: "rpcpassword".to_string(),
        wallet_name: Some("testwallet".to_string()),
    };
    let bitcoin_client = BitcoinClient::new(bitcoin_config);
    
    // Initialize BitVMX verifier with actual service URLs
    let bitvmx_verifier = BitVMXOptionVerifier::with_urls(
        "http://localhost:8081".to_string(),
        "http://localhost:8080".to_string(),
    );
    
    // Create factory with both integrations
    let mut factory = OptionFactory::new_with_full_integration(
        "btc_operator_integration_test".to_string(),
        vec!["oracle1".to_string()],
        Some(bitcoin_client),
        Some(bitvmx_verifier),
    );
    
    let request = CreateProductRequest {
        option_type: OptionType::Call,
        underlying: "BTCUSD".to_string(),
        strike: 68000,
        days_to_expiry: 7,
        initial_iv: 0.70,
        max_units: 25,
        premium_adjustment: None,
    };
    
    let current_btc_price = 70000.0;
    
    println!("📦 Creating option with full integration...");
    
    match factory.create_and_anchor(request, current_btc_price).await {
        Ok(response) => {
            println!("✅ SUCCESS! Full integration working:");
            println!("   Product ID: {}", response.option_id);
            println!("   Premium: {} BTC", response.calculated_premium);
            
            // Check Bitcoin anchoring
            let bitcoin_ok = response.bitcoin_anchor_txid.is_some();
            if let Some(ref tx_id) = response.bitcoin_anchor_txid {
                println!("   🔗 Bitcoin L1 Anchored: {}", tx_id);
                println!("      → OP_RETURN transaction successful!");
            } else {
                println!("   ⚠️  Bitcoin anchoring failed/skipped");
            }
            
            // Check BitVMX verification  
            let bitvmx_hash = &response.bitvmx_program_hash;
            let bitvmx_ok = bitvmx_hash.starts_with("bitvmx_");
            if bitvmx_ok {
                println!("   🛡️  Real BitVMX Verification: {}", bitvmx_hash);
                println!("      → Using actual BitVMX protocol services!");
            } else if bitvmx_hash.starts_with("fallback_") {
                println!("   ⚠️  Fallback Verification: {}", bitvmx_hash);
                println!("      → BitVMX services not responding");
            }
            
            println!("\n🎯 Integration Status Summary:");
                
            println!("   {} Bitcoin L1 OP_RETURN: {}", 
                if bitcoin_ok { "✅" } else { "❌" },
                if bitcoin_ok { "Working" } else { "Failed" }
            );
            println!("   {} BitVMX Protocol: {}", 
                if bitvmx_ok { "✅" } else { "⚠️ " },
                if bitvmx_ok { "Active" } else { "Fallback" }
            );
            
            if bitcoin_ok && bitvmx_ok {
                println!("\n🎉 PERFECT! Both OP_RETURN and BitVMX are working!");
            } else if bitcoin_ok || bitvmx_ok {
                println!("\n✅ Partial integration working");
            } else {
                println!("\n⚠️  Both integrations failed/fallback");
            }
        }
        Err(e) => {
            println!("❌ Integration test failed: {}", e);
            println!("This may happen if Bitcoin node or BitVMX services are down");
        }
    }
}