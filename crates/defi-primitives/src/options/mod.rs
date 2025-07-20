//! Option settlement primitives

pub mod types;
pub mod pricing;
pub mod contract;
pub mod transaction;

pub use types::{OptionType, OptionStatus};
pub use pricing::BlackScholesPricing;
pub use contract::OptionContract;
pub use transaction::{
    TxType, CreateOptionTx, BuyOptionTx, SettleOptionTx, ChallengeTx, 
    ChallengeType, OptionTransaction, PROTOCOL_ID
};