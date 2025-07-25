//! Demo: Option registration with Bitcoin OP_RETURN anchoring

use contracts::{
    SimpleContractManager, OptionType, BitcoinAnchoringService
};
use chrono::Utc;

#[tokio::main]
async fn main() -> anyhow::Result<()> {
    env_logger::init();
    
    println!("=== BTCFi Option Anchoring Demo ===");
    println!("Demonstrating on-chain option registration using OP_RETURN\n");
    
    // Initialize components
    let mut contract_manager = SimpleContractManager::new();
    let anchoring_service = BitcoinAnchoringService::regtest();
    
    // Add initial liquidity
    println!("1. Adding liquidity to option pool...");
    contract_manager.add_liquidity(100_000_000)?; // 1 BTC
    println!("   ✓ Added 1 BTC liquidity");
    
    // Get current BTC price (mock for demo)
    let btc_price = 52000_00; // $52,000
    println!("\n2. Current BTC price: ${}", btc_price as f64 / 100.0);
    
    // Create and anchor a call option
    println!("\n3. Creating CALL option:");
    println!("   - Strike: $50,000");
    println!("   - Quantity: 0.1 BTC");
    println!("   - Expiry: 1 week");
    
    let call_id = format!("CALL_{}_{}", btc_price, Utc::now().timestamp());
    let call_txid = contract_manager.create_option_with_anchor(
        call_id.clone(),
        OptionType::Call,
        50000_00,     // Strike price
        10_000_000,   // 0.1 BTC
        500_000,      // 0.005 BTC premium
        144 * 7,      // 1 week in blocks
        "demo_user".to_string(),
        &anchoring_service,
    ).await?;
    
    println!("   ✓ Call option created and anchored!");
    println!("   - Option ID: {}", call_id);
    println!("   - Bitcoin txid: {}", call_txid);
    println!("   - OP_RETURN: CREATE:0:5000000:{}", 144 * 7);
    
    // Create and anchor a put option
    println!("\n4. Creating PUT option:");
    println!("   - Strike: $54,000");
    println!("   - Quantity: 0.05 BTC");
    println!("   - Expiry: 2 weeks");
    
    let put_id = format!("PUT_{}_{}", btc_price, Utc::now().timestamp());
    let put_txid = contract_manager.create_option_with_anchor(
        put_id.clone(),
        OptionType::Put,
        54000_00,     // Strike price
        5_000_000,    // 0.05 BTC
        300_000,      // 0.003 BTC premium
        144 * 14,     // 2 weeks
        "demo_user".to_string(),
        &anchoring_service,
    ).await?;
    
    println!("   ✓ Put option created and anchored!");
    println!("   - Option ID: {}", put_id);
    println!("   - Bitcoin txid: {}", put_txid);
    println!("   - OP_RETURN: CREATE:1:5400000:{}", 144 * 14);
    
    // Show pool state
    println!("\n5. Current Pool State:");
    println!("   - Total Liquidity: {} BTC", contract_manager.pool_state.total_liquidity as f64 / 100_000_000.0);
    println!("   - Locked Collateral: {} BTC", contract_manager.pool_state.locked_collateral as f64 / 100_000_000.0);
    println!("   - Available Liquidity: {} BTC", contract_manager.pool_state.available_liquidity as f64 / 100_000_000.0);
    println!("   - Premium Collected: {} BTC", contract_manager.pool_state.total_premium_collected as f64 / 100_000_000.0);
    println!("   - Active Options: {}", contract_manager.pool_state.active_options);
    println!("   - Utilization Rate: {:.1}%", contract_manager.pool_state.utilization_rate());
    
    // Verify anchors
    println!("\n6. Verifying on-chain anchors...");
    
    let call_anchor = anchoring_service.verify_anchor(&call_txid).await?;
    println!("   ✓ Call option verified:");
    println!("     - Type: {}", if call_anchor.option_type == 0 { "CALL" } else { "PUT" });
    println!("     - Strike: ${}", call_anchor.strike_price as f64 / 100.0);
    
    let put_anchor = anchoring_service.verify_anchor(&put_txid).await?;
    println!("   ✓ Put option verified:");
    println!("     - Type: {}", if put_anchor.option_type == 0 { "CALL" } else { "PUT" });
    println!("     - Strike: ${}", put_anchor.strike_price as f64 / 100.0);
    
    println!("\n=== Demo Complete ===");
    println!("\nTo view transactions on Bitcoin:");
    println!("  bitcoin-cli -regtest getrawtransaction {} true", call_txid);
    println!("  bitcoin-cli -regtest getrawtransaction {} true", put_txid);
    
    Ok(())
}

/// How to run this demo:
/// 
/// 1. Start Bitcoin regtest:
///    bitcoind -regtest -daemon -rpcuser=test -rpcpassword=test
/// 
/// 2. Create wallet and generate blocks:
///    bitcoin-cli -regtest createwallet "test"
///    bitcoin-cli -regtest -generate 101
/// 
/// 3. Run the demo:
///    cargo run --example option_anchoring_demo
/// 
/// 4. Check the OP_RETURN data:
///    bitcoin-cli -regtest getrawtransaction <txid> true | jq '.vout[] | select(.scriptPubKey.type == "nulldata")'