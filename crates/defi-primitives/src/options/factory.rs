//! Option Factory for product creation and management
//! 
//! Implements the CREATE transaction schema from business requirements.
//! Allows service operators to register option products that users can purchase.

use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use tracing::{info, error, warn};
use bitcoin_client::{BitcoinClient, BitcoinConfig};
use super::{
    types::OptionType,
    pricing::BlackScholesPricing,
    transaction::{CreateOptionTx, TxType},
    bitvmx_integration::BitVMXOptionVerifier,
};

/// Option Factory for managing product creation and lifecycle
pub struct OptionFactory {
    /// Registry of all created option products
    pub products: HashMap<String, OptionProduct>,
    /// Black-Scholes pricing engine
    pub pricing_engine: BlackScholesPricing,
    /// Service operator address (issuer)
    pub operator_address: String,
    /// Supported oracle providers
    pub oracle_providers: Vec<String>,
    /// Bitcoin client for L1 anchoring
    pub bitcoin_client: Option<BitcoinClient>,
    /// BitVMX verifier for fraud-proof protocols
    pub bitvmx_verifier: Option<BitVMXOptionVerifier>,
}

/// Option product registered by service operator
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct OptionProduct {
    /// CREATE transaction that created this product
    pub create_tx: CreateOptionTx,
    /// Current availability status
    pub status: ProductStatus,
    /// Maximum units that can be sold
    pub max_units: u32,
    /// Units already sold
    pub units_sold: u32,
    /// Calculated premium per unit (BTC)
    pub premium_per_unit: f64,
    /// Last premium update timestamp
    pub premium_updated_at: u64,
}

/// Product lifecycle status
#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum ProductStatus {
    Active,      // Available for purchase
    Paused,      // Temporarily unavailable
    SoldOut,     // All units sold
    Expired,     // Past expiry time
    Cancelled,   // Manually cancelled by operator
}

impl OptionProduct {
    /// Check if product is active and available for purchase
    pub fn is_active(&self) -> bool {
        let now = chrono::Utc::now().timestamp() as u64;
        matches!(self.status, ProductStatus::Active) &&
        self.create_tx.expiry > now &&
        self.units_sold < self.max_units
    }

    /// Get available units for purchase
    pub fn available_units(&self) -> u32 {
        self.max_units.saturating_sub(self.units_sold)
    }

    /// Check if option is in the money at current price
    pub fn is_itm(&self, current_price: f64) -> bool {
        match self.create_tx.option_type {
            OptionType::Call => current_price > self.create_tx.strike as f64,
            OptionType::Put => current_price < self.create_tx.strike as f64,
        }
    }
}

/// Request to create new option product
#[derive(Debug, Deserialize)]
pub struct CreateProductRequest {
    pub option_type: OptionType,
    pub underlying: String,
    pub strike: u64,
    pub days_to_expiry: u32,
    pub initial_iv: f64,
    pub max_units: u32,
    pub premium_adjustment: Option<f64>, // Optional manual adjustment (default 1.0)
}

/// Response after creating product
#[derive(Debug, Serialize)]
pub struct CreateProductResponse {
    pub option_id: String,
    pub create_tx: CreateOptionTx,
    pub calculated_premium: f64,
    pub max_units: u32,
    pub expiry_timestamp: u64,
}

/// Response after creating and anchoring product to Bitcoin L1
#[derive(Debug, Serialize)]
pub struct CreateAndAnchorResponse {
    pub option_id: String,
    pub create_tx: CreateOptionTx,
    pub calculated_premium: f64,
    pub max_units: u32,
    pub expiry_timestamp: u64,
    pub bitcoin_anchor_txid: Option<String>,
    pub bitvmx_program_hash: String,
}

/// Public product information for user interface
#[derive(Debug, Serialize)]
pub struct ProductListItem {
    pub option_id: String,
    pub option_type: String,
    pub underlying: String,
    pub strike: u64,
    pub expiry_date: String,
    pub days_to_expiry: u32,
    pub premium_per_unit: f64,
    pub available_units: u32,
    pub initial_iv: f64,
    pub oracle_list: Vec<String>,
    pub current_btc_price: f64,
    pub is_itm: bool,
    pub estimated_max_payout: f64,
}

impl OptionFactory {
    /// Create new Option Factory
    pub fn new(operator_address: String) -> Self {
        Self {
            products: HashMap::new(),
            pricing_engine: BlackScholesPricing {
                spot: 50000.0,  // Will be updated with real price
                strike: 50000.0,
                time_to_expiry: 0.0,
                risk_free_rate: 0.05,
                volatility: 0.5,
            },
            operator_address,
            oracle_providers: vec![
                "binance".to_string(),
                "coinbase".to_string(), 
                "kraken".to_string(),
            ],
            bitcoin_client: None,
            bitvmx_verifier: None,
        }
    }

    /// Create new Option Factory with Bitcoin client for L1 anchoring
    pub fn new_with_bitcoin(operator_address: String, bitcoin_config: BitcoinConfig) -> Self {
        let mut factory = Self::new(operator_address);
        factory.bitcoin_client = Some(BitcoinClient::new(bitcoin_config));
        factory
    }

    /// Create new Option Factory with full BitVMX and Bitcoin integration
    pub fn new_with_full_integration(
        operator_address: String, 
        bitcoin_config: BitcoinConfig
    ) -> Self {
        let mut factory = Self::new(operator_address);
        factory.bitcoin_client = Some(BitcoinClient::new(bitcoin_config));
        factory.bitvmx_verifier = Some(BitVMXOptionVerifier::new());
        factory
    }

    /// Create new option product (service operator only)
    pub fn create_product(
        &mut self,
        request: CreateProductRequest,
        current_btc_price: f64,
    ) -> Result<CreateProductResponse, String> {
        // Generate unique option ID
        let option_id = self.generate_option_id(&request);
        
        // Check if product already exists
        if self.products.contains_key(&option_id) {
            return Err(format!("Product {} already exists", option_id));
        }

        // Calculate expiry timestamp
        let now = chrono::Utc::now().timestamp() as u64;
        let expiry_timestamp = now + (request.days_to_expiry as u64 * 86400);

        // Calculate premium using Black-Scholes
        let premium_per_unit = self.calculate_product_premium(
            &request,
            current_btc_price,
            expiry_timestamp,
        )?;

        // Apply manual adjustment if provided
        let adjusted_premium = premium_per_unit * request.premium_adjustment.unwrap_or(1.0);

        // Create the CREATE transaction
        let create_tx = CreateOptionTx {
            protocol: "BTCFI01".to_string(),
            tx_type: TxType::Create,
            option_id: option_id.clone(),
            option_type: request.option_type,
            underlying: request.underlying.clone(),
            strike: request.strike,
            expiry: expiry_timestamp,
            unit: 1.0,
            issuer: self.operator_address.clone(),
            initial_iv: request.initial_iv,
            premium_formula: "Black-Scholes".to_string(),
            oracle_ids: self.oracle_providers.clone(),
            created_at: now,
            sig: self.generate_signature(&option_id), // TODO: Implement real signature
        };

        // Create product record
        let product = OptionProduct {
            create_tx: create_tx.clone(),
            status: ProductStatus::Active,
            max_units: request.max_units,
            units_sold: 0,
            premium_per_unit: adjusted_premium,
            premium_updated_at: now,
        };

        // Store in registry
        self.products.insert(option_id.clone(), product);

        tracing::info!(
            "Created option product: {:?} {} @{} expiring in {} days, premium: {} BTC",
            request.option_type,
            request.strike,
            request.underlying,
            request.days_to_expiry,
            adjusted_premium
        );

        Ok(CreateProductResponse {
            option_id,
            create_tx,
            calculated_premium: adjusted_premium,
            max_units: request.max_units,
            expiry_timestamp,
        })
    }

    /// Create option product and anchor to Bitcoin L1 in one transaction
    pub async fn create_and_anchor(
        &mut self,
        request: CreateProductRequest,
        current_btc_price: f64,
    ) -> Result<CreateAndAnchorResponse, String> {
        info!("Creating and anchoring option product: {:?}", request);

        // Step 1: Create product using existing logic
        let create_response = self.create_product(request, current_btc_price)?;
        let option_id = &create_response.option_id;
        let create_tx = &create_response.create_tx;

        // Step 2: Anchor to Bitcoin L1 if client is available
        let anchor_txid = if let Some(ref bitcoin_client) = self.bitcoin_client {
            match self.anchor_to_bitcoin(create_tx, bitcoin_client).await {
                Ok(txid) => {
                    info!("Successfully anchored option {} to Bitcoin: {}", option_id, txid);
                    Some(txid)
                }
                Err(e) => {
                    error!("Failed to anchor option {} to Bitcoin: {}", option_id, e);
                    // Remove the product from registry since anchoring failed
                    self.products.remove(option_id);
                    return Err(format!("Failed to anchor to Bitcoin: {}", e));
                }
            }
        } else {
            warn!("Bitcoin client not configured, skipping L1 anchoring for option {}", option_id);
            None
        };

        // Step 3: Generate BitVMX verification program (placeholder for now)
        let bitvmx_program_hash = self.generate_bitvmx_program(create_tx).await?;

        Ok(CreateAndAnchorResponse {
            option_id: create_response.option_id,
            create_tx: create_response.create_tx,
            calculated_premium: create_response.calculated_premium,
            max_units: create_response.max_units,
            expiry_timestamp: create_response.expiry_timestamp,
            bitcoin_anchor_txid: anchor_txid,
            bitvmx_program_hash,
        })
    }

    /// Anchor option data to Bitcoin L1 using OP_RETURN
    async fn anchor_to_bitcoin(
        &self,
        create_tx: &CreateOptionTx,
        bitcoin_client: &BitcoinClient,
    ) -> Result<String, String> {
        info!("Anchoring option {} to Bitcoin L1", create_tx.option_id);

        // Create simplified OP_RETURN data (28 bytes)
        let op_return_data = self.serialize_create_tx_for_bitcoin(create_tx)?;
        
        info!("OP_RETURN data: {} bytes", op_return_data.len());

        // Send transaction with small amount for change
        match bitcoin_client.send_op_return_transaction(&op_return_data, Some(0.001)).await {
            Ok(txid) => {
                info!("Bitcoin anchoring successful: {}", txid);
                Ok(txid)
            }
            Err(e) => {
                error!("Bitcoin anchoring failed: {}", e);
                Err(format!("Bitcoin RPC error: {}", e))
            }
        }
    }

    /// Serialize CREATE transaction to Bitcoin OP_RETURN format (28 bytes)
    fn serialize_create_tx_for_bitcoin(&self, create_tx: &CreateOptionTx) -> Result<Vec<u8>, String> {
        let mut data = Vec::new();

        // TX Type (1 byte): CREATE=0
        data.push(0x00);

        // Option ID (6 bytes): hash the option ID string and take first 6 bytes
        use std::collections::hash_map::DefaultHasher;
        use std::hash::{Hash, Hasher};
        
        let mut hasher = DefaultHasher::new();
        create_tx.option_id.hash(&mut hasher);
        let hash = hasher.finish();
        let hash_bytes = hash.to_be_bytes();
        data.extend_from_slice(&hash_bytes[..6]);  // Take first 6 bytes

        // Option Type (1 byte): CALL=0, PUT=1
        let option_type_byte = match create_tx.option_type {
            OptionType::Call => 0x00,
            OptionType::Put => 0x01,
        };
        data.push(option_type_byte);

        // Strike (8 bytes, big endian)
        let strike_sats = (create_tx.strike as u64) * 100_000_000;
        data.extend_from_slice(&strike_sats.to_be_bytes());

        // Expiry (8 bytes, big endian)
        data.extend_from_slice(&create_tx.expiry.to_be_bytes());

        // Unit (4 bytes): 1.0 as IEEE 754 float
        data.extend_from_slice(&1.0f32.to_be_bytes());

        if data.len() != 28 {
            return Err(format!("Invalid OP_RETURN data length: {} (expected 28)", data.len()));
        }

        Ok(data)
    }

    /// Generate BitVMX verification program for option product
    async fn generate_bitvmx_program(&mut self, create_tx: &CreateOptionTx) -> Result<String, String> {
        info!("🔧 Generating BitVMX verification program for option: {}", create_tx.option_id);

        // Use BitVMX verifier if available
        if let Some(ref mut verifier) = self.bitvmx_verifier {
            match verifier.register_option_product(create_tx).await {
                Ok(program_hash) => {
                    info!("✅ BitVMX protocol registration successful: {}", program_hash);
                    return Ok(program_hash);
                }
                Err(e) => {
                    warn!("⚠️ BitVMX registration failed, using fallback: {}", e);
                }
            }
        }

        // Fallback: generate deterministic hash
        let program_input = format!(
            "option_id={},strike={},expiry={},type={:?}",
            create_tx.option_id,
            create_tx.strike,
            create_tx.expiry,
            create_tx.option_type
        );
        
        use std::collections::hash_map::DefaultHasher;
        use std::hash::{Hash, Hasher};
        
        let mut hasher = DefaultHasher::new();
        program_input.hash(&mut hasher);
        let program_hash = format!("fallback_{:016x}", hasher.finish());
        
        info!("Generated fallback BitVMX program hash: {}", program_hash);
        Ok(program_hash)
    }

    /// Get all active products for user interface
    pub fn get_product_list(&self, current_btc_price: f64) -> Vec<ProductListItem> {
        let now = chrono::Utc::now().timestamp() as u64;
        
        self.products
            .values()
            .filter(|product| {
                matches!(product.status, ProductStatus::Active) &&
                product.create_tx.expiry > now &&
                product.units_sold < product.max_units
            })
            .map(|product| {
                let days_to_expiry = ((product.create_tx.expiry - now) as f64 / 86400.0).ceil() as u32;
                let is_itm = self.is_in_the_money(&product.create_tx, current_btc_price);
                let estimated_max_payout = self.calculate_max_payout(&product.create_tx, current_btc_price);

                ProductListItem {
                    option_id: product.create_tx.option_id.clone(),
                    option_type: format!("{:?}", product.create_tx.option_type),
                    underlying: product.create_tx.underlying.clone(),
                    strike: product.create_tx.strike,
                    expiry_date: self.format_timestamp(product.create_tx.expiry),
                    days_to_expiry,
                    premium_per_unit: product.premium_per_unit,
                    available_units: product.max_units - product.units_sold,
                    initial_iv: product.create_tx.initial_iv,
                    oracle_list: product.create_tx.oracle_ids.clone(),
                    current_btc_price,
                    is_itm,
                    estimated_max_payout,
                }
            })
            .collect()
    }

    /// Update product availability after purchase
    pub fn record_purchase(&mut self, option_id: &str, quantity: u32) -> Result<(), String> {
        let product = self.products.get_mut(option_id)
            .ok_or_else(|| format!("Product {} not found", option_id))?;

        if product.units_sold + quantity > product.max_units {
            return Err("Insufficient units available".to_string());
        }

        product.units_sold += quantity;
        
        // Update status if sold out
        if product.units_sold >= product.max_units {
            product.status = ProductStatus::SoldOut;
        }

        tracing::info!(
            "Recorded purchase: {} units of {}, {} units remaining",
            quantity,
            option_id,
            product.max_units - product.units_sold
        );

        Ok(())
    }

    /// Update product premium (operator can adjust prices)
    pub fn update_premium(
        &mut self,
        option_id: &str,
        new_premium: f64,
    ) -> Result<(), String> {
        let product = self.products.get_mut(option_id)
            .ok_or_else(|| format!("Product {} not found", option_id))?;

        if !matches!(product.status, ProductStatus::Active) {
            return Err("Cannot update premium for inactive product".to_string());
        }

        product.premium_per_unit = new_premium;
        product.premium_updated_at = chrono::Utc::now().timestamp() as u64;

        tracing::info!("Updated premium for {}: {} BTC", option_id, new_premium);
        Ok(())
    }

    /// Pause/resume product sales
    pub fn set_product_status(&mut self, option_id: &str, status: ProductStatus) -> Result<(), String> {
        let product = self.products.get_mut(option_id)
            .ok_or_else(|| format!("Product {} not found", option_id))?;

        product.status = status;
        tracing::info!("Updated status for {}: {:?}", option_id, product.status);
        Ok(())
    }

    /// Get product details
    pub fn get_product(&self, option_id: &str) -> Option<&OptionProduct> {
        self.products.get(option_id)
    }

    /// List all products (wrapper for get_product_list)
    pub fn list_products(&self, current_btc_price: f64) -> Vec<ProductListItem> {
        self.get_product_list(current_btc_price)
    }

    // Helper methods

    fn generate_option_id(&self, request: &CreateProductRequest) -> String {
        let type_str = match request.option_type {
            OptionType::Call => "CALL",
            OptionType::Put => "PUT",
        };
        
        let now = chrono::Utc::now().timestamp();
        format!("BTC{}{}D_{}_{}", type_str, request.strike, request.days_to_expiry, now)
    }

    fn calculate_product_premium(
        &mut self,
        request: &CreateProductRequest,
        current_btc_price: f64,
        expiry_timestamp: u64,
    ) -> Result<f64, String> {
        let now = chrono::Utc::now().timestamp() as u64;
        let time_to_expiry = (expiry_timestamp - now) as f64 / (365.0 * 86400.0); // Convert to years

        self.pricing_engine.spot = current_btc_price;
        self.pricing_engine.strike = request.strike as f64;
        self.pricing_engine.time_to_expiry = time_to_expiry;
        self.pricing_engine.volatility = request.initial_iv;

        let premium_usd = self.pricing_engine.calculate_premium(request.option_type);
        
        // Convert USD to BTC
        let premium_btc = premium_usd / current_btc_price;
        
        Ok(premium_btc)
    }

    fn is_in_the_money(&self, create_tx: &CreateOptionTx, current_price: f64) -> bool {
        match create_tx.option_type {
            OptionType::Call => current_price > create_tx.strike as f64,
            OptionType::Put => current_price < create_tx.strike as f64,
        }
    }

    fn calculate_max_payout(&self, create_tx: &CreateOptionTx, current_price: f64) -> f64 {
        match create_tx.option_type {
            OptionType::Call => {
                if current_price > create_tx.strike as f64 {
                    current_price - create_tx.strike as f64
                } else {
                    0.0
                }
            },
            OptionType::Put => {
                if current_price < create_tx.strike as f64 {
                    create_tx.strike as f64 - current_price
                } else {
                    0.0
                }
            },
        }
    }

    fn format_timestamp(&self, timestamp: u64) -> String {
        chrono::DateTime::from_timestamp(timestamp as i64, 0)
            .unwrap_or_default()
            .format("%Y-%m-%dT%H:%M:%SZ")
            .to_string()
    }

    fn generate_signature(&self, option_id: &str) -> String {
        // TODO: Implement actual ECDSA signature
        format!("0x{:x}", md5::compute(format!("{}{}", self.operator_address, option_id)))
    }
}

impl Default for OptionFactory {
    fn default() -> Self {
        Self::new("bc1q_service_operator_address".to_string())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_create_product() {
        let mut factory = OptionFactory::default();
        
        let request = CreateProductRequest {
            option_type: OptionType::Call,
            underlying: "BTCUSD".to_string(),
            strike: 52000,
            days_to_expiry: 7,
            initial_iv: 0.68,
            max_units: 100,
            premium_adjustment: None,
        };

        let response = factory.create_product(request, 50000.0).unwrap();
        
        assert!(response.option_id.contains("CALL"));
        assert!(response.option_id.contains("52000"));
        assert_eq!(response.create_tx.option_type, OptionType::Call);
        assert_eq!(response.create_tx.strike, 52000);
        assert_eq!(response.max_units, 100);
    }

    #[test]
    fn test_product_list() {
        let mut factory = OptionFactory::default();
        
        let request = CreateProductRequest {
            option_type: OptionType::Call,
            underlying: "BTCUSD".to_string(),
            strike: 52000,
            days_to_expiry: 7,
            initial_iv: 0.68,
            max_units: 100,
            premium_adjustment: None,
        };

        factory.create_product(request, 50000.0).unwrap();
        
        let products = factory.get_product_list(51000.0);
        assert_eq!(products.len(), 1);
        
        let product = &products[0];
        assert_eq!(product.option_type, "Call");
        assert_eq!(product.strike, 52000);
        assert_eq!(product.available_units, 100);
        assert!(!product.is_itm); // Call with strike 52000 @ spot 51000 is OTM
    }

    #[test]
    fn test_record_purchase() {
        let mut factory = OptionFactory::default();
        
        let request = CreateProductRequest {
            option_type: OptionType::Call,
            underlying: "BTCUSD".to_string(),
            strike: 52000,
            days_to_expiry: 7,
            initial_iv: 0.68,
            max_units: 100,
            premium_adjustment: None,
        };

        let response = factory.create_product(request, 50000.0).unwrap();
        
        // Record purchase
        factory.record_purchase(&response.option_id, 10).unwrap();
        
        let product = factory.get_product(&response.option_id).unwrap();
        assert_eq!(product.units_sold, 10);
        
        // Check product list shows updated availability
        let products = factory.get_product_list(50000.0);
        assert_eq!(products[0].available_units, 90);
    }
}