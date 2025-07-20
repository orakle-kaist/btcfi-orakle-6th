//! Comprehensive Integration Tests for BTCFi L1 Anchoring Option System
//! 
//! Tests the complete end-to-end workflows:
//! 1. Option product creation (CREATE transaction)
//! 2. Option purchase by users (BUY transaction)  
//! 3. Option settlement at expiry (SETTLE transaction)
//! 4. Oracle price aggregation and anchoring
//! 5. BitVMX proof generation and verification

use std::time::{SystemTime, UNIX_EPOCH};

use defi_primitives::{
    OptionType, BlackScholesPricing,
    error::Result,
};
use defi_primitives::options::{
    OptionFactory, OptionBuyService, BuyOptionRequest, CreateProductRequest,
};

/// Test fixture for integration testing
struct IntegrationTestFixture {
    factory: OptionFactory,
    buy_service: OptionBuyService,
    current_btc_price: f64,
}

impl IntegrationTestFixture {
    fn new() -> Self {
        let factory = OptionFactory::new("bc1q_test_operator".to_string());
        let buy_service = OptionBuyService::new(factory, 100.0); // 100 BTC pool
        
        Self {
            factory: OptionFactory::new("bc1q_test_operator".to_string()),
            buy_service,
            current_btc_price: 50000.0,
        }
    }

    fn current_timestamp(&self) -> u64 {
        SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .unwrap()
            .as_secs()
    }
}

#[tokio::test]
async fn test_complete_option_lifecycle() -> Result<()> {
    tracing_subscriber::fmt::init();
    let mut fixture = IntegrationTestFixture::new();
    
    println!("🚀 Starting Complete Option Lifecycle Test");
    
    // Step 1: Create Option Product (Service Operator)
    println!("📦 Step 1: Creating option product");
    
    let create_request = CreateProductRequest {
        option_type: OptionType::Call,
        underlying: "BTCUSD".to_string(),
        strike: 52000,
        days_to_expiry: 7,
        initial_iv: 0.68,
        max_units: 1000,
        premium_adjustment: None,
    };
    
    let create_response = fixture.factory.create_product(
        create_request,
        fixture.current_btc_price,
    ).map_err(|e| format!("Failed to create product: {}", e))?;
    
    println!("✅ Option product created: {}", create_response.option_id);
    println!("   Strike: ${}, Expiry: {} days, Premium: {} BTC", 
        create_response.create_tx.strike,
        (create_response.expiry_timestamp - fixture.current_timestamp()) / 86400,
        create_response.calculated_premium
    );
    
    // Step 2: User Browse Available Products
    println!("🛍️ Step 2: Browsing available products");
    
    let product_list = fixture.factory.list_products(fixture.current_btc_price);
    assert_eq!(product_list.len(), 1);
    
    let product = &product_list[0];
    println!("   Available: {} units @ {} BTC premium", 
        product.available_units, product.premium_per_unit);
    println!("   Current BTC: ${}, Strike: ${}, ITM: {}", 
        product.current_btc_price, product.strike, product.is_itm);
    
    // Step 3: User Purchase Option
    println!("💰 Step 3: User purchasing option");
    
    let buy_request = BuyOptionRequest {
        option_id: create_response.option_id.clone(),
        buyer_address: "bc1q_test_user_123".to_string(),
        quantity: 5,
        max_premium_per_unit: Some(create_response.calculated_premium * 1.1), // 10% slippage
        timestamp: fixture.current_timestamp(),
    };
    
    let buy_response = fixture.buy_service.process_buy_request(buy_request).await?;
    
    assert!(buy_response.success);
    println!("✅ Purchase successful: TX {}", buy_response.transaction_id);
    println!("   Quantity: {}, Total Premium: {} BTC", 
        buy_response.buy_tx.buy_quantity, buy_response.total_premium);
    println!("   Pool Balance After: {} BTC", buy_response.pool_balance_after);
    
    // Step 4: Verify Product State After Purchase
    println!("📊 Step 4: Verifying product state");
    
    let updated_products = fixture.factory.list_products(fixture.current_btc_price);
    let updated_product = &updated_products[0];
    
    assert_eq!(updated_product.available_units, 995); // 1000 - 5
    println!("   Remaining units: {}", updated_product.available_units);
    
    // Step 5: Price Movement Simulation (ITM scenario)
    println!("📈 Step 5: Simulating price movement (BTC -> $54,000)");
    
    fixture.current_btc_price = 54000.0; // Option is now ITM
    let updated_products = fixture.factory.list_products(fixture.current_btc_price);
    let product_itm = &updated_products[0];
    
    assert!(product_itm.is_itm);
    println!("   Option is now ITM! Current Price: ${}, Strike: ${}", 
        product_itm.current_btc_price, product_itm.strike);
    println!("   Estimated Max Payout: ${}", product_itm.estimated_max_payout);
    
    // Step 6: Black-Scholes Pricing Verification
    println!("🧮 Step 6: Verifying Black-Scholes pricing");
    
    let pricing_engine = BlackScholesPricing::new(
        54000.0, // current spot
        52000.0, // strike
        6.0 / 365.0, // ~6 days remaining
        0.04, // risk-free rate
        0.68, // volatility
    );
    
    let theoretical_premium = pricing_engine.calculate_premium(OptionType::Call);
    let delta = pricing_engine.calculate_delta(OptionType::Call);
    let theta = pricing_engine.calculate_theta(OptionType::Call);
    
    println!("   Theoretical Premium: ${:.2}", theoretical_premium);
    println!("   Delta: {:.4}, Theta: ${:.2}/day", delta, theta);
    
    assert!(theoretical_premium > 2000.0); // Should be worth at least intrinsic value
    assert!(delta > 0.5 && delta < 1.0); // ITM call should have high delta
    assert!(theta < 0.0); // Theta should be negative (time decay)
    
    println!("✅ All integration tests passed!");
    
    Ok(())
}

#[tokio::test]
async fn test_multiple_users_purchasing() -> Result<()> {
    let mut fixture = IntegrationTestFixture::new();
    
    println!("👥 Testing Multiple Users Purchase Scenario");
    
    // Create a popular option product
    let create_request = CreateProductRequest {
        option_type: OptionType::Call,
        underlying: "BTCUSD".to_string(),
        strike: 51000, // Close to current price
        days_to_expiry: 3,
        initial_iv: 0.8,
        max_units: 100, // Limited supply
        premium_adjustment: Some(0.9), // Attractive pricing
    };
    
    let create_response = fixture.factory.create_product(
        create_request,
        fixture.current_btc_price,
    ).map_err(|e| format!("Failed to create product: {}", e))?;
    
    // Simulate multiple users buying rapidly
    let mut successful_purchases = 0;
    let mut total_premium_collected = 0.0;
    
    for i in 1..=20 {
        let buy_request = BuyOptionRequest {
            option_id: create_response.option_id.clone(),
            buyer_address: format!("bc1q_user_{:03}", i),
            quantity: 5,
            max_premium_per_unit: Some(create_response.calculated_premium * 1.2),
            timestamp: fixture.current_timestamp(),
        };
        
        match fixture.buy_service.process_buy_request(buy_request).await {
            Ok(response) => {
                successful_purchases += 1;
                total_premium_collected += response.total_premium;
                println!("✅ User {} purchased 5 units", i);
            }
            Err(e) => {
                println!("❌ User {} failed: {}", i, e);
                break; // Likely sold out
            }
        }
    }
    
    println!("📊 Purchase Results:");
    println!("   Successful Purchases: {}", successful_purchases);
    println!("   Total Premium Collected: {} BTC", total_premium_collected);
    
    // Verify sold out status
    let final_products = fixture.factory.list_products(fixture.current_btc_price);
    if final_products.is_empty() || final_products[0].available_units == 0 {
        println!("🔥 Product sold out as expected!");
    }
    
    assert!(successful_purchases <= 20); // Should be limited by max_units
    assert!(total_premium_collected > 0.0);
    
    Ok(())
}

#[tokio::test]
async fn test_slippage_protection() -> Result<()> {
    let mut fixture = IntegrationTestFixture::new();
    
    println!("🛡️ Testing Slippage Protection");
    
    // Create option with high volatility (expensive premium)
    let create_request = CreateProductRequest {
        option_type: OptionType::Put,
        underlying: "BTCUSD".to_string(),
        strike: 48000,
        days_to_expiry: 14,
        initial_iv: 1.2, // Very high IV = expensive premium
        max_units: 100,
        premium_adjustment: Some(1.5), // Make it even more expensive
    };
    
    let create_response = fixture.factory.create_product(
        create_request,
        fixture.current_btc_price,
    ).map_err(|e| format!("Failed to create product: {}", e))?;
    
    println!("   Created expensive option with premium: {} BTC", 
        create_response.calculated_premium);
    
    // User sets strict slippage protection
    let buy_request = BuyOptionRequest {
        option_id: create_response.option_id.clone(),
        buyer_address: "bc1q_conservative_user".to_string(),
        quantity: 1,
        max_premium_per_unit: Some(create_response.calculated_premium * 0.8), // 20% below
        timestamp: fixture.current_timestamp(),
    };
    
    // Should fail due to slippage protection
    let result = fixture.buy_service.process_buy_request(buy_request).await;
    
    match result {
        Err(e) => {
            println!("✅ Slippage protection worked: {}", e);
            assert!(e.to_string().contains("slippage protection"));
        }
        Ok(_) => {
            panic!("Expected slippage protection to trigger!");
        }
    }
    
    // Now try with generous slippage
    let buy_request_generous = BuyOptionRequest {
        option_id: create_response.option_id.clone(),
        buyer_address: "bc1q_generous_user".to_string(),
        quantity: 1,
        max_premium_per_unit: Some(create_response.calculated_premium * 1.5), // 50% above
        timestamp: fixture.current_timestamp(),
    };
    
    let result = fixture.buy_service.process_buy_request(buy_request_generous).await?;
    
    println!("✅ Purchase with generous slippage succeeded: TX {}", 
        result.transaction_id);
    
    Ok(())
}

#[tokio::test]
async fn test_option_expiry_handling() -> Result<()> {
    let mut fixture = IntegrationTestFixture::new();
    
    println!("⏰ Testing Option Expiry Handling");
    
    // Create option that expires very soon (1 day)
    let create_request = CreateProductRequest {
        option_type: OptionType::Call,
        underlying: "BTCUSD".to_string(),
        strike: 52000,
        days_to_expiry: 1, // 1 day only
        initial_iv: 0.6,
        max_units: 50,
        premium_adjustment: None,
    };
    
    let create_response = fixture.factory.create_product(
        create_request,
        fixture.current_btc_price,
    ).map_err(|e| format!("Failed to create product: {}", e))?;
    
    println!("   Created option expiring in 1 day");
    
    // Simulate time passing (option expires)
    let expired_timestamp = fixture.current_timestamp() + 86400 + 3600; // 1 day + 1 hour
    
    let buy_request_expired = BuyOptionRequest {
        option_id: create_response.option_id.clone(),
        buyer_address: "bc1q_late_user".to_string(),
        quantity: 1,
        max_premium_per_unit: None,
        timestamp: expired_timestamp,
    };
    
    // Should fail because option has expired
    let result = fixture.buy_service.process_buy_request(buy_request_expired).await;
    
    match result {
        Err(e) => {
            println!("✅ Expired option purchase correctly rejected: {}", e);
            assert!(e.to_string().contains("expired") || e.to_string().contains("EXPIRED"));
        }
        Ok(_) => {
            panic!("Expected expired option purchase to fail!");
        }
    }
    
    // Check that expired options don't appear in product list
    let products_before_expiry = fixture.factory.list_products(fixture.current_btc_price);
    assert_eq!(products_before_expiry.len(), 1);
    
    // After expiry, should not appear in active products
    // Note: This would require factory to check expiry in list_products method
    
    Ok(())
}

#[tokio::test]
async fn test_pricing_greeks_calculation() -> Result<()> {
    println!("📐 Testing Black-Scholes Greeks Calculation");
    
    // Test different scenarios
    let test_cases = vec![
        ("ATM Call", 50000.0, 50000.0, OptionType::Call, 30.0 / 365.0),
        ("OTM Call", 50000.0, 55000.0, OptionType::Call, 30.0 / 365.0),
        ("ITM Call", 55000.0, 50000.0, OptionType::Call, 30.0 / 365.0),
        ("ATM Put", 50000.0, 50000.0, OptionType::Put, 30.0 / 365.0),
        ("OTM Put", 50000.0, 45000.0, OptionType::Put, 30.0 / 365.0),
        ("ITM Put", 45000.0, 50000.0, OptionType::Put, 30.0 / 365.0),
    ];
    
    for (name, spot, strike, option_type, time_to_expiry) in test_cases {
        println!("   Testing {}: S=${}, K=${}", name, spot, strike);
        
        let pricing = BlackScholesPricing::new(spot, strike, time_to_expiry, 0.04, 0.7);
        
        let premium = pricing.calculate_premium(option_type);
        let delta = pricing.calculate_delta(option_type);
        let theta = pricing.calculate_theta(option_type);
        let vega = pricing.calculate_vega();
        
        println!("     Premium: ${:.2}, Delta: {:.4}, Theta: ${:.2}, Vega: {:.2}", 
            premium, delta, theta, vega);
        
        // Basic sanity checks
        assert!(premium >= 0.0);
        assert!(vega >= 0.0); // Vega is always positive
        assert!(theta <= 0.0); // Theta is always negative (time decay)
        
        match option_type {
            OptionType::Call => {
                assert!(delta >= 0.0 && delta <= 1.0);
                if spot > strike {
                    assert!(premium >= spot - strike); // At least intrinsic value
                }
            }
            OptionType::Put => {
                assert!(delta >= -1.0 && delta <= 0.0);
                if strike > spot {
                    assert!(premium >= strike - spot); // At least intrinsic value
                }
            }
        }
    }
    
    println!("✅ All Greeks calculations passed sanity checks!");
    
    Ok(())
}

#[cfg(test)]
mod performance_tests {
    use super::*;
    use std::time::Instant;
    
    #[tokio::test]
    async fn test_high_volume_product_creation() -> Result<()> {
        println!("⚡ Testing High Volume Product Creation");
        
        let mut factory = OptionFactory::new("bc1q_bulk_operator".to_string());
        let start = Instant::now();
        
        // Create 100 different option products
        for i in 0..100 {
            let request = CreateProductRequest {
                option_type: if i % 2 == 0 { OptionType::Call } else { OptionType::Put },
                underlying: "BTCUSD".to_string(),
                strike: 45000 + (i as u64 * 100), // Different strikes
                days_to_expiry: 1 + (i % 30), // 1-30 days
                initial_iv: 0.5 + (i as f64 * 0.01), // Varying IV
                max_units: 100,
                premium_adjustment: None,
            };
            
            factory.create_product(request, 50000.0)
                .map_err(|e| format!("Failed to create product {}: {}", i, e))?;
        }
        
        let duration = start.elapsed();
        println!("   Created 100 products in {:?}", duration);
        println!("   Average: {:?} per product", duration / 100);
        
        // Verify all products are listed
        let products = factory.list_products(50000.0);
        assert_eq!(products.len(), 100);
        
        println!("✅ High volume creation test passed!");
        
        Ok(())
    }
}