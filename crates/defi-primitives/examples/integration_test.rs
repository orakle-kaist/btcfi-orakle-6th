use bitcoin_client::{BitcoinClient, BitcoinConfig};
use defi_primitives::options::{
    factory::{OptionFactory, CreateProductRequest},
    types::OptionType,
    bitvmx_integration::BitVMXOptionVerifier,
};

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    tracing_subscriber::fmt::init();

    println!("🚀 BTCFi L1 Anchoring Option System Integration Test");

    // 1. Setup Bitcoin client (regtest)
    let bitcoin_config = BitcoinConfig {
        rpc_url: "http://localhost:18443".to_string(),
        rpc_user: "rpcuser".to_string(),
        rpc_password: "rpcpass".to_string(),
        wallet_name: Some("testwallet".to_string()),
        network: bitcoin_client::Network::Regtest,
    };
    let bitcoin_client = BitcoinClient::new(bitcoin_config);

    // 2. Setup BitVMX verifier
    let bitvmx_verifier = BitVMXOptionVerifier::new();

    // 3. Create Option Factory with full integration
    let mut factory = OptionFactory::new_with_full_integration(
        "bc1q_test_operator".to_string(),
        vec!["binance".to_string(), "coinbase".to_string()],
        Some(bitcoin_client),
        Some(bitvmx_verifier),
    );

    // 4. Create test option product
    let request = CreateProductRequest {
        option_type: OptionType::Call,
        underlying: "BTCUSD".to_string(),
        strike: 52000,
        days_to_expiry: 7,
        initial_iv: 0.68,
        max_units: 100,
        premium_adjustment: Some(1.1), // 10% markup
    };

    println!("📋 Creating option product with request: {:?}", request);

    // 5. Test full integration: create + anchor + BitVMX
    match factory.create_and_anchor(request, 51000.0).await {
        Ok(response) => {
            println!("✅ Integration test successful!");
            println!("Option ID: {}", response.option_id);
            println!("Premium: {} BTC", response.calculated_premium);
            
            if let Some(txid) = &response.bitcoin_anchor_txid {
                println!("🔗 Bitcoin L1 Anchor: {}", txid);
            }
            
            println!("🛡️ BitVMX Program Hash: {}", response.bitvmx_program_hash);
            
            // Check if this is actual BitVMX or fallback
            if response.bitvmx_program_hash.starts_with("bitvmx_") {
                println!("✅ Using REAL BitVMX verification!");
            } else if response.bitvmx_program_hash.starts_with("fallback_") {
                println!("⚠️ Using fallback mode (BitVMX services not responding)");
            }
        }
        Err(e) => {
            println!("❌ Integration test failed: {}", e);
        }
    }

    // 6. List created products
    let products = factory.list_products(51000.0);
    println!("\n📜 Created Products:");
    for product in products {
        println!("  - {} {} @{} (Premium: {} BTC, Available: {} units)", 
            product.option_type, 
            product.strike,
            product.underlying,
            product.premium_per_unit,
            product.available_units
        );
    }

    Ok(())
}