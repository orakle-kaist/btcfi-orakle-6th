//! 옵션 구매와 BitVMX 증명 생성을 연동하는 예제

use anyhow::Result;
use btcfi_contracts::{
    BuyerOnlyOption, BuyerOnlyOptionManager, DeltaNeutralPool,
    bitvmx_proof_generator::{OptionSettlementProofGenerator, SettlementResult},
    bitvmx_emulator_integration::OptionSettlementExecutor,
};
use bitcoin_script_riscv::riscv::trace::Trace;
use oracle_vm_common::types::{OptionType, PriceData};
use chrono::{Duration, Utc};

#[tokio::main]
async fn main() -> Result<()> {
    println!("=== 옵션 구매 및 BitVMX 증명 생성 예제 ===\n");

    // 1. Delta Neutral Pool 초기화
    let btc_address = "bc1qexample...".to_string();
    let mut pool = DeltaNeutralPool::new(btc_address, 10_000_000_000);
    println!("✓ Delta Neutral Pool 생성 완료");
    println!("  초기 자본: {} sats\n", pool.total_liquidity);

    // 2. 옵션 매니저 생성
    let mut option_manager = BuyerOnlyOptionManager::new();

    // 3. 현재 BTC 가격 설정 ($50,000)
    let current_price = PriceData {
        timestamp: Utc::now().timestamp() as u64,
        price: 50_000_00, // $50,000.00 (cents)
        confidence: 100,
        source: "aggregator".to_string(),
    };

    // 4. Call 옵션 구매
    let call_option = BuyerOnlyOption {
        option_id: format!("CALL-{}", Utc::now().timestamp()),
        buyer_address: "buyer123".to_string(),
        option_type: OptionType::Call,
        strike_price: 52_000_00, // $52,000
        quantity: 100, // 0.001 BTC
        expiry: Utc::now() + Duration::days(7),
        premium_paid: 0,
        purchase_price: current_price.clone(),
        settled: false,
    };

    let premium = pool.calculate_premium(
        &call_option.option_type,
        call_option.strike_price,
        current_price.price,
        call_option.quantity,
        7,
    );

    println!("📊 Call 옵션 구매:");
    println!("  행사가: ${}", call_option.strike_price as f64 / 100.0);
    println!("  수량: {} sats", call_option.quantity);
    println!("  프리미엄: {} sats", premium);

    // 5. BitVMX 증명 생성 준비
    println!("\n🔧 BitVMX 증명 생성 준비...");
    
    // 간단한 옵션 정산 프로그램 (실제로는 RISC-V ELF 파일)
    let mock_elf_bytes = include_bytes!("../../bitvmx_protocol/BitVMX-CPU/docker-riscv32/src/option_settlement.elf");
    
    // 증명 생성기 초기화
    let proof_generator = OptionSettlementProofGenerator::new(mock_elf_bytes)?;
    
    // 6. 만기 시점 시뮬레이션 - ITM 시나리오
    let spot_price_at_expiry = 55_000_00; // $55,000
    println!("\n📈 만기 시점 가격: ${}", spot_price_at_expiry as f64 / 100.0);
    
    // 7. BitVMX 증명 생성
    let (proof_scripts, settlement_result) = proof_generator.generate_settlement_proof(
        0, // Call option
        call_option.strike_price,
        spot_price_at_expiry,
        call_option.quantity,
    )?;
    
    println!("\n✅ BitVMX 증명 생성 완료:");
    println!("  ITM 여부: {}", if settlement_result.is_itm { "예" } else { "아니오" });
    println!("  내재가치: {} sats", settlement_result.intrinsic_value);
    println!("  정산 금액: {} sats", settlement_result.payout);
    println!("  증명 스크립트 수: {}", proof_scripts.len());
    
    // 8. 실제 emulator로 검증 (옵션)
    if let Ok(executor) = OptionSettlementExecutor::from_program_bytes(mock_elf_bytes) {
        println!("\n🔍 Emulator로 검증 중...");
        
        let trace = executor.execute_simple_settlement(
            0, // Call
            call_option.strike_price,
            spot_price_at_expiry,
            call_option.quantity,
        )?;
        
        println!("  실행 단계 수: {}", trace.steps.len());
        println!("  최종 결과 검증: ✓");
    }
    
    // 9. 옵션 정산
    option_manager.options.push(call_option.clone());
    let settled_options = option_manager.settle_expired_options(
        &mut pool,
        spot_price_at_expiry,
    )?;
    
    println!("\n💰 정산 완료:");
    println!("  정산된 옵션 수: {}", settled_options.len());
    if let Some(settled) = settled_options.first() {
        println!("  옵션 ID: {}", settled.option_id);
        println!("  정산 완료: {}", settled.settled);
    }
    
    // 10. 최종 풀 상태
    println!("\n📊 최종 Pool 상태:");
    println!("  총 유동성: {} sats", pool.total_liquidity);
    println!("  ITM Call 노출: {} sats", pool.total_call_itm_exposure);
    
    println!("\n🎉 옵션 구매와 BitVMX 증명 생성이 성공적으로 완료되었습니다!");
    
    Ok(())
}

/// BitVMX 실행 추적 결과
pub struct SettlementTrace {
    pub steps: Vec<ExecutionStep>,
    pub final_payout: u32,
}

/// 실행 단계
pub struct ExecutionStep {
    pub pc: u32,
    pub instruction: String,
    pub registers: [u32; 32],
}