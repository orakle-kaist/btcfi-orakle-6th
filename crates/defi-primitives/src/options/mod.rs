//! Option settlement primitives

pub mod types;
pub mod pricing;
pub mod contract;
pub mod factory;
pub mod transaction;
pub mod buy_service;
pub mod bitvmx_integration;
pub mod bitvmx_cpu_integration;
pub mod bitvmx_protocol_types;
pub mod option_create;
pub mod production_service;
// pub mod batch_anchor; // 일시적으로 비활성화

pub use types::{OptionType, OptionStatus};
pub use pricing::BlackScholesPricing;
pub use contract::OptionContract;
pub use factory::{
    OptionFactory, OptionProduct, ProductStatus, CreateProductRequest, 
    CreateProductResponse, ProductListItem
};
pub use transaction::{
    TxType, CreateOptionTx, BuyOptionTx, SettleOptionTx, ChallengeTx, 
    ChallengeType, OptionTransaction, PROTOCOL_ID
};
pub use buy_service::{
    OptionBuyService, BuyOptionRequest, BuyOptionResponse, 
    BuyValidationError, UserPosition
};
pub use bitvmx_integration::{
    BitVMXClient, BitVMXOptionVerifier, BitVMXSetupResponse
};
pub use bitvmx_cpu_integration::{
    BitVMXCPUVerifier, VerificationResult, OptionVerificationInput
};
pub use bitvmx_protocol_types::{
    BitVMXProtocolSetupProperties, BitVMXProtocolProperties, BitVMXTransactions,
    ExecutionTrace, BitVMXProverData, BitVMXVerifierData
};
pub use option_create::{
    OptionCreator, CreateRequest, CreateResponse
};
pub use production_service::{
    ProductionOptionService, ServiceConfig, CreateOptionProductRequest, 
    CreateOptionProductResponse, MarketInfoResponse, PublicProductInfo
};
// pub use batch_anchor::{
//     BatchAnchoringService, AnchoringTier, PendingOption, AnchoringCostCalculator
// };

#[cfg(test)]
mod test_factory_integration;