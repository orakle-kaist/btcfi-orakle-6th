//! BitVMX Oracle VM implementation

use oracle_vm_common::{OracleVmError, Result};
use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use defi_primitives::{
    OptionType, OptionStatus, OptionContract, OptionVault, BlackScholesPricing,
    OptionTransaction, CreateOptionTx, BuyOptionTx, SettleOptionTx
};

/// Oracle VM state for single-pool option system
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct OracleVMState {
    /// Current block height on Bitcoin L1
    pub block_height: u64,
    
    /// Current timestamp (derived from block height)
    pub current_timestamp: u64,
    
    /// Anchored price data by block height
    pub price_data: HashMap<u64, AggregatedPriceData>,
    
    /// Single option vault pool
    pub option_vault: OptionVault,
    
    /// Active option contracts by ID
    pub options: HashMap<String, OptionContract>,
    
    /// Pending settlements to be executed
    pub pending_settlements: Vec<OptionSettlement>,
    
    /// Transaction history for L1 anchoring
    pub transaction_history: Vec<OptionTransaction>,
}

/// Aggregated price data from oracle consensus
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AggregatedPriceData {
    pub btc_usd_price: u64,  // Price in satoshis per USD
    pub timestamp: u64,
    pub data_sources: Vec<String>,
    pub consensus_achieved: bool,
}

/// Option settlement for single-pool system
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct OptionSettlement {
    pub option_id: String,
    pub settlement_price: u64,
    pub settlement_timestamp: u64,
    pub payout_amount: u64,
    pub buyer_address: String,
}

/// Oracle VM implementation
pub struct OracleVM {
    state: OracleVMState,
}

impl OracleVM {
    /// Create new Oracle VM instance with initial vault balance
    pub fn new(initial_vault_balance: u64) -> Self {
        Self {
            state: OracleVMState {
                block_height: 0,
                current_timestamp: 0,
                price_data: HashMap::new(),
                option_vault: OptionVault::new(initial_vault_balance),
                options: HashMap::new(),
                pending_settlements: Vec::new(),
                transaction_history: Vec::new(),
            },
        }
    }
    
    /// Process new block with aggregated price data
    pub fn process_block(&mut self, block_height: u64, price_data: AggregatedPriceData) -> Result<Vec<OptionSettlement>> {
        // Update state
        self.state.block_height = block_height;
        self.state.current_timestamp = price_data.timestamp;
        self.state.price_data.insert(block_height, price_data.clone());
        
        // Check for option settlements
        let settlements = self.check_option_settlements(&price_data)?;
        
        // Add to pending settlements
        self.state.pending_settlements.extend(settlements.clone());
        
        Ok(settlements)
    }
    
    /// Check if any options need settlement
    fn check_option_settlements(&self, price_data: &AggregatedPriceData) -> Result<Vec<OptionSettlement>> {
        let mut settlements = Vec::new();
        
        for (option_id, option) in &self.state.options {
            // Check if option has expired
            if price_data.timestamp >= option.expiry && option.status == OptionStatus::Bought {
                let payout = option.calculate_payout(price_data.btc_usd_price);
                
                if payout > 0 {
                    settlements.push(OptionSettlement {
                        option_id: option_id.clone(),
                        settlement_price: price_data.btc_usd_price,
                        settlement_timestamp: price_data.timestamp,
                        payout_amount: payout,
                        buyer_address: option.buyer.as_ref()
                            .unwrap_or(&"unknown".to_string()).clone(),
                    });
                }
            }
        }
        
        Ok(settlements)
    }
    
    /// Process option creation transaction
    pub fn process_create_option(&mut self, tx: CreateOptionTx) -> Result<()> {
        let option = OptionContract {
            option_id: tx.option_id.clone(),
            option_type: tx.option_type,
            strike: tx.strike,
            expiry: tx.expiry,
            underlying: tx.underlying.clone(),
            premium: 0, // Will be calculated when purchased
            vault_address: tx.issuer.clone(),
            buyer: None,
            status: OptionStatus::Created,
            settlement_price: None,
            created_at: tx.created_at,
        };
        
        self.state.options.insert(tx.option_id.clone(), option);
        
        // Add to transaction history
        self.state.transaction_history.push(OptionTransaction::Create(tx));
        
        Ok(())
    }
    
    /// Process option purchase transaction
    pub fn process_buy_option(&mut self, tx: BuyOptionTx) -> Result<()> {
        // Get option
        let option = self.state.options.get_mut(&tx.option_id)
            .ok_or_else(|| OracleVmError::InvalidInput("Option not found".to_string()))?;
        
        // Check if option is available for purchase
        if option.status != OptionStatus::Created {
            return Err(OracleVmError::InvalidInput("Option not available for purchase".to_string()));
        }
        
        // Calculate maximum potential payout
        let max_payout = match option.option_type {
            OptionType::Call => option.strike * tx.buy_quantity, // Conservative estimate
            OptionType::Put => option.strike * tx.buy_quantity,
        };
        
        // Check if vault can handle the exposure
        if !self.state.option_vault.can_accept_option(max_payout) {
            return Err(OracleVmError::InvalidInput("Insufficient vault capacity".to_string()));
        }
        
        // Update option
        option.buyer = Some(tx.buyer.clone());
        option.status = OptionStatus::Bought;
        option.premium = (tx.premium_paid * 100_000_000.0) as u64; // Convert to satoshis
        
        // Add premium to vault and reserve payout
        self.state.option_vault.add_premium(option.premium);
        self.state.option_vault.reserve_payout(max_payout)?;
        
        // Add to transaction history
        self.state.transaction_history.push(OptionTransaction::Buy(tx));
        
        Ok(())
    }
    
    /// Process option settlement 
    pub fn process_settle_option(&mut self, settlement: OptionSettlement) -> Result<SettleOptionTx> {
        // Get option
        let option = self.state.options.get_mut(&settlement.option_id)
            .ok_or_else(|| OracleVmError::InvalidInput("Option not found".to_string()))?;
        
        // Calculate actual payout
        let actual_payout = option.calculate_payout(settlement.settlement_price);
        
        // Get reserved amount (max potential payout)
        let reserved_amount = match option.option_type {
            OptionType::Call => option.strike,
            OptionType::Put => option.strike,
        };
        
        // Process settlement in vault
        self.state.option_vault.settle_option(reserved_amount, actual_payout)?;
        
        // Update option status
        option.status = OptionStatus::Settled;
        option.settlement_price = Some(settlement.settlement_price);
        
        // Create settlement transaction
        let settle_tx = SettleOptionTx::new(
            settlement.option_id,
            settlement.buyer_address,
            1, // quantity
            settlement.settlement_price,
            actual_payout as f64 / 100_000_000.0, // Convert to BTC
            "oracle_proof_placeholder".to_string(),
            "bitvmx_proof_placeholder".to_string(),
            self.state.option_vault.total_balance as f64 / 100_000_000.0,
            settlement.settlement_timestamp,
        );
        
        // Add to transaction history
        self.state.transaction_history.push(OptionTransaction::Settle(settle_tx.clone()));
        
        Ok(settle_tx)
    }
    
    /// Get current state
    pub fn get_state(&self) -> &OracleVMState {
        &self.state
    }
    
    /// Get vault status
    pub fn get_vault_status(&self) -> &OptionVault {
        &self.state.option_vault
    }
    
    /// Get option by ID
    pub fn get_option(&self, option_id: &str) -> Option<&OptionContract> {
        self.state.options.get(option_id)
    }
    
    /// Get all active options
    pub fn get_active_options(&self) -> Vec<&OptionContract> {
        self.state.options.values()
            .filter(|option| matches!(option.status, OptionStatus::Created | OptionStatus::Bought))
            .collect()
    }
    
    /// Execute settlement using BitVMX
    pub async fn execute_settlement(&mut self, settlement: OptionSettlement) -> Result<()> {
        let _settle_tx = self.process_settle_option(settlement.clone())?;
        
        // Remove from pending settlements
        self.state.pending_settlements.retain(|s| s.option_id != settlement.option_id);
        
        tracing::info!("Executed option settlement: {} -> {} satoshis", 
                      settlement.option_id, settlement.payout_amount);
        
        Ok(())
    }
    
    /// Calculate option premium using Black-Scholes
    pub fn calculate_option_premium(
        &self,
        option_type: OptionType,
        spot_price: f64,
        strike_price: f64,
        time_to_expiry_days: f64,
        volatility: f64,
    ) -> f64 {
        let pricing = BlackScholesPricing {
            spot: spot_price,
            strike: strike_price,
            time_to_expiry: time_to_expiry_days / 365.0,
            risk_free_rate: 0.05, // 5% risk-free rate
            volatility,
        };
        
        pricing.calculate_premium(option_type)
    }
    
    /// Get transaction history
    pub fn get_transaction_history(&self) -> &Vec<OptionTransaction> {
        &self.state.transaction_history
    }
}

impl Default for OracleVM {
    fn default() -> Self {
        Self::new(1_000_000_000) // Default 10 BTC vault
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    
    #[tokio::test]
    async fn test_oracle_vm_creation() {
        let vm = OracleVM::new(1_000_000_000);
        assert_eq!(vm.state.block_height, 0);
        assert_eq!(vm.state.option_vault.total_balance, 1_000_000_000);
        assert!(vm.state.options.is_empty());
    }
    
    #[tokio::test]
    async fn test_option_creation() {
        let mut vm = OracleVM::new(1_000_000_000);
        
        let create_tx = CreateOptionTx::new(
            "opt_btc_call_52k".to_string(),
            OptionType::Call,
            "BTCUSD".to_string(),
            52_000_00000000, // $52,000 in satoshis
            1723126800, // expiry timestamp
            "vault_pool".to_string(),
            0.7, // initial IV
            vec!["binance".to_string(), "coinbase".to_string()],
            1722450000, // created at
        );
        
        vm.process_create_option(create_tx).unwrap();
        
        assert!(vm.state.options.contains_key("opt_btc_call_52k"));
        let option = vm.get_option("opt_btc_call_52k").unwrap();
        assert_eq!(option.status, OptionStatus::Created);
    }
    
    #[tokio::test]
    async fn test_option_purchase() {
        let mut vm = OracleVM::new(1_000_000_000);
        
        // Create option first
        let create_tx = CreateOptionTx::new(
            "opt_btc_call_52k".to_string(),
            OptionType::Call,
            "BTCUSD".to_string(),
            52_000_000, // $520 (reduced for test)
            1723126800,
            "vault_pool".to_string(),
            0.7,
            vec!["binance".to_string()],
            1722450000,
        );
        vm.process_create_option(create_tx).unwrap();
        
        // Buy option
        let buy_tx = BuyOptionTx::new(
            "opt_btc_call_52k".to_string(),
            "user123".to_string(),
            1, // quantity
            0.00121, // premium in BTC
            "payment_txid".to_string(),
            10.0, // vault balance
            1722512100,
        );
        
        vm.process_buy_option(buy_tx).unwrap();
        
        let option = vm.get_option("opt_btc_call_52k").unwrap();
        assert_eq!(option.status, OptionStatus::Bought);
        assert_eq!(option.buyer, Some("user123".to_string()));
        
        // Check vault updated
        assert!(vm.state.option_vault.total_balance > 1_000_000_000);
    }
    
    #[tokio::test]
    async fn test_option_settlement() {
        let mut vm = OracleVM::new(1_000_000_000);
        
        // Create and buy option
        let create_tx = CreateOptionTx::new(
            "opt_btc_call_50k".to_string(),
            OptionType::Call,
            "BTCUSD".to_string(),
            50_000_000, // $500 strike (reduced for test)
            1722450000, // past expiry for test
            "vault_pool".to_string(),
            0.7,
            vec!["binance".to_string()],
            1722400000,
        );
        vm.process_create_option(create_tx).unwrap();
        
        let buy_tx = BuyOptionTx::new(
            "opt_btc_call_50k".to_string(),
            "user123".to_string(),
            1,
            0.001,
            "payment_txid".to_string(),
            10.0,
            1722420000,
        );
        vm.process_buy_option(buy_tx).unwrap();
        
        // Process price update that triggers settlement
        let price_data = AggregatedPriceData {
            btc_usd_price: 55_000_000, // $550 (in the money)
            timestamp: 1722450001, // after expiry
            data_sources: vec!["binance".to_string(), "coinbase".to_string()],
            consensus_achieved: true,
        };
        
        let settlements = vm.process_block(1000, price_data).unwrap();
        assert_eq!(settlements.len(), 1);
        
        let settlement = &settlements[0];
        assert_eq!(settlement.payout_amount, 5_000_000); // $50 profit
        
        // Execute settlement
        vm.execute_settlement(settlement.clone()).await.unwrap();
        
        let option = vm.get_option("opt_btc_call_50k").unwrap();
        assert_eq!(option.status, OptionStatus::Settled);
    }
    
    #[tokio::test]
    async fn test_black_scholes_integration() {
        let vm = OracleVM::new(1_000_000_000);
        
        let premium = vm.calculate_option_premium(
            OptionType::Call,
            50000.0, // spot
            52000.0, // strike
            7.0,     // 7 days to expiry
            0.7,     // 70% volatility
        );
        
        assert!(premium > 0.0);
        assert!(premium < 2000.0); // Reasonable premium range
    }
}