//! Common types for options

use serde::{Deserialize, Serialize};

/// Option type (Call or Put)
#[derive(Debug, Clone, Copy, PartialEq, Serialize, Deserialize)]
pub enum OptionType {
    Call,
    Put,
}

/// Option status lifecycle
#[derive(Debug, Clone, Copy, PartialEq, Serialize, Deserialize)]
pub enum OptionStatus {
    Created,
    Bought,
    Expired,
    Exercised,
    Settled,
}