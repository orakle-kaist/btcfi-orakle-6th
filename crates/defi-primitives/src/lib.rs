//! DeFi primitives for Oracle VM

pub mod error;
pub mod options;
pub mod vaults;

// Re-export commonly used types
pub use options::{
    OptionType, OptionStatus, BlackScholesPricing, OptionContract,
    TxType, CreateOptionTx, BuyOptionTx, SettleOptionTx, ChallengeTx, 
    ChallengeType, OptionTransaction, PROTOCOL_ID
};
pub use vaults::OptionVault;