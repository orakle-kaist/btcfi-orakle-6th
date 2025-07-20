//! Error types for committer

use std::fmt;

#[derive(Debug)]
pub enum CommitterError {
    BitcoinError(String),
    SerializationError(String),
    NetworkError(String),
    ConfigError(String),
}

impl fmt::Display for CommitterError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            CommitterError::BitcoinError(msg) => write!(f, "Bitcoin error: {}", msg),
            CommitterError::SerializationError(msg) => write!(f, "Serialization error: {}", msg),
            CommitterError::NetworkError(msg) => write!(f, "Network error: {}", msg),
            CommitterError::ConfigError(msg) => write!(f, "Config error: {}", msg),
        }
    }
}

impl std::error::Error for CommitterError {}

impl From<&str> for CommitterError {
    fn from(msg: &str) -> Self {
        CommitterError::BitcoinError(msg.to_string())
    }
}

impl From<String> for CommitterError {
    fn from(msg: String) -> Self {
        CommitterError::BitcoinError(msg)
    }
}

impl From<serde_json::Error> for CommitterError {
    fn from(err: serde_json::Error) -> Self {
        CommitterError::SerializationError(err.to_string())
    }
}

pub type Result<T> = std::result::Result<T, CommitterError>;