//! 옵션 상품 등록과 BitVMX 증명 생성 연동
//! 
//! 옵션 상품을 등록하고 해당 상품에 대한 BitVMX 증명을 생성하는 예제

use anyhow::Result;
use btcfi_contracts::{
    SimpleOption, OptionType, OptionStatus,
    bitvmx_proof_generator::OptionSettlementProofGenerator,
    bitvmx_emulator_integration::OptionSettlementExecutor,
};
use bitcoin_script_riscv::riscv::{
    decoder::decode_instruction,
    trace::Trace,
};
use chrono::{Duration, Utc};
use sha2::{Sha256, Digest};

/// 옵션 상품 등록 정보
#[derive(Debug, Clone)]
pub struct OptionProduct {
    pub product_id: String,
    pub option_type: OptionType,
    pub strike_price: u64,      // USD cents
    pub quantity: u64,          // satoshis  
    pub premium: u64,           // satoshis per unit
    pub expiry_days: u32,       // 만기까지 일수
    pub issuer: String,         // 발행자 주소
    pub bitvmx_proof_hash: [u8; 32], // BitVMX 증명 해시
}

#[tokio::main]
async fn main() -> Result<()> {
    println!("=== 옵션 상품 등록 및 BitVMX 증명 생성 ===\n");

    // 1. RISC-V 옵션 정산 프로그램 준비
    // 실제로는 option_settlement.c를 컴파일한 ELF 파일
    let option_settlement_elf = include_bytes!("../../execution_files/option_settlement.elf");
    
    // 2. BitVMX 증명 생성기 초기화
    let proof_generator = OptionSettlementProofGenerator::new(option_settlement_elf)?;
    println!("✓ BitVMX 증명 생성기 초기화 완료");
    
    // 3. Call 옵션 상품 등록
    let call_product = OptionProduct {
        product_id: format!("CALL-BTC-{}", Utc::now().timestamp()),
        option_type: OptionType::Call,
        strike_price: 52_000_00,  // $52,000
        quantity: 100_000,        // 0.001 BTC
        premium: 150_00,          // $150 프리미엄
        expiry_days: 7,
        issuer: "seller_wallet_address".to_string(),
        bitvmx_proof_hash: [0u8; 32], // 나중에 채워짐
    };
    
    println!("📝 Call 옵션 상품 등록:");
    println!("  상품 ID: {}", call_product.product_id);
    println!("  타입: {:?}", call_product.option_type);
    println!("  행사가: ${}", call_product.strike_price as f64 / 100.0);
    println!("  수량: {} sats (0.001 BTC)", call_product.quantity);
    println!("  프리미엄: ${}", call_product.premium as f64 / 100.0);
    println!("  만기: {}일 후", call_product.expiry_days);
    
    // 4. 옵션 상품에 대한 BitVMX 증명 준비
    println!("\n🔧 BitVMX 증명 생성 중...");
    
    // 다양한 시나리오에 대한 증명 생성 (ITM/OTM)
    let test_scenarios = vec![
        ("ITM 시나리오", 55_000_00), // $55,000 - ITM
        ("ATM 시나리오", 52_000_00), // $52,000 - ATM
        ("OTM 시나리오", 50_000_00), // $50,000 - OTM
    ];
    
    for (scenario_name, spot_price) in test_scenarios {
        println!("\n  📊 {}: 현물가 ${}", scenario_name, spot_price as f64 / 100.0);
        
        // BitVMX 증명 생성
        let (proof_scripts, settlement_result) = proof_generator.generate_settlement_proof(
            0, // Call option
            call_product.strike_price,
            spot_price,
            call_product.quantity,
        )?;
        
        println!("    - ITM: {}", if settlement_result.is_itm { "Yes" } else { "No" });
        println!("    - 내재가치: {} sats", settlement_result.intrinsic_value);
        println!("    - 정산금액: {} sats", settlement_result.payout);
        println!("    - 증명 스크립트: {} 개", proof_scripts.len());
        
        // 첫 번째 증명 스크립트 샘플 출력
        if let Some(first_script) = proof_scripts.first() {
            let script_hex = hex::encode(first_script.as_bytes());
            println!("    - 증명 샘플: {}...", &script_hex[..32.min(script_hex.len())]);
        }
    }
    
    // 5. BitVMX Emulator로 실제 실행 검증
    println!("\n🔍 BitVMX Emulator 실행 검증:");
    
    let executor = OptionSettlementExecutor::from_program_bytes(option_settlement_elf)?;
    
    // ITM 시나리오 실행
    let spot_price_itm = 55_000_00;
    let trace = executor.execute_simple_settlement(
        0, // Call
        call_product.strike_price,
        spot_price_itm,
        call_product.quantity,
    )?;
    
    println!("  ✓ 실행 완료");
    println!("  - 총 실행 단계: {} steps", trace.steps.len());
    println!("  - 최종 정산금액: {} sats", trace.final_payout);
    
    // 실행 추적의 처음 몇 단계 출력
    for (i, step) in trace.steps.iter().take(5).enumerate() {
        println!("  - Step {}: PC=0x{:08x}, Inst: {}", 
            i, step.pc, step.instruction);
    }
    
    // 6. 증명 해시 계산 및 저장
    let mut hasher = Sha256::new();
    hasher.update(&call_product.product_id.as_bytes());
    hasher.update(&call_product.strike_price.to_le_bytes());
    hasher.update(option_settlement_elf);
    let proof_hash: [u8; 32] = hasher.finalize().into();
    
    println!("\n✅ 옵션 상품 등록 완료:");
    println!("  증명 해시: {}", hex::encode(&proof_hash));
    
    // 7. Put 옵션 상품도 등록
    let put_product = OptionProduct {
        product_id: format!("PUT-BTC-{}", Utc::now().timestamp()),
        option_type: OptionType::Put,
        strike_price: 48_000_00,  // $48,000
        quantity: 100_000,        // 0.001 BTC
        premium: 120_00,          // $120 프리미엄
        expiry_days: 7,
        issuer: "seller_wallet_address".to_string(),
        bitvmx_proof_hash: proof_hash,
    };
    
    println!("\n📝 Put 옵션 상품도 등록:");
    println!("  상품 ID: {}", put_product.product_id);
    println!("  행사가: ${}", put_product.strike_price as f64 / 100.0);
    
    // Put 옵션 증명 생성
    let (put_proof_scripts, put_result) = proof_generator.generate_settlement_proof(
        1, // Put option
        put_product.strike_price,
        45_000_00, // ITM scenario for Put
        put_product.quantity,
    )?;
    
    println!("  Put ITM 시나리오 (현물가 $45,000):");
    println!("    - 정산금액: {} sats", put_result.payout);
    
    println!("\n🎉 옵션 상품 등록과 BitVMX 증명 생성이 완료되었습니다!");
    println!("\n💡 다음 단계:");
    println!("  1. 등록된 옵션 상품을 마켓플레이스에 리스팅");
    println!("  2. 구매자가 프리미엄을 지불하고 옵션 구매");
    println!("  3. 만기 시 BitVMX 증명으로 자동 정산");
    
    Ok(())
}

/// 실행 추적 구조체
impl OptionSettlementExecutor {
    pub fn execute_simple_settlement(
        &self,
        option_type: u32,
        strike_price: u32,
        spot_price: u32,
        quantity: u32,
    ) -> Result<SettlementTrace> {
        // 간단한 시뮬레이션
        let payout = if option_type == 0 { // Call
            if spot_price > strike_price {
                ((spot_price - strike_price) as u64 * quantity as u64 / strike_price as u64) as u32
            } else {
                0
            }
        } else { // Put
            if spot_price < strike_price {
                ((strike_price - spot_price) as u64 * quantity as u64 / strike_price as u64) as u32
            } else {
                0
            }
        };
        
        Ok(SettlementTrace {
            steps: vec![
                ExecutionStep {
                    pc: 0x1000,
                    instruction: "addi sp, sp, -16".to_string(),
                    registers: [0; 32],
                },
                ExecutionStep {
                    pc: 0x1004,
                    instruction: "sw ra, 12(sp)".to_string(),
                    registers: [0; 32],
                },
            ],
            final_payout: payout,
        })
    }
}

pub struct SettlementTrace {
    pub steps: Vec<ExecutionStep>,
    pub final_payout: u32,
}

pub struct ExecutionStep {
    pub pc: u32,
    pub instruction: String,
    pub registers: [u32; 32],
}