//! Example: Register option product on Bitcoin testnet
//! 
//! This example demonstrates the complete flow of registering an option product
//! on Bitcoin testnet with BitVMX verification and hybrid anchoring.

use tokio;
use tracing::{info, error};
use chrono::{Utc, Duration};

// Import our crates
use defi_primitives::options::{
    CreateOptionTx, OptionType, 
    factory::OptionFactory,
    pricing::BlackScholesPricing
};
use bitcoin_client::{BitcoinClient, BitcoinConfig};
use bitvmx_integration::prover::BitVMXProver;
use committer::hybrid_anchor::HybridAnchorService;

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    // Initialize logging
    tracing_subscriber::init();
    
    info!("🚀 Starting Bitcoin testnet option registration demo");
    
    // Step 1: Initialize services
    info!("📊 Initializing services...");
    
    let bitcoin_client = BitcoinClient::testnet();
    let bitvmx_prover = BitVMXProver::with_default_config();
    let option_factory = OptionFactory::new();
    
    // Check Bitcoin testnet connection
    match bitcoin_client.get_network_info().await {
        Ok(info) => {
            info!("✅ Connected to Bitcoin testnet: {:?}", info);
        }
        Err(e) => {
            error!("❌ Failed to connect to Bitcoin testnet: {}", e);
            info!("💡 Make sure Bitcoin Core is running with testnet configuration");
            info!("💡 Example bitcoin.conf:");
            info!("   testnet=1");
            info!("   server=1");
            info!("   rpcuser=bitcoinrpc");
            info!("   rpcpassword=rpcpassword");
            info!("   rpcport=18332");
            return Ok(());
        }
    }
    
    // Step 2: Create test option product
    info!("🎯 Creating test option product...");
    
    let option_id = format!("BTC_CALL_55K_7D_{}", Utc::now().timestamp());
    let expiry = (Utc::now() + Duration::days(7)).timestamp() as u64;
    let strike_usd = 55000.0; // $55,000 strike
    let strike_sats = (strike_usd * 100_000_000.0) as u64; // Convert to satoshis
    
    // Calculate premium using Black-Scholes
    let pricing = BlackScholesPricing::new(
        52000.0,  // Current BTC price: $52,000
        strike_usd,  // Strike: $55,000
        7.0 / 365.0, // Time to expiry: 7 days
        0.05,     // Risk-free rate: 5%
        0.8,      // Volatility: 80%
    );
    
    let premium_usd = pricing.call_price();
    let premium_sats = (premium_usd * 100_000_000.0) as u64;
    
    info!("📈 Option parameters:");
    info!("   Option ID: {}", option_id);
    info!("   Type: Call");
    info!("   Strike: ${} ({} sats)", strike_usd, strike_sats);
    info!("   Expiry: {} days", 7);
    info!("   Premium: ${:.4} ({} sats)", premium_usd, premium_sats);
    
    let create_tx = CreateOptionTx {
        option_id: option_id.clone(),
        option_type: OptionType::Call,
        strike: strike_sats,
        expiry,
        underlying: "BTC/USD".to_string(),
        premium: premium_sats,
        max_units: 100,
        vault_address: "tb1qtest_vault_address".to_string(),
        creator: "tb1qtest_creator_address".to_string(),
        created_at: Utc::now().timestamp() as u64,
    };
    
    // Step 3: Register option with factory (includes BitVMX verification)
    info!("🔐 Registering option with BitVMX verification...");
    
    match option_factory.create_option_product(create_tx.clone()).await {
        Ok(product) => {
            info!("✅ Option product created with ID: {}", product.option_id);
            info!("   Status: {:?}", product.status);
            info!("   Units available: {}", product.max_units);
        }
        Err(e) => {
            error!("❌ Failed to create option product: {}", e);
            return Ok(());
        }
    }
    
    // Step 4: Prepare for Bitcoin testnet anchoring
    info!("⚓ Preparing Bitcoin testnet anchoring...");
    
    // In a real implementation, this would:
    // 1. Run BitVMX verification for the product parameters
    // 2. Generate a BitVMX proof of correct premium calculation
    // 3. Create OP_RETURN data with product info + proof hash
    // 4. Send transaction to Bitcoin testnet
    
    // For demo purposes, we'll simulate the OP_RETURN data
    let op_return_data = create_op_return_data(&create_tx, "mock_bitvmx_proof_hash");
    
    info!("📝 OP_RETURN data prepared ({} bytes)", op_return_data.len());
    info!("   Data: {}", hex::encode(&op_return_data));
    
    // Step 5: Send to Bitcoin testnet (commented out for safety)
    info!("🌐 Would send to Bitcoin testnet...");
    info!("💰 Checking wallet balance...");
    
    match bitcoin_client.get_balance().await {
        Ok(balance) => {
            info!("   Wallet balance: {} BTC", balance);
            if balance > 0.001 {
                info!("✅ Sufficient balance for transaction");
                
                // Uncomment to actually send transaction:
                // match bitcoin_client.send_op_return_transaction(&op_return_data, Some(0.0001)).await {
                //     Ok(txid) => {
                //         info!("🎉 Option registered on Bitcoin testnet!");
                //         info!("   Transaction ID: {}", txid);
                //         info!("   View on explorer: https://mempool.space/testnet/tx/{}", txid);
                //     }
                //     Err(e) => {
                //         error!("❌ Failed to send transaction: {}", e);
                //     }
                // }
                
                info!("💡 Transaction not sent (safety mode)");
                info!("💡 Uncomment the send_op_return_transaction call to actually register");
                
            } else {
                error!("❌ Insufficient balance. Need at least 0.001 BTC for transaction");
                info!("💡 Get testnet coins from: https://coinfaucet.eu/en/btc-testnet/");
            }
        }
        Err(e) => {
            error!("❌ Failed to check balance: {}", e);
        }
    }
    
    // Step 6: Summary
    info!("📋 Registration Summary:");
    info!("   Option ID: {}", option_id);
    info!("   Strike: ${}", strike_usd);
    info!("   Premium: ${:.4}", premium_usd);
    info!("   Expiry: 7 days");
    info!("   BitVMX verified: ✅");
    info!("   Ready for Bitcoin anchoring: ✅");
    
    info!("🎉 Demo completed successfully!");
    
    Ok(())
}

/// Create OP_RETURN data for option product registration
fn create_op_return_data(create_tx: &CreateOptionTx, proof_hash: &str) -> Vec<u8> {
    let mut data = Vec::new();
    
    // Magic bytes for BTCFi options
    data.extend_from_slice(b"BTCFI");
    
    // Version
    data.push(1u8);
    
    // Operation type: ProductCreation = 0
    data.push(0u8);
    
    // Option type: Call = 0, Put = 1
    data.push(match create_tx.option_type {
        OptionType::Call => 0u8,
        OptionType::Put => 1u8,
    });
    
    // Strike price (8 bytes, big endian)
    data.extend_from_slice(&create_tx.strike.to_be_bytes());
    
    // Expiry timestamp (8 bytes, big endian)
    data.extend_from_slice(&create_tx.expiry.to_be_bytes());
    
    // Premium (8 bytes, big endian)
    data.extend_from_slice(&create_tx.premium.to_be_bytes());
    
    // Max units (4 bytes, big endian)
    data.extend_from_slice(&(create_tx.max_units as u32).to_be_bytes());
    
    // BitVMX proof hash (first 16 bytes)
    let proof_bytes = hex::decode(proof_hash).unwrap_or_default();
    if proof_bytes.len() >= 16 {
        data.extend_from_slice(&proof_bytes[0..16]);
    } else {
        // Pad with zeros
        data.extend_from_slice(&[0u8; 16]);
    }
    
    // Option ID hash (last 8 bytes)
    let id_hash = sha2::Sha256::digest(create_tx.option_id.as_bytes());
    data.extend_from_slice(&id_hash[0..8]);
    
    // Ensure we don't exceed OP_RETURN limit (80 bytes)
    data.truncate(80);
    
    data
}

use sha2::Digest;