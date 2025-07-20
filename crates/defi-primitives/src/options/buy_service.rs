//! Buy Option Service
//! 
//! Handles option purchase transactions and validation

use std::collections::HashMap;
use serde::{Deserialize, Serialize};
use tracing::{info, warn, error};

use super::{
    OptionFactory, BuyOptionTx, OptionTransaction, 
    BlackScholesPricing, OptionType
};
use crate::error::{Result, DefiError};

/// Buy option request from user
#[derive(Debug, Deserialize)]
pub struct BuyOptionRequest {
    pub option_id: String,
    pub buyer_address: String,
    pub quantity: u64,
    pub max_premium_per_unit: Option<f64>, // Slippage protection
    pub timestamp: u64,
}

/// Buy option response
#[derive(Debug, Serialize)]
pub struct BuyOptionResponse {
    pub success: bool,
    pub transaction_id: String,
    pub buy_tx: BuyOptionTx,
    pub total_premium: f64,
    pub estimated_pnl: Option<f64>, // If option is in-the-money
    pub pool_balance_after: f64,
    pub presigned_settlement: Option<PresignedSettlementInfo>, // BitVMX guarantee
}

/// Pre-signed settlement information for user
#[derive(Debug, Serialize)]
pub struct PresignedSettlementInfo {
    pub settlement_txid: String,
    pub program_hash: String,
    pub max_payout: f64,
    pub expiry: u64,
    pub verification_url: String,
}

/// Buy option validation error
#[derive(Debug, Serialize)]
pub struct BuyValidationError {
    pub error_type: String,
    pub message: String,
    pub max_available_quantity: Option<u64>,
    pub current_premium: Option<f64>,
}

/// Option buying service
pub struct OptionBuyService {
    factory: OptionFactory,
    pricing_engine: BlackScholesPricing,
    pool_balance: f64,
    active_positions: HashMap<String, Vec<UserPosition>>, // option_id -> positions
}

/// User's option position
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct UserPosition {
    pub buyer: String,
    pub quantity: u64,
    pub premium_paid: f64,
    pub buy_timestamp: u64,
    pub option_id: String,
}

impl OptionBuyService {
    /// Create new buy service
    pub fn new(factory: OptionFactory, initial_pool_balance: f64) -> Self {
        Self {
            factory,
            pricing_engine: BlackScholesPricing::default(),
            pool_balance: initial_pool_balance,
            active_positions: HashMap::new(),
        }
    }

    /// Process buy option request
    pub async fn process_buy_request(
        &mut self, 
        request: BuyOptionRequest
    ) -> Result<BuyOptionResponse> {
        info!("🛒 Processing buy request for option: {}", request.option_id);

        // Validate request
        let validation = self.validate_buy_request(&request).await?;
        if let Some(error) = validation {
            return Err(format!("Buy validation failed: {}", error.message).into());
        }

        // Get option product
        let product = self.factory.get_product(&request.option_id)
            .ok_or_else(|| format!("Option product not found: {}", request.option_id))?;

        // Calculate current premium
        let current_premium = self.calculate_current_premium(&product, request.timestamp)?;

        // Check slippage protection
        if let Some(max_premium) = request.max_premium_per_unit {
            if current_premium > max_premium {
                return Err(format!(
                    "Premium {} exceeds maximum {} (slippage protection)", 
                    current_premium, max_premium
                ).into());
            }
        }

        let total_premium = current_premium * request.quantity as f64;

        // Update pool balance
        self.pool_balance += total_premium;

        // Create buy transaction
        let transaction_id = self.generate_transaction_id(&request);
        let buy_tx = BuyOptionTx::new(
            request.option_id.clone(),
            request.buyer_address.clone(),
            request.quantity,
            current_premium,
            transaction_id.clone(),
            self.pool_balance,
            request.timestamp,
        );

        // Record position
        let position = UserPosition {
            buyer: request.buyer_address.clone(),
            quantity: request.quantity,
            premium_paid: total_premium,
            buy_timestamp: request.timestamp,
            option_id: request.option_id.clone(),
        };

        self.active_positions
            .entry(request.option_id.clone())
            .or_insert_with(Vec::new)
            .push(position);

        // Calculate estimated P&L (if option is in-the-money)
        let estimated_pnl = self.calculate_estimated_pnl(&product, request.quantity, current_premium);

        info!(
            "✅ Buy transaction created: {} units at {} premium (total: {})", 
            request.quantity, current_premium, total_premium
        );

        Ok(BuyOptionResponse {
            success: true,
            transaction_id,
            buy_tx,
            total_premium,
            estimated_pnl,
            pool_balance_after: self.pool_balance,
            presigned_settlement: None, // TODO: Integrate BitVMX pre-sign
        })
    }

    /// Validate buy request
    async fn validate_buy_request(
        &self, 
        request: &BuyOptionRequest
    ) -> Result<Option<BuyValidationError>> {
        // Check if option exists
        let product = match self.factory.get_product(&request.option_id) {
            Some(p) => p,
            None => {
                return Ok(Some(BuyValidationError {
                    error_type: "OPTION_NOT_FOUND".to_string(),
                    message: format!("Option {} does not exist", request.option_id),
                    max_available_quantity: None,
                    current_premium: None,
                }));
            }
        };

        // Check if option is active
        if !product.is_active() {
            return Ok(Some(BuyValidationError {
                error_type: "OPTION_INACTIVE".to_string(),
                message: "Option is not active for trading".to_string(),
                max_available_quantity: None,
                current_premium: None,
            }));
        }

        // Check if option has expired
        if request.timestamp > product.create_tx.expiry {
            return Ok(Some(BuyValidationError {
                error_type: "OPTION_EXPIRED".to_string(),
                message: "Option has already expired".to_string(),
                max_available_quantity: None,
                current_premium: None,
            }));
        }

        // Check minimum quantity
        if request.quantity == 0 {
            return Ok(Some(BuyValidationError {
                error_type: "INVALID_QUANTITY".to_string(),
                message: "Quantity must be greater than 0".to_string(),
                max_available_quantity: Some(1000), // Example max
                current_premium: None,
            }));
        }

        // Check maximum quantity (pool risk management)
        let max_quantity = self.calculate_max_available_quantity(&product);
        if request.quantity > max_quantity {
            let current_premium = self.calculate_current_premium(&product, request.timestamp)?;
            return Ok(Some(BuyValidationError {
                error_type: "QUANTITY_EXCEEDS_LIMIT".to_string(),
                message: format!("Requested quantity {} exceeds maximum {}", request.quantity, max_quantity),
                max_available_quantity: Some(max_quantity),
                current_premium: Some(current_premium),
            }));
        }

        // Check if buyer address is valid
        if request.buyer_address.is_empty() || !self.is_valid_bitcoin_address(&request.buyer_address) {
            return Ok(Some(BuyValidationError {
                error_type: "INVALID_BUYER_ADDRESS".to_string(),
                message: "Invalid buyer Bitcoin address".to_string(),
                max_available_quantity: None,
                current_premium: None,
            }));
        }

        Ok(None) // All validations passed
    }

    /// Calculate current premium for the option
    fn calculate_current_premium(&self, product: &super::OptionProduct, timestamp: u64) -> Result<f64> {
        let time_to_expiry = if product.create_tx.expiry > timestamp {
            (product.create_tx.expiry - timestamp) as f64 / (365.25 * 24.0 * 3600.0) // Convert to years
        } else {
            0.0 // Expired
        };

        // Use current BTC price (should be fetched from oracle)
        let current_price = 50000.0; // TODO: Get from oracle service

        // Update pricing engine with current parameters
        let mut updated_engine = self.pricing_engine.clone();
        updated_engine.spot = current_price;
        updated_engine.strike = product.create_tx.strike as f64;
        updated_engine.time_to_expiry = time_to_expiry;
        updated_engine.risk_free_rate = 0.04;
        updated_engine.volatility = product.create_tx.initial_iv;

        let premium = updated_engine.calculate_premium(product.create_tx.option_type);

        Ok(premium)
    }

    /// Calculate maximum available quantity based on pool risk
    fn calculate_max_available_quantity(&self, product: &super::OptionProduct) -> u64 {
        // Simple risk management: limit exposure based on pool balance
        let max_exposure_ratio = 0.1; // Max 10% of pool per option
        let max_exposure = self.pool_balance * max_exposure_ratio;
        
        // Estimate maximum units based on strike and current price
        let estimated_max_payout = product.create_tx.strike as f64 * 0.2; // Assume max 20% ITM
        let max_units = (max_exposure / estimated_max_payout).floor() as u64;
        
        std::cmp::max(1, std::cmp::min(max_units, 1000)) // Between 1 and 1000
    }

    /// Calculate estimated P&L if option were to expire now
    fn calculate_estimated_pnl(
        &self, 
        product: &super::OptionProduct, 
        quantity: u64,
        premium_paid_per_unit: f64
    ) -> Option<f64> {
        let current_price = 50000.0; // TODO: Get from oracle
        
        let intrinsic_value = match product.create_tx.option_type {
            OptionType::Call => {
                if current_price > product.create_tx.strike as f64 {
                    current_price - product.create_tx.strike as f64
                } else {
                    0.0
                }
            }
            OptionType::Put => {
                if product.create_tx.strike as f64 > current_price {
                    product.create_tx.strike as f64 - current_price
                } else {
                    0.0
                }
            }
        };

        if intrinsic_value > 0.0 {
            let total_premium_paid = premium_paid_per_unit * quantity as f64;
            let total_intrinsic_value = intrinsic_value * quantity as f64;
            Some(total_intrinsic_value - total_premium_paid)
        } else {
            Some(-premium_paid_per_unit * quantity as f64) // Premium loss
        }
    }

    /// Generate unique transaction ID
    fn generate_transaction_id(&self, request: &BuyOptionRequest) -> String {
        format!(
            "buy_{}_{}_{}_{}", 
            request.option_id, 
            request.buyer_address[..8].to_string(), 
            request.quantity, 
            request.timestamp
        )
    }

    /// Validate Bitcoin address format (basic check)
    fn is_valid_bitcoin_address(&self, address: &str) -> bool {
        address.starts_with("bc1") || address.starts_with("1") || address.starts_with("3")
    }

    /// Get user positions for specific option
    pub fn get_user_positions(&self, option_id: &str) -> Vec<UserPosition> {
        self.active_positions
            .get(option_id)
            .cloned()
            .unwrap_or_default()
    }

    /// Get total pool balance
    pub fn get_pool_balance(&self) -> f64 {
        self.pool_balance
    }

    /// Update pool balance (for external adjustments)
    pub fn update_pool_balance(&mut self, new_balance: f64) {
        info!("💰 Pool balance updated: {} -> {}", self.pool_balance, new_balance);
        self.pool_balance = new_balance;
    }

    /// Get buy transaction as OptionTransaction enum
    pub fn create_option_transaction(&self, buy_tx: BuyOptionTx) -> OptionTransaction {
        OptionTransaction::Buy(buy_tx)
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::options::{OptionType, ProductStatus};

    fn create_test_factory() -> OptionFactory {
        let mut factory = OptionFactory::new("test_operator".to_string());

        // Add test product
        let create_request = super::super::CreateProductRequest {
            option_type: OptionType::Call,
            underlying: "BTCUSD".to_string(),
            strike: 52000,
            days_to_expiry: 1, // 1 day from now
            initial_iv: 0.68,
            max_units: 100,
            premium_adjustment: None,
        };

        factory.create_product(create_request, 50000.0).unwrap();
        factory
    }

    #[tokio::test]
    async fn test_successful_buy() {
        let factory = create_test_factory();
        let mut buy_service = OptionBuyService::new(factory, 1000.0);

        let products = buy_service.factory.list_products(50000.0);
        let option_id = products[0].option_id.clone();

        let request = BuyOptionRequest {
            option_id,
            buyer_address: "bc1qtest123".to_string(),
            quantity: 2,
            max_premium_per_unit: Some(0.1),
            timestamp: chrono::Utc::now().timestamp() as u64,
        };

        let response = buy_service.process_buy_request(request).await.unwrap();
        assert!(response.success);
        assert_eq!(response.buy_tx.buy_quantity, 2);
        assert!(response.total_premium > 0.0);
    }

    #[tokio::test]
    async fn test_buy_nonexistent_option() {
        let factory = create_test_factory();
        let mut buy_service = OptionBuyService::new(factory, 1000.0);

        let request = BuyOptionRequest {
            option_id: "nonexistent".to_string(),
            buyer_address: "bc1qtest123".to_string(),
            quantity: 1,
            max_premium_per_unit: None,
            timestamp: chrono::Utc::now().timestamp() as u64,
        };

        let result = buy_service.process_buy_request(request).await;
        assert!(result.is_err());
    }

    #[tokio::test]
    async fn test_slippage_protection() {
        let factory = create_test_factory();
        let mut buy_service = OptionBuyService::new(factory, 1000.0);

        let products = buy_service.factory.list_products(50000.0);
        let option_id = products[0].option_id.clone();

        let request = BuyOptionRequest {
            option_id,
            buyer_address: "bc1qtest123".to_string(),
            quantity: 1,
            max_premium_per_unit: Some(0.000001), // Very low limit
            timestamp: chrono::Utc::now().timestamp() as u64,
        };

        let result = buy_service.process_buy_request(request).await;
        assert!(result.is_err());
        assert!(result.unwrap_err().to_string().contains("slippage"));
    }

    #[test]
    fn test_position_tracking() {
        let factory = create_test_factory();
        let buy_service = OptionBuyService::new(factory, 1000.0);

        let positions = buy_service.get_user_positions("test_option");
        assert!(positions.is_empty());
        
        assert_eq!(buy_service.get_pool_balance(), 1000.0);
    }
}