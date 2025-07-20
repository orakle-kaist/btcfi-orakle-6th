//! Error handling for DeFi primitives

use std::fmt;

#[derive(Debug)]
pub enum DefiError {
    InvalidInput(String),
    InsufficientFunds,
    OptionExpired,
    OptionNotActive,
    PricingError(String),
    ValidationError(String),
    SerializationError(String),
    NetworkError(String),
}

impl fmt::Display for DefiError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            DefiError::InvalidInput(msg) => write!(f, "Invalid input: {}", msg),
            DefiError::InsufficientFunds => write!(f, "Insufficient funds"),
            DefiError::OptionExpired => write!(f, "Option has expired"),
            DefiError::OptionNotActive => write!(f, "Option is not active"),
            DefiError::PricingError(msg) => write!(f, "Pricing error: {}", msg),
            DefiError::ValidationError(msg) => write!(f, "Validation error: {}", msg),
            DefiError::SerializationError(msg) => write!(f, "Serialization error: {}", msg),
            DefiError::NetworkError(msg) => write!(f, "Network error: {}", msg),
        }
    }
}

impl std::error::Error for DefiError {}

impl From<String> for DefiError {
    fn from(msg: String) -> Self {
        DefiError::ValidationError(msg)
    }
}

impl From<&str> for DefiError {
    fn from(msg: &str) -> Self {
        DefiError::ValidationError(msg.to_string())
    }
}

pub type Result<T> = std::result::Result<T, DefiError>;