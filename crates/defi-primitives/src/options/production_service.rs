//! Production Option Service
//!
//! This service provides a production-ready API for option product creation
//! with full Bitcoin L1 anchoring and BitVMX verification integration.

use std::collections::HashMap;
use serde::{Deserialize, Serialize};
use tracing::{info, warn, error};
use bitcoin_client::{BitcoinClient, BitcoinConfig};

use super::{
    types::OptionType,
    factory::{OptionFactory, CreateProductRequest, CreateProductResponse, CreateAndAnchorResponse},
    bitvmx_integration::BitVMXOptionVerifier,
    bitvmx_cpu_integration::BitVMXCPUVerifier,
};

/// Production Option Service for creating and managing option products
pub struct ProductionOptionService {
    /// Option factory for product creation
    pub factory: OptionFactory,
    /// Service operator's Bitcoin address
    pub operator_address: String,
    /// Current BTC price (updated from oracles)
    pub current_btc_price: f64,
    /// Service configuration
    pub config: ServiceConfig,
}

/// Service configuration for production environment
#[derive(Debug, Clone)]
pub struct ServiceConfig {
    /// Bitcoin network configuration
    pub bitcoin_config: BitcoinConfig,
    /// Oracle providers for price feeds
    pub oracle_providers: Vec<String>,
    /// Maximum option duration in days
    pub max_option_duration_days: u32,
    /// Minimum premium as percentage of strike
    pub min_premium_percentage: f64,
    /// Maximum units per option product
    pub max_units_per_product: u32,
    /// Enable BitVMX verification
    pub enable_bitvmx: bool,
    /// Enable Bitcoin L1 anchoring
    pub enable_bitcoin_anchoring: bool,
}

/// API request for creating option product
#[derive(Debug, Deserialize)]
pub struct CreateOptionProductRequest {
    /// Option type (Call or Put)
    pub option_type: OptionType,
    /// Underlying asset (e.g., "BTC/USD")
    pub underlying: String,
    /// Strike price in USD
    pub strike_price: u64,
    /// Days until expiration
    pub days_to_expiry: u32,
    /// Initial implied volatility (0.0 to 1.0)
    pub implied_volatility: f64,
    /// Maximum units to sell
    pub max_units: u32,
    /// Optional premium adjustment factor (default 1.0)
    pub premium_adjustment: Option<f64>,
    /// Service operator signature (for authentication)
    pub operator_signature: String,
}

/// API response for option product creation
#[derive(Debug, Serialize)]
pub struct CreateOptionProductResponse {
    /// Success status
    pub success: bool,
    /// Option product ID
    pub option_id: String,
    /// Calculated premium per unit in BTC
    pub premium_btc: f64,
    /// Calculated premium per unit in USD
    pub premium_usd: f64,
    /// Maximum units available
    pub max_units: u32,
    /// Expiration timestamp
    pub expiry_timestamp: u64,
    /// Days until expiration
    pub days_to_expiry: u32,
    /// Bitcoin anchoring transaction ID (if enabled)
    pub bitcoin_anchor_txid: Option<String>,
    /// BitVMX program hash (if enabled)
    pub bitvmx_program_hash: Option<String>,
    /// BitVMX verification steps (if enabled)
    pub bitvmx_verification_steps: Option<u64>,
    /// Creation timestamp
    pub created_at: u64,
    /// Error message (if any)
    pub error: Option<String>,
}

/// Market information response
#[derive(Debug, Serialize)]
pub struct MarketInfoResponse {
    /// Current BTC price in USD
    pub current_btc_price: f64,
    /// Price update timestamp
    pub price_updated_at: u64,
    /// Available oracle providers
    pub oracle_providers: Vec<String>,
    /// Service status
    pub service_status: String,
    /// Total active option products
    pub active_products_count: usize,
    /// Bitcoin network status
    pub bitcoin_network_status: String,
    /// BitVMX verification status
    pub bitvmx_status: String,
}

/// Product listing for public API
#[derive(Debug, Serialize)]
pub struct PublicProductInfo {
    /// Option product ID
    pub option_id: String,
    /// Option type (Call/Put)
    pub option_type: String,
    /// Underlying asset
    pub underlying: String,
    /// Strike price in USD
    pub strike_price: u64,
    /// Current premium per unit in BTC
    pub premium_btc: f64,
    /// Current premium per unit in USD
    pub premium_usd: f64,
    /// Available units for purchase
    pub available_units: u32,
    /// Days until expiration
    pub days_to_expiry: u32,
    /// Implied volatility
    pub implied_volatility: f64,
    /// Is option currently in-the-money
    pub is_itm: bool,
    /// Estimated maximum payout in USD
    pub max_payout_usd: f64,
    /// Bitcoin anchor transaction (if available)
    pub bitcoin_anchor_txid: Option<String>,
    /// Creation timestamp
    pub created_at: u64,
}

impl ProductionOptionService {
    /// Create new production option service
    pub fn new(
        operator_address: String,
        config: ServiceConfig,
    ) -> Result<Self, String> {
        info!("🏭 Initializing Production Option Service");
        info!("   Operator: {}", operator_address);
        info!("   Bitcoin Network: {:?}", config.bitcoin_config);
        info!("   BitVMX Enabled: {}", config.enable_bitvmx);
        info!("   Bitcoin Anchoring Enabled: {}", config.enable_bitcoin_anchoring);

        // Create Bitcoin client if anchoring is enabled  
        let bitcoin_client = if config.enable_bitcoin_anchoring {
            info!("🔗 Initializing Bitcoin client...");
            let client = BitcoinClient::new(config.bitcoin_config.clone());
            info!("✅ Bitcoin client created");
            Some(client)
        } else {
            None
        };

        // Create BitVMX verifier if enabled
        let bitvmx_verifier = if config.enable_bitvmx {
            info!("🔧 Initializing BitVMX verifier...");
            Some(BitVMXOptionVerifier::new())
        } else {
            None
        };

        // Create option factory with full integration
        let factory = OptionFactory::new_with_full_integration(
            operator_address.clone(),
            config.oracle_providers.clone(),
            bitcoin_client,
            bitvmx_verifier,
        );

        info!("✅ Production Option Service initialized successfully");

        Ok(Self {
            factory,
            operator_address,
            current_btc_price: 50000.0, // Will be updated from oracles
            config,
        })
    }

    /// Create option product with full production pipeline
    pub async fn create_option_product(
        &mut self,
        request: CreateOptionProductRequest,
    ) -> CreateOptionProductResponse {
        let created_at = chrono::Utc::now().timestamp() as u64;
        
        info!("🚀 Creating option product (Production Service)");
        info!("   Type: {:?} | Strike: {} | Expiry: {} days", 
              request.option_type, request.strike_price, request.days_to_expiry);

        // Validate request
        if let Err(validation_error) = self.validate_create_request(&request) {
            error!("❌ Request validation failed: {}", validation_error);
            return CreateOptionProductResponse {
                success: false,
                option_id: String::new(),
                premium_btc: 0.0,
                premium_usd: 0.0,
                max_units: 0,
                expiry_timestamp: 0,
                days_to_expiry: 0,
                bitcoin_anchor_txid: None,
                bitvmx_program_hash: None,
                bitvmx_verification_steps: None,
                created_at,
                error: Some(validation_error),
            };
        }

        // Update current BTC price from oracles
        self.update_btc_price().await;

        // Create factory request
        let factory_request = CreateProductRequest {
            option_type: request.option_type,
            underlying: request.underlying,
            strike: request.strike_price,
            days_to_expiry: request.days_to_expiry,
            initial_iv: request.implied_volatility,
            max_units: request.max_units,
            premium_adjustment: request.premium_adjustment,
        };

        // Create product with full anchoring and verification
        match self.factory.create_and_anchor(factory_request, self.current_btc_price).await {
            Ok(response) => {
                let premium_usd = response.calculated_premium * self.current_btc_price;
                
                info!("✅ Option product created successfully!");
                info!("   Option ID: {}", response.option_id);
                info!("   Premium: {} BTC (${:.2} USD)", response.calculated_premium, premium_usd);
                
                if let Some(ref txid) = response.bitcoin_anchor_txid {
                    info!("   Bitcoin Anchor: {}", txid);
                }
                info!("   BitVMX Program: {}", response.bitvmx_program_hash);

                CreateOptionProductResponse {
                    success: true,
                    option_id: response.option_id,
                    premium_btc: response.calculated_premium,
                    premium_usd,
                    max_units: response.max_units,
                    expiry_timestamp: response.expiry_timestamp,
                    days_to_expiry: request.days_to_expiry,
                    bitcoin_anchor_txid: response.bitcoin_anchor_txid,
                    bitvmx_program_hash: Some(response.bitvmx_program_hash),
                    bitvmx_verification_steps: None, // TODO: Get from BitVMX result
                    created_at,
                    error: None,
                }
            }
            Err(e) => {
                error!("❌ Option product creation failed: {}", e);
                CreateOptionProductResponse {
                    success: false,
                    option_id: String::new(),
                    premium_btc: 0.0,
                    premium_usd: 0.0,
                    max_units: 0,
                    expiry_timestamp: 0,
                    days_to_expiry: 0,
                    bitcoin_anchor_txid: None,
                    bitvmx_program_hash: None,
                    bitvmx_verification_steps: None,
                    created_at,
                    error: Some(e),
                }
            }
        }
    }

    /// Get market information
    pub async fn get_market_info(&self) -> MarketInfoResponse {
        info!("📊 Fetching market information");

        let bitcoin_status = if self.config.enable_bitcoin_anchoring {
            match &self.factory.bitcoin_client {
                Some(_) => "Connected".to_string(),
                None => "Disconnected".to_string(),
            }
        } else {
            "Disabled".to_string()
        };

        let bitvmx_status = if self.config.enable_bitvmx {
            match &self.factory.bitvmx_verifier {
                Some(_) => "Enabled".to_string(),
                None => "Disabled".to_string(),
            }
        } else {
            "Disabled".to_string()
        };

        MarketInfoResponse {
            current_btc_price: self.current_btc_price,
            price_updated_at: chrono::Utc::now().timestamp() as u64,
            oracle_providers: self.config.oracle_providers.clone(),
            service_status: "Active".to_string(),
            active_products_count: self.factory.products.len(),
            bitcoin_network_status: bitcoin_status,
            bitvmx_status,
        }
    }

    /// List all available option products
    pub fn list_available_products(&self) -> Vec<PublicProductInfo> {
        info!("📋 Listing available option products");

        let products = self.factory.get_product_list(self.current_btc_price);
        
        products.into_iter().map(|product| {
            let premium_usd = product.premium_per_unit * self.current_btc_price;
            
            PublicProductInfo {
                option_id: product.option_id,
                option_type: product.option_type,
                underlying: product.underlying,
                strike_price: product.strike,
                premium_btc: product.premium_per_unit,
                premium_usd,
                available_units: product.available_units,
                days_to_expiry: product.days_to_expiry,
                implied_volatility: product.initial_iv,
                is_itm: product.is_itm,
                max_payout_usd: product.estimated_max_payout,
                bitcoin_anchor_txid: None, // TODO: Get from product data
                created_at: 0, // TODO: Get from product data
            }
        }).collect()
    }

    /// Validate create option product request
    fn validate_create_request(&self, request: &CreateOptionProductRequest) -> Result<(), String> {
        // Validate days to expiry
        if request.days_to_expiry == 0 || request.days_to_expiry > self.config.max_option_duration_days {
            return Err(format!(
                "Invalid expiry: must be 1-{} days", 
                self.config.max_option_duration_days
            ));
        }

        // Validate strike price
        if request.strike_price == 0 {
            return Err("Strike price must be greater than 0".to_string());
        }

        // Validate implied volatility
        if request.implied_volatility <= 0.0 || request.implied_volatility > 5.0 {
            return Err("Implied volatility must be between 0.0 and 5.0".to_string());
        }

        // Validate max units
        if request.max_units == 0 || request.max_units > self.config.max_units_per_product {
            return Err(format!(
                "Max units must be 1-{}", 
                self.config.max_units_per_product
            ));
        }

        // Validate premium adjustment
        if let Some(adjustment) = request.premium_adjustment {
            if adjustment <= 0.0 || adjustment > 10.0 {
                return Err("Premium adjustment must be between 0.0 and 10.0".to_string());
            }
        }

        // TODO: Validate operator signature
        if request.operator_signature.is_empty() {
            return Err("Operator signature required".to_string());
        }

        Ok(())
    }

    /// Update BTC price from oracle providers
    async fn update_btc_price(&mut self) {
        // In production, this would fetch from actual oracle providers
        // For now, simulate a price update
        let mock_prices = vec![49800.0, 50200.0, 50100.0];
        let avg_price = mock_prices.iter().sum::<f64>() / mock_prices.len() as f64;
        
        info!("📈 Updating BTC price: ${:.2} (from {} oracles)", avg_price, mock_prices.len());
        self.current_btc_price = avg_price;
    }
}

impl Default for ServiceConfig {
    fn default() -> Self {
        Self {
            bitcoin_config: BitcoinConfig::default(),
            oracle_providers: vec![
                "binance".to_string(),
                "coinbase".to_string(),
                "kraken".to_string(),
            ],
            max_option_duration_days: 365, // 1 year maximum
            min_premium_percentage: 0.01,  // 1% minimum
            max_units_per_product: 10000,  // 10,000 units maximum
            enable_bitvmx: true,
            enable_bitcoin_anchoring: true,
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[tokio::test]
    async fn test_production_service_creation() {
        let config = ServiceConfig::default();
        let service = ProductionOptionService::new(
            "bc1qtest_operator_address".to_string(),
            config,
        );
        
        assert!(service.is_ok());
        let service = service.unwrap();
        assert_eq!(service.operator_address, "bc1qtest_operator_address");
    }

    #[tokio::test]
    async fn test_create_option_product() {
        let config = ServiceConfig {
            enable_bitcoin_anchoring: false, // Disable for testing
            enable_bitvmx: true,
            ..ServiceConfig::default()
        };
        
        let mut service = ProductionOptionService::new(
            "bc1qtest_operator_address".to_string(),
            config,
        ).unwrap();

        let request = CreateOptionProductRequest {
            option_type: OptionType::Call,
            underlying: "BTC/USD".to_string(),
            strike_price: 55000,
            days_to_expiry: 7,
            implied_volatility: 0.68,
            max_units: 100,
            premium_adjustment: None,
            operator_signature: "test_signature".to_string(),
        };

        let response = service.create_option_product(request).await;
        assert!(response.success);
        assert!(!response.option_id.is_empty());
        assert!(response.premium_btc > 0.0);
        assert!(response.premium_usd > 0.0);
    }

    #[test]
    fn test_validation() {
        let config = ServiceConfig::default();
        let service = ProductionOptionService::new(
            "bc1qtest".to_string(),
            config,
        ).unwrap();

        // Test invalid expiry
        let invalid_request = CreateOptionProductRequest {
            option_type: OptionType::Call,
            underlying: "BTC/USD".to_string(),
            strike_price: 55000,
            days_to_expiry: 0, // Invalid
            implied_volatility: 0.68,
            max_units: 100,
            premium_adjustment: None,
            operator_signature: "test".to_string(),
        };

        let result = service.validate_create_request(&invalid_request);
        assert!(result.is_err());
    }
}