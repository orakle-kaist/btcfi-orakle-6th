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
pub mod bitvm_verified_option_creator;
pub mod bitvm_bridge_integration;
pub mod bitvm_native_integration;
pub mod bitvm_product_registration;
pub mod production_service;
pub mod proper_bitvm_option;
pub mod secure_key_management;
pub mod bitvm_transaction_sequence;
pub mod economic_security_model;
pub mod real_bitvm_transactions;
pub mod real_taproot_musig2;
pub mod real_challenge_response_circuit;
pub mod binary_arithmetic_verification;
pub mod simplified_bitvm_demo;
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
pub use bitvm_verified_option_creator::{
    BitVMVerifiedOptionCreator, BitVMCreateRequest, BitVMCreateResponse,
    BitVMContext, VerificationMethod, DisputeTransactions
};
pub use bitvm_bridge_integration::{
    BitVMBridgeIntegrator, OnChainDisputeResult, BridgeConfig
};
pub use production_service::{
    ProductionOptionService, ServiceConfig, CreateOptionProductRequest, 
    CreateOptionProductResponse, MarketInfoResponse, PublicProductInfo
};
pub use bitvm_product_registration::{
    BitVMProductRegistrator, BitVMProductRequest, BitVMProductResponse,
    OffChainComputationResult
};
pub use proper_bitvm_option::{
    ProperBitVMOption, ProperOptionRequest, ProperOptionResponse,
    BitVMKeyStore, SecurityConfig, DisputeTransactionHashes, SecurityInfo, BitVMCommitment
};
pub use secure_key_management::{
    SecureBitVMKeyStore, KeyRole, KeyMetadata, KeyDerivationConfig, EncryptedKey, AuditLogger
};
pub use bitvm_transaction_sequence::{
    BitVMTransactionSequence, PreSignedTransactionSet, SignedTransaction, BitVMTransactionType,
    ChallengeRound, DisputeState, DisputeStateType
};
pub use economic_security_model::{
    EconomicSecurityModel, CollateralPosition, CollateralStatus, SlashingEvent, SlashingReason,
    RewardPool, RewardDistribution, RewardType, CollateralRequirement, DisputeOutcome, 
    DisputeResult, EconomicAction, SystemPerformanceData
};
// pub use batch_anchor::{
//     BatchAnchoringService, AnchoringTier, PendingOption, AnchoringCostCalculator
// };

#[cfg(test)]
mod test_factory_integration;