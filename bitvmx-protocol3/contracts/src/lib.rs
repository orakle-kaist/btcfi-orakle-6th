//! BTCFi Option Contracts for BitVMX Protocol 2
//! 
//! This library implements Bitcoin option contracts with BitVMX verification.

use serde::{Deserialize, Serialize};

/// Option type enumeration
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum OptionType {
    Call = 0,
    Put = 1,
}

/// Option status enumeration
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum OptionStatus {
    Active,
    Exercised,
    Expired,
    Settled,
}

// Re-export modules
pub mod bitcoin_option;
pub mod bitvmx_option_registry;
pub mod bitvmx_integration;
pub mod bitvmx_proof_generator;
pub mod bitvmx_emulator_integration;
pub mod simple_contract;

// Re-export important types
pub use bitcoin_option::*;
pub use bitvmx_option_registry::*;
pub use bitvmx_integration::*;
pub use bitvmx_proof_generator::*;
pub use bitvmx_emulator_integration::*;
pub use simple_contract::*;