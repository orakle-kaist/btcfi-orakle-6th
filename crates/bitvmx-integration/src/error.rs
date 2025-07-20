//! Error types for BitVMX integration

use std::fmt;

#[derive(Debug)]
pub enum BitVMXError {
    /// Settlement error
    SettlementError(String),
    
    /// Invalid oracle data
    InvalidOracleData(String),
    
    /// Invalid option type
    InvalidOptionType(String),
    
    /// Prover error
    ProverError(String),
    
    /// Network error
    NetworkError(String),
    
    /// Serialization error
    SerializationError(String),
    
    /// Bitcoin error
    BitcoinError(String),
    
    /// Signature error
    SignatureError(String),
}

impl fmt::Display for BitVMXError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            BitVMXError::SettlementError(msg) => write!(f, "Settlement error: {}", msg),
            BitVMXError::InvalidOracleData(msg) => write!(f, "Invalid oracle data: {}", msg),
            BitVMXError::InvalidOptionType(msg) => write!(f, "Invalid option type: {}", msg),
            BitVMXError::ProverError(msg) => write!(f, "Prover error: {}", msg),
            BitVMXError::NetworkError(msg) => write!(f, "Network error: {}", msg),
            BitVMXError::SerializationError(msg) => write!(f, "Serialization error: {}", msg),
            BitVMXError::BitcoinError(msg) => write!(f, "Bitcoin error: {}", msg),
            BitVMXError::SignatureError(msg) => write!(f, "Signature error: {}", msg),
        }
    }
}

impl std::error::Error for BitVMXError {}

impl From<reqwest::Error> for BitVMXError {
    fn from(err: reqwest::Error) -> Self {
        BitVMXError::NetworkError(err.to_string())
    }
}

impl From<serde_json::Error> for BitVMXError {
    fn from(err: serde_json::Error) -> Self {
        BitVMXError::SerializationError(err.to_string())
    }
}

pub type Result<T> = std::result::Result<T, BitVMXError>;