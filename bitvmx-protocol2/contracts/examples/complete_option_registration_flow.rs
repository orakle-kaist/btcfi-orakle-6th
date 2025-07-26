//! Complete Option Registration Flow with BitVMX Protocol 2
//! 
//! This example demonstrates the full lifecycle of option registration,
//! from creation to BitVMX proof generation and blockchain anchoring.

use anyhow::Result;
use btcfi_contracts::{
    OptionType, OptionStatus,
    BitVMXOptionRegistry, BitVMXOptionInput,
    OptionSettlementProofGenerator, OptionSettlementExecutor,
};
use chrono::{Duration, Utc};
use sha2::{Sha256, Digest};
use bitcoin::Network;
use std::collections::HashMap;

/// Complete option product with all metadata
#[derive(Debug, Clone)]
pub struct CompleteOptionProduct {
    pub product_id: String,
    pub option_type: OptionType,
    pub strike_price: u64,        // USD cents
    pub quantity: u64,            // satoshis  
    pub premium: u64,             // satoshis per unit
    pub expiry_timestamp: u64,    // Unix timestamp
    pub issuer: String,           // 발행자 주소
    pub current_btc_price: u64,   // Oracle BTC price
    pub oracle_sources: Vec<String>,
    pub bitvmx_proof_hash: [u8; 32],
    pub registration_txid: Option<String>,
    pub status: OptionStatus,
}

/// Option Registry Manager for BitVMX Protocol 2
pub struct BitVMXOptionManager {
    registry: BitVMXOptionRegistry,
    products: HashMap<String, CompleteOptionProduct>,
    proof_generator: OptionSettlementProofGenerator,
}

impl BitVMXOptionManager {
    /// Initialize the option manager
    pub fn new() -> Result<Self> {
        // Load the option settlement ELF program
        let option_settlement_elf = include_bytes!("../../execution_files/option_settlement.elf");
        
        Ok(Self {
            registry: BitVMXOptionRegistry::new(Network::Regtest),
            products: HashMap::new(),
            proof_generator: OptionSettlementProofGenerator::new(option_settlement_elf)?,
        })
    }

    /// Register a new option product
    pub async fn register_option_product(
        &mut self,
        option_type: OptionType,
        strike_price: u64,
        quantity: u64,
        premium: u64,
        expiry_days: u32,
        issuer: String,
        current_btc_price: u64,
    ) -> Result<String> {
        let expiry_timestamp = Utc::now().timestamp() as u64 + (expiry_days as u64 * 24 * 3600);
        let product_id = format!("{:?}-BTC-{}", option_type, Utc::now().timestamp());

        // Create BitVMX input
        let bitvmx_input = BitVMXOptionInput {
            option_type,
            strike_price,
            quantity,
            expiry_timestamp,
            issuer: issuer.clone(),
            premium,
            oracle_sources: vec![
                "binance".to_string(),
                "coinbase".to_string(),
                "kraken".to_string(),
            ],
        };

        // Register with BitVMX
        println!("🔧 BitVMX 옵션 등록 시작...");
        let (txid, proof) = self.registry.register_option(bitvmx_input).await?;
        
        // Create complete product
        let product = CompleteOptionProduct {
            product_id: product_id.clone(),
            option_type,
            strike_price,
            quantity,
            premium,
            expiry_timestamp,
            issuer,
            current_btc_price,
            oracle_sources: vec!["binance".to_string(), "coinbase".to_string(), "kraken".to_string()],
            bitvmx_proof_hash: proof.hash_chain.final_hash,
            registration_txid: Some(txid.clone()),
            status: OptionStatus::Active,
        };

        // Store product
        self.products.insert(product_id.clone(), product);

        println!("✅ 옵션 상품 등록 완료!");
        println!("  상품 ID: {}", product_id);
        println!("  등록 트랜잭션: {}", txid);
        
        Ok(product_id)
    }

    /// Generate settlement proof for an option
    pub async fn generate_settlement_proof(
        &self,
        product_id: &str,
        settlement_price: u64,
    ) -> Result<()> {
        let product = self.products.get(product_id)
            .ok_or_else(|| anyhow::anyhow!("상품을 찾을 수 없습니다: {}", product_id))?;

        println!("\n🔍 옵션 정산 증명 생성 중...");
        println!("  상품: {}", product_id);
        println!("  행사가: ${}", product.strike_price as f64 / 100.0);
        println!("  정산가: ${}", settlement_price as f64 / 100.0);

        // Generate proof
        let (proof_scripts, settlement_result) = self.proof_generator.generate_settlement_proof(
            product.option_type as u32,
            product.strike_price,
            settlement_price,
            product.quantity,
        )?;

        println!("📊 정산 결과:");
        println!("  ITM: {}", if settlement_result.is_itm { "Yes" } else { "No" });
        println!("  내재가치: {} sats", settlement_result.intrinsic_value);
        println!("  정산금액: {} sats", settlement_result.payout);
        println!("  증명 스크립트: {} 개", proof_scripts.len());

        // Show sample proof script
        if let Some(script) = proof_scripts.first() {
            let script_hex = hex::encode(script.as_bytes());
            println!("  증명 샘플: {}...", &script_hex[..32.min(script_hex.len())]);
        }

        Ok(())
    }

    /// List all registered products
    pub fn list_products(&self) {
        println!("\n📋 등록된 옵션 상품 목록:");
        for (id, product) in &self.products {
            println!("  {} - {:?} ${} {} BTC",
                id,
                product.option_type,
                product.strike_price as f64 / 100.0,
                product.quantity as f64 / 100_000_000.0
            );
        }
    }

    /// Get product details
    pub fn get_product(&self, product_id: &str) -> Option<&CompleteOptionProduct> {
        self.products.get(product_id)
    }
}

#[tokio::main]
async fn main() -> Result<()> {
    println!("=== BitVMX Protocol 2 - Complete Option Registration Flow ===\n");

    // Initialize manager
    let mut manager = BitVMXOptionManager::new()?;
    println!("✓ BitVMX 옵션 매니저 초기화 완료\n");

    // Current BTC price (from oracle)
    let current_btc_price = 52_000_00; // $52,000

    // Register Call option
    println!("📝 Call 옵션 등록:");
    let call_id = manager.register_option_product(
        OptionType::Call,
        53_000_00,  // $53,000 strike
        10_000_000, // 0.1 BTC
        200_000,    // 0.002 BTC premium
        7,          // 7 days
        "seller_wallet_123".to_string(),
        current_btc_price,
    ).await?;

    // Register Put option
    println!("\n📝 Put 옵션 등록:");
    let put_id = manager.register_option_product(
        OptionType::Put,
        51_000_00,  // $51,000 strike
        5_000_000,  // 0.05 BTC
        100_000,    // 0.001 BTC premium
        14,         // 14 days
        "seller_wallet_456".to_string(),
        current_btc_price,
    ).await?;

    // List products
    manager.list_products();

    // Test settlement scenarios
    println!("\n🧪 정산 시나리오 테스트:");

    // Test Call option settlement (ITM)
    println!("\n1. Call 옵션 ITM 시나리오:");
    manager.generate_settlement_proof(&call_id, 55_000_00).await?; // $55,000

    // Test Call option settlement (OTM)
    println!("\n2. Call 옵션 OTM 시나리오:");
    manager.generate_settlement_proof(&call_id, 50_000_00).await?; // $50,000

    // Test Put option settlement (ITM)
    println!("\n3. Put 옵션 ITM 시나리오:");
    manager.generate_settlement_proof(&put_id, 48_000_00).await?; // $48,000

    // Test Put option settlement (OTM)
    println!("\n4. Put 옵션 OTM 시나리오:");
    manager.generate_settlement_proof(&put_id, 54_000_00).await?; // $54,000

    // Real BitVMX execution test
    println!("\n🔧 실제 BitVMX 실행 테스트:");
    let executor = OptionSettlementExecutor::from_program_bytes(
        include_bytes!("../../execution_files/option_settlement.elf")
    )?;

    let trace = executor.execute_simple_settlement(
        0,          // Call option
        53_000_00,  // Strike
        55_000_00,  // Spot (ITM)
        10_000_000, // Quantity
    )?;

    println!("  ✓ 실행 완료");
    println!("  - 실행 단계: {} steps", trace.steps.len());
    println!("  - 최종 정산금액: {} sats", trace.final_payout);

    // Show execution trace sample
    for (i, step) in trace.steps.iter().take(3).enumerate() {
        println!("  - Step {}: PC=0x{:08x}, Inst: {}", 
            i, step.pc, step.instruction);
    }

    println!("\n🎉 Complete Option Registration Flow 완료!");
    println!("\n💡 BitVMX Protocol 2 의 주요 특징:");
    println!("  1. ✅ 실제 RISC-V 프로그램 실행");
    println!("  2. ✅ BitVMX 증명 생성");
    println!("  3. ✅ 비트코인 체인 앵커링");
    println!("  4. ✅ 옵션 정산 자동화");
    println!("  5. ✅ Oracle 가격 연동");

    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[tokio::test]
    async fn test_complete_flow() -> Result<()> {
        let mut manager = BitVMXOptionManager::new()?;
        
        let product_id = manager.register_option_product(
            OptionType::Call,
            50_000_00,
            1_000_000,
            50_000,
            7,
            "test_issuer".to_string(),
            52_000_00,
        ).await?;

        assert!(!product_id.is_empty());
        assert!(manager.get_product(&product_id).is_some());

        manager.generate_settlement_proof(&product_id, 55_000_00).await?;

        Ok(())
    }

    #[test]
    fn test_manager_initialization() {
        let manager = BitVMXOptionManager::new();
        assert!(manager.is_ok());
    }
}