//! Bitcoin client for Oracle VM

pub mod client;
pub mod scripts;
pub mod utxo;

pub use client::{BitcoinClient, BitcoinConfig, TransactionInfo, UtxoInfo};
pub use bitcoin::Network;