//! Bitcoin OP_RETURN anchoring integration tests

use contracts::{
    SimpleContractManager, OptionType, BitcoinAnchoringService, OptionAnchorData
};
use anyhow::Result;

/// Test option creation with OP_RETURN anchoring on Bitcoin regtest
#[tokio::test]
#[ignore = "Requires Bitcoin regtest node running"]
async fn test_option_anchoring_on_regtest() -> Result<()> {
    // Setup
    let mut manager = SimpleContractManager::new();
    let anchoring_service = BitcoinAnchoringService::regtest();
    
    // Add liquidity to pool
    manager.add_liquidity(10_000_000)?; // 0.1 BTC
    
    // Create a call option
    let option_id = "test_call_001".to_string();
    let txid = manager.create_option_with_anchor(
        option_id.clone(),
        OptionType::Call,
        50000_00, // $50,000 strike
        1_000_000, // 0.01 BTC quantity
        100_000,   // 0.001 BTC premium
        144 * 7,   // 1 week expiry (in blocks)
        "test_user".to_string(),
        &anchoring_service,
    ).await?;
    
    println!("Option {} anchored with txid: {}", option_id, txid);
    
    // Verify the anchor
    let anchor_data = anchoring_service.verify_anchor(&txid).await?;
    assert_eq!(anchor_data.option_type, 0); // Call
    assert_eq!(anchor_data.strike_price, 50000_00);
    
    // Create a put option
    let put_id = "test_put_001".to_string();
    let put_txid = manager.create_option_with_anchor(
        put_id.clone(),
        OptionType::Put,
        48000_00, // $48,000 strike
        2_000_000, // 0.02 BTC quantity
        150_000,   // 0.0015 BTC premium
        144 * 14,  // 2 weeks expiry
        "test_user".to_string(),
        &anchoring_service,
    ).await?;
    
    println!("Option {} anchored with txid: {}", put_id, put_txid);
    
    // Verify pool state
    assert_eq!(manager.pool_state.active_options, 2);
    assert_eq!(manager.pool_state.total_premium_collected, 250_000);
    
    println!("\nPool State:");
    println!("  Active Options: {}", manager.pool_state.active_options);
    println!("  Total Liquidity: {} sats", manager.pool_state.total_liquidity);
    println!("  Locked Collateral: {} sats", manager.pool_state.locked_collateral);
    println!("  Available Liquidity: {} sats", manager.pool_state.available_liquidity);
    
    Ok(())
}

/// Test OP_RETURN data encoding and decoding
#[test]
fn test_anchor_data_schema() {
    // Test call option
    let call_anchor = OptionAnchorData {
        option_type: 0,
        strike_price: 52000_00,
        expiry: 1735689600,
    };
    
    let encoded = call_anchor.encode();
    let expected = b"CREATE:0:5200000:1735689600";
    assert_eq!(&encoded, expected);
    
    // Test decoding
    let decoded = OptionAnchorData::decode(&encoded).unwrap();
    assert_eq!(decoded.option_type, 0);
    assert_eq!(decoded.strike_price, 52000_00);
    assert_eq!(decoded.expiry, 1735689600);
    
    // Test put option
    let put_anchor = OptionAnchorData {
        option_type: 1,
        strike_price: 48000_00,
        expiry: 1736294400,
    };
    
    let put_encoded = put_anchor.encode();
    assert!(put_encoded.starts_with(b"CREATE:1:"));
}

/// Setup script for Bitcoin regtest
/// Run this before running the tests:
/// ```bash
/// # Start Bitcoin regtest node
/// bitcoind -regtest -daemon \
///   -rpcuser=test -rpcpassword=test \
///   -rpcallowip=127.0.0.1 \
///   -fallbackfee=0.00001
/// 
/// # Create wallet
/// bitcoin-cli -regtest createwallet "test"
/// 
/// # Generate some blocks to get coins
/// bitcoin-cli -regtest -generate 101
/// ```
#[test]
fn print_regtest_setup_instructions() {
    println!("\n=== Bitcoin Regtest Setup Instructions ===\n");
    println!("1. Start Bitcoin regtest node:");
    println!("   bitcoind -regtest -daemon \\");
    println!("     -rpcuser=test -rpcpassword=test \\");
    println!("     -rpcallowip=127.0.0.1 \\");
    println!("     -fallbackfee=0.00001\n");
    println!("2. Create wallet:");
    println!("   bitcoin-cli -regtest createwallet \"test\"\n");
    println!("3. Generate blocks to get coins:");
    println!("   bitcoin-cli -regtest -generate 101\n");
    println!("4. Run the anchoring test:");
    println!("   cargo test --test bitcoin_anchoring_test -- --ignored --nocapture\n");
    println!("5. Check OP_RETURN data:");
    println!("   bitcoin-cli -regtest getrawtransaction <txid> true\n");
}