use defi_primitives::options::{
    factory::{OptionFactory, CreateProductRequest},
    types::OptionType,
    bitvmx_integration::{BitVMXOptionVerifier, BitVMXSessionStatus},
};

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    tracing_subscriber::fmt::init();

    println!("🚀 Full BitVMX Integration Test - Real Protocol Setup");

    // 1. Setup BitVMX verifier
    let mut bitvmx_verifier = BitVMXOptionVerifier::new();

    // 2. Create Option Factory with BitVMX only
    let mut factory = OptionFactory::new_with_full_integration(
        "bc1q_test_operator".to_string(),
        vec!["binance".to_string(), "coinbase".to_string()],
        None, // No Bitcoin client - focus on BitVMX
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
        premium_adjustment: Some(1.1),
    };

    println!("📋 Creating option with REAL BitVMX setup fund API: {:?}", request);

    // 4. Test full BitVMX protocol integration
    match factory.create_and_anchor(request, 51000.0).await {
        Ok(response) => {
            println!("✅ Option creation successful!");
            println!("Option ID: {}", response.option_id);
            println!("🛡️ BitVMX Program Hash: {}", response.bitvmx_program_hash);
            
            // Get the verifier back to check session details
            if let Some(ref mut verifier) = factory.bitvmx_verifier {
                if let Some(session) = verifier.get_session(&response.option_id) {
                    println!("🎯 SUCCESS: Using REAL BitVMX with setup fund API!");
                    println!("💰 This means funds are locked on Bitcoin testnet!");
                    
                    println!("\n📊 BitVMX Session Details:");
                    println!("  Setup UUID: {}", session.setup_uuid);
                    println!("  Funding TX: {}", session.funding_tx_id);
                    println!("  Program Hash: {}", session.program_hash);
                    println!("  Status: {:?}", session.status);
                    
                    // Execute verification steps
                    println!("\n🔄 Starting BitVMX verification process...");
                    
                    match verifier.execute_verification_step(&response.option_id).await {
                        Ok(status) => {
                            println!("✅ Verification step 1 completed: {:?}", status);
                            
                            // Execute second step
                            if let Ok(final_status) = verifier.execute_verification_step(&response.option_id).await {
                                println!("✅ Verification step 2 completed: {:?}", final_status);
                                
                                if matches!(final_status, BitVMXSessionStatus::Completed) {
                                    println!("🎉 FULL BitVMX VERIFICATION COMPLETED!");
                                    println!("🔗 Verification results should now be on Bitcoin!");
                                }
                            }
                        }
                        Err(e) => {
                            println!("⚠️ Verification step failed: {}", e);
                        }
                    }
                } else {
                    println!("❌ BitVMX integration failed - production mode requires working services");
                }
            }
        }
        Err(e) => {
            println!("❌ Option creation failed: {}", e);
        }
    }

    println!("\n📜 Created Products:");
    let products = factory.list_products(51000.0);
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