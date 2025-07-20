//! Vault management for single-sided options

use serde::{Deserialize, Serialize};

/// Vault pool for managing single-sided options
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct OptionVault {
    /// Total BTC balance in the vault
    pub total_balance: u64,
    /// Reserved balance for potential payouts
    pub reserved_balance: u64,
    /// Total premium collected
    pub total_premium_collected: u64,
    /// Active options exposure
    pub active_exposure: u64,
    /// Maximum allowed exposure (% of total balance)
    pub max_exposure_ratio: f64,
}

impl OptionVault {
    /// Create new vault with initial balance
    pub fn new(initial_balance: u64) -> Self {
        Self {
            total_balance: initial_balance,
            reserved_balance: 0,
            total_premium_collected: 0,
            active_exposure: 0,
            max_exposure_ratio: 0.8, // 80% max exposure
        }
    }
    
    /// Check if vault can accept new option
    pub fn can_accept_option(&self, potential_payout: u64) -> bool {
        let new_exposure = self.active_exposure + potential_payout;
        let max_allowed = (self.total_balance as f64 * self.max_exposure_ratio) as u64;
        new_exposure <= max_allowed
    }
    
    /// Add premium to vault
    pub fn add_premium(&mut self, premium: u64) {
        self.total_balance += premium;
        self.total_premium_collected += premium;
    }
    
    /// Reserve funds for potential payout
    pub fn reserve_payout(&mut self, amount: u64) -> Result<(), &'static str> {
        if self.total_balance - self.reserved_balance < amount {
            return Err("Insufficient funds in vault");
        }
        self.reserved_balance += amount;
        self.active_exposure += amount;
        Ok(())
    }
    
    /// Process settlement (payout or release reservation)
    pub fn settle_option(&mut self, reserved_amount: u64, actual_payout: u64) -> Result<(), &'static str> {
        if self.reserved_balance < reserved_amount {
            return Err("Invalid reservation amount");
        }
        
        self.reserved_balance -= reserved_amount;
        self.active_exposure -= reserved_amount;
        
        if actual_payout > 0 {
            if self.total_balance < actual_payout {
                return Err("Insufficient funds for payout");
            }
            self.total_balance -= actual_payout;
        }
        
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    
    #[test]
    fn test_vault_operations() {
        let mut vault = OptionVault::new(1_000_000_000); // 10 BTC
        
        // Test adding premium
        vault.add_premium(1_000_000); // 0.01 BTC
        assert_eq!(vault.total_balance, 1_001_000_000);
        
        // Test reservation
        assert!(vault.reserve_payout(500_000_000).is_ok());
        assert_eq!(vault.reserved_balance, 500_000_000);
        
        // Test settlement
        assert!(vault.settle_option(500_000_000, 100_000_000).is_ok());
        assert_eq!(vault.total_balance, 901_000_000);
    }
}