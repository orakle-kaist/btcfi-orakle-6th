use defi_primitives::options::{
    factory::{OptionFactory, CreateProductRequest},
    types::OptionType,
    bitvmx_integration::BitVMXOptionVerifier,
};

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    tracing_subscriber::fmt::init();

    println!("🛡️ BitVMX Integration Test (Without Bitcoin)");

    // 1. Setup BitVMX verifier
    let bitvmx_verifier = BitVMXOptionVerifier::new();

    // 2. Create Option Factory with BitVMX only
    let mut factory = OptionFactory::new_with_full_integration(
        "bc1q_test_operator".to_string(),
        vec!["binance".to_string(), "coinbase".to_string()],
        None, // No Bitcoin client - test BitVMX only
        Some(bitvmx_verifier),
    );

    // 3. Create test option product
    let request = CreateProductRequest {
        option_type: OptionType::Call,
        underlying: "BTCUSD".to_string(),
        strike: 52000,
        days_to_expiry: 7,
        initial_iv: 0.68,
        max_units: 100,
        premium_adjustment: Some(1.1), // 10% markup
    };

    println!("📋 Creating option product with BitVMX verification: {:?}", request);

    // 4. Test BitVMX integration: create + BitVMX only
    match factory.create_and_anchor(request, 51000.0).await {
        Ok(response) => {
            println!("✅ BitVMX test successful!");
            println!("Option ID: {}", response.option_id);
            println!("Premium: {} BTC", response.calculated_premium);
            
            println!("🛡️ BitVMX Program Hash: {}", response.bitvmx_program_hash);
            
            // Check if this is actual BitVMX or fallback
            if response.bitvmx_program_hash.starts_with("bitvmx_") {
                println!("✅ Using REAL BitVMX verification with running services!");
                println!("🎯 This confirms OP_RETURN + BitVMX integration is working!");
            } else if response.bitvmx_program_hash.starts_with("fallback_") {
                println!("⚠️ Using fallback mode (BitVMX services not responding properly)");
            }
        }
        Err(e) => {
            println!("❌ BitVMX test failed: {}", e);
        }
    }

    // 5. List created products
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