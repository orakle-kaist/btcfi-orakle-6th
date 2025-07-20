//! Option contract representation and management

use serde::{Deserialize, Serialize};
use super::types::{OptionType, OptionStatus};

/// Option contract representation
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct OptionContract {
    /// Unique option ID
    pub option_id: String,
    /// Option type (Call/Put)
    pub option_type: OptionType,
    /// Strike price in satoshis
    pub strike: u64,
    /// Expiry timestamp
    pub expiry: u64,
    /// Underlying asset pair
    pub underlying: String,
    /// Premium paid in satoshis
    pub premium: u64,
    /// Vault address (pool)
    pub vault_address: String,
    /// Buyer address
    pub buyer: Option<String>,
    /// Current status
    pub status: OptionStatus,
    /// Settlement price (if settled)
    pub settlement_price: Option<u64>,
    /// Created timestamp
    pub created_at: u64,
}

impl OptionContract {
    /// Calculate potential payout at given price
    pub fn calculate_payout(&self, spot_price: u64) -> u64 {
        match self.option_type {
            OptionType::Call => {
                if spot_price > self.strike {
                    spot_price - self.strike
                } else {
                    0
                }
            }
            OptionType::Put => {
                if self.strike > spot_price {
                    self.strike - spot_price
                } else {
                    0
                }
            }
        }
    }
    
    /// Check if option is expired
    pub fn is_expired(&self, current_timestamp: u64) -> bool {
        current_timestamp >= self.expiry
    }
    
    /// Check if option is in the money
    pub fn is_in_the_money(&self, spot_price: u64) -> bool {
        self.calculate_payout(spot_price) > 0
    }
}