//! BTCFi Protocol v2를 사용한 완전한 옵션 상품 등록 예제
//! 
//! Bitcoin 블록체인에 옵션을 등록하고 BitVMX 증명과 연동

use anyhow::Result;
use btcfi_contracts::{
    SimpleOption, OptionStatus,
    bitcoin_anchoring_v2::{BitcoinAnchoringServiceV2, CreateOptionAnchorData},
    bitvmx_option_settlement::{OptionSettlementTransaction, OptionSettlementPackage},
    option_registration::{OptionRegistrationManager, OptionType as RegOptionType},
};
use oracle_vm_common::types::OptionType;
use bitcoin::{Network, secp256k1::SecretKey};
use chrono::Utc;
use std::str::FromStr;

#[tokio::main]
async fn main() -> Result<()> {
    println!("=== BTCFi Protocol v2 옵션 상품 등록 및 BitVMX 증명 생성 ===\n");
    
    // 1. 옵션 상품 생성
    let option = SimpleOption {
        option_id: "BTCCALL52000D_7".to_string(),
        option_type: OptionType::Call,
        strike_price: 52_000_00,  // $52,000
        quantity: 100_000,        // 0.001 BTC
        premium_paid: 15_000,     // 0.00015 BTC premium
        expiry_height: 1008,      // ~7 days
        status: OptionStatus::Active,
        user_id: "seller_001".to_string(),
    };
    
    println!("📋 옵션 상품 정보:");
    println!("  ID: {}", option.option_id);
    println!("  타입: {:?}", option.option_type);
    println!("  행사가: ${}", option.strike_price as f64 / 100.0);
    println!("  수량: {} sats (0.001 BTC)", option.quantity);
    println!("  만기: {} 블록 후", option.expiry_height);
    
    // 2. BTCFi CREATE 데이터 생성
    let anchor_data = CreateOptionAnchorData::from_option(&option);
    let encoded_data = anchor_data.encode();
    
    println!("\n📊 BTCFi CREATE 앵커 데이터:");
    println!("  크기: {} bytes", encoded_data.len());
    println!("  TX Type: 0x{:02x} (CREATE)", anchor_data.tx_type as u8);
    println!("  Option ID Hash: {}", anchor_data.option_id_hex());
    println!("  Strike (sats): {}", anchor_data.strike_sats);
    println!("  Expiry (Unix): {}", anchor_data.expiry);
    println!("  인코딩: {}", hex::encode(&encoded_data));
    
    // 3. Bitcoin 앵커링 (OP_RETURN)
    println!("\n⛓️ Bitcoin 블록체인에 앵커링...");
    
    // 실제 환경에서는 이 부분을 실행
    /*
    let anchoring_service = BitcoinAnchoringServiceV2::regtest();
    match anchoring_service.anchor_option(&option).await {
        Ok(txid) => {
            println!("✅ 앵커링 성공!");
            println!("  TXID: {}", txid);
            
            // 검증
            match anchoring_service.verify_anchor(&txid).await {
                Ok(verified) => {
                    println!("\n🔍 앵커 데이터 검증:");
                    println!("  Option ID: {}", verified.option_id_hex());
                    println!("  Strike USD: ${}", verified.strike_usd());
                },
                Err(e) => println!("⚠️ 검증 실패: {}", e),
            }
        },
        Err(e) => println!("❌ 앵커링 실패: {}", e),
    }
    */
    
    // 데모용 TXID
    let anchor_txid = "abcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890";
    println!("  [Demo] TXID: {}", anchor_txid);
    
    // 4. BitVMX 증명 생성
    println!("\n🔧 BitVMX 정산 트랜잭션 및 증명 생성...");
    
    let seller_key = SecretKey::from_str(
        "0000000000000000000000000000000000000000000000000000000000000001"
    )?;
    let buyer_key = SecretKey::from_str(
        "0000000000000000000000000000000000000000000000000000000000000002"
    )?;
    
    let settlement_tx = OptionSettlementTransaction::new(Network::Testnet);
    
    // 정산 트랜잭션 생성 (ITM 시나리오)
    let settlement_package = settlement_tx.create_option_settlement_with_proof(
        &seller_key,
        &buyer_key,
        0,  // Call option
        option.strike_price,
        option.quantity as u64,
        option.premium_paid as u64,
        bitcoin::Txid::from_str(anchor_txid)?,
        0,
        1_000_000, // 0.01 BTC funding
    )?;
    
    println!("\n📦 BitVMX 정산 패키지:");
    println!("  정산 TXID: {}", settlement_package.txid);
    println!("  증명 스크립트: {} 개", settlement_package.proof_scripts.len());
    println!("  실행 단계: {}", settlement_package.execution_trace.total_steps);
    println!("  정산금액: {} sats", settlement_package.option_details.payout);
    
    // 5. 옵션 등록 관리
    println!("\n📝 옵션 등록 시스템에 추가...");
    
    let mut registration_manager = OptionRegistrationManager::new(Network::Testnet);
    
    let elf_program = include_bytes!("../../bitvmx_protocol/BitVMX-CPU/docker-riscv32/src/option_settlement.elf");
    
    let registered_option = registration_manager.register_option_product(
        &seller_key,
        RegOptionType::Call,
        option.strike_price,
        option.quantity as u64,
        option.premium_paid as u64,
        7, // 7 days
        elf_program,
    )?;
    
    // 6. 완전한 옵션 데이터
    println!("\n✅ 옵션 상품 등록 완료!");
    println!("\n📊 최종 옵션 정보:");
    println!("  Option ID: {}", registered_option.option_id);
    println!("  발행자: {}", hex::encode(registered_option.issuer_pubkey.serialize()));
    println!("  앵커 TXID: {}", anchor_txid);
    println!("  등록 TXID: {}", registered_option.registration_txid);
    println!("  BitVMX 증명: {}", hex::encode(&registered_option.bitvmx_proof_commitment));
    println!("  상태: {:?}", registered_option.status);
    
    // 7. 트랜잭션 데이터 출력
    println!("\n📋 Raw Transaction Data:");
    
    // BTCFi CREATE OP_RETURN 트랜잭션
    println!("\n1. BTCFi CREATE Transaction (OP_RETURN):");
    println!("   Data: {}", hex::encode(&encoded_data));
    println!("   Script: OP_RETURN {}", hex::encode(&encoded_data));
    
    // BitVMX 정산 트랜잭션
    let settlement_tx_hex = bitcoin::consensus::encode::serialize_hex(&settlement_package.transaction);
    println!("\n2. BitVMX Settlement Transaction:");
    println!("   Hex: {}...", &settlement_tx_hex[..100]);
    println!("   Size: {} bytes", settlement_tx_hex.len() / 2);
    
    // 등록 트랜잭션
    let registration_tx_hex = bitcoin::consensus::encode::serialize_hex(&registered_option.registration_tx);
    println!("\n3. Registration Transaction:");
    println!("   Hex: {}...", &registration_tx_hex[..100]);
    println!("   Size: {} bytes", registration_tx_hex.len() / 2);
    
    println!("\n🎉 BTCFi Protocol v2 옵션 등록 프로세스 완료!");
    println!("\n💡 다음 단계:");
    println!("  1. Bitcoin 네트워크에 CREATE 트랜잭션 브로드캐스트");
    println!("  2. 구매자가 프리미엄 지불하고 BUY 트랜잭션 생성");
    println!("  3. 만기 시 BitVMX 증명으로 자동 정산 (SETTLE)");
    println!("  4. 분쟁 시 Challenge-Response 프로토콜 (CHALLENGE)");
    
    Ok(())
}