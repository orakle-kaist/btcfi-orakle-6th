//! 실제 옵션 상품 등록과 BitVMX 증명 생성
//! 
//! 실제 트랜잭션과 증명을 생성하는 실행 가능한 예제

use anyhow::Result;
use btcfi_contracts::bitvmx_option_settlement::{
    OptionSettlementTransaction, OptionSettlementPackage,
};
use bitcoin::{
    Network, secp256k1::SecretKey,
    Txid,
};
use std::str::FromStr;

#[tokio::main]
async fn main() -> Result<()> {
    println!("=== 실제 BitVMX 옵션 정산 트랜잭션 생성 ===\n");
    
    // 1. 키 생성 (테스트용)
    let seller_key = SecretKey::from_str(
        "0000000000000000000000000000000000000000000000000000000000000001"
    )?;
    let buyer_key = SecretKey::from_str(
        "0000000000000000000000000000000000000000000000000000000000000002"
    )?;
    
    // 2. 옵션 정산 트랜잭션 생성기 초기화
    let settlement_tx = OptionSettlementTransaction::new(Network::Testnet);
    
    // 3. 펀딩 트랜잭션 정보 (예시)
    let funding_txid = Txid::from_str(
        "abcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890"
    )?;
    let funding_vout = 0;
    let funding_amount = 1_000_000; // 0.01 BTC
    
    // 4. Call 옵션 정산 트랜잭션 생성
    println!("📝 Call 옵션 정산 트랜잭션 생성 중...");
    
    let call_package = settlement_tx.create_option_settlement_with_proof(
        &seller_key,
        &buyer_key,
        0,              // Call option
        52_000_00,      // Strike: $52,000
        100_000,        // Quantity: 0.001 BTC
        15_000,         // Premium: 0.00015 BTC
        funding_txid,
        funding_vout,
        funding_amount,
    )?;
    
    print_settlement_package(&call_package);
    
    // 5. Put 옵션 정산 트랜잭션 생성
    println!("\n📝 Put 옵션 정산 트랜잭션 생성 중...");
    
    let put_package = settlement_tx.create_option_settlement_with_proof(
        &seller_key,
        &buyer_key,
        1,              // Put option
        48_000_00,      // Strike: $48,000
        100_000,        // Quantity: 0.001 BTC
        12_000,         // Premium: 0.00012 BTC
        funding_txid,
        funding_vout,
        funding_amount,
    )?;
    
    print_settlement_package(&put_package);
    
    // 6. 트랜잭션 데이터 출력
    println!("\n📋 트랜잭션 상세 정보:");
    println!("\nCall 옵션 Raw Transaction (hex):");
    let call_tx_hex = bitcoin::consensus::encode::serialize_hex(&call_package.transaction);
    println!("{}", &call_tx_hex[..100]);
    println!("... (총 {} bytes)", call_tx_hex.len() / 2);
    
    println!("\nPut 옵션 Raw Transaction (hex):");
    let put_tx_hex = bitcoin::consensus::encode::serialize_hex(&put_package.transaction);
    println!("{}", &put_tx_hex[..100]);
    println!("... (총 {} bytes)", put_tx_hex.len() / 2);
    
    // 7. 증명 스크립트 샘플
    println!("\n🔐 BitVMX 증명 스크립트 샘플:");
    if let Some(proof) = call_package.proof_scripts.first() {
        let proof_hex = hex::encode(proof.as_bytes());
        println!("첫 번째 증명: {}", &proof_hex[..64.min(proof_hex.len())]);
    }
    
    println!("\n✅ 실제 BitVMX 옵션 정산 트랜잭션 생성 완료!");
    println!("\n💡 다음 단계:");
    println!("  1. 생성된 트랜잭션을 Bitcoin 네트워크에 브로드캐스트");
    println!("  2. 만기 시 자동 정산 실행");
    println!("  3. Challenge-Response 프로토콜로 분쟁 해결");
    
    Ok(())
}

fn print_settlement_package(package: &OptionSettlementPackage) {
    println!("\n📦 정산 패키지 정보:");
    println!("  옵션 타입: {}", package.option_details.option_type);
    println!("  행사가: ${}", package.option_details.strike_price as f64 / 100.0);
    println!("  현물가: ${}", package.option_details.spot_price as f64 / 100.0);
    println!("  수량: {} sats", package.option_details.quantity);
    println!("  프리미엄: {} sats", package.option_details.premium);
    println!("  내재가치: ${}", package.option_details.intrinsic_value as f64 / 100.0);
    println!("  정산금액: {} sats", package.option_details.payout);
    println!("\n  TXID: {}", package.txid);
    println!("  증명 스크립트 수: {}", package.proof_scripts.len());
    println!("  실행 단계: {}", package.execution_trace.total_steps);
    println!("  최종 PC: 0x{:08x}", package.execution_trace.final_pc);
}