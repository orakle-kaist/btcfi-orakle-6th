//! 레그테스트 환경에서 옵션 상품 등록 테스트
//! 
//! Bitcoin 레그테스트 노드와 BitVMX 서비스를 사용하여 실제 옵션 상품 등록을 테스트합니다.

use defi_primitives::options::{
    factory::{OptionFactory, CreateProductRequest},
    types::OptionType,
    bitvmx_integration::BitVMXOptionVerifier,
};
use bitcoin_client::{BitcoinClient, BitcoinConfig, Network};

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    tracing_subscriber::fmt::init();

    println!("🚀 BitVMX RegTest 네이티브 환경 테스트");

    // 1. Bitcoin RegTest 클라이언트 설정 (BitVMX 원래 설정)
    println!("⛏️ Bitcoin RegTest 노드 연결 중...");
    
    let bitcoin_config = BitcoinConfig {
        network: bitcoin::Network::Regtest,
        rpc_url: "http://127.0.0.1:18443".to_string(),
        rpc_user: "bitcoin".to_string(),
        rpc_password: "bitcoin".to_string(),
        wallet_name: Some("regtest_wallet".to_string()),
    };
    
    let bitcoin_client = BitcoinClient::new(bitcoin_config);
    
    // Bitcoin 노드 연결 확인
    match bitcoin_client.get_network_info().await {
        Ok(info) => {
            println!("✅ Bitcoin 노드 연결 성공:");
            println!("   노드 정보: {}", info);
            if let Some(version) = info.get("version") {
                println!("   버전: {}", version);
            }
            if let Some(connections) = info.get("connections") {
                println!("   연결 수: {}", connections);
            }
        }
        Err(e) => {
            println!("❌ Bitcoin 노드 연결 실패: {}", e);
            println!("💡 Bitcoin 노드가 실행 중인지 확인하세요");
            return Ok(());
        }
    }

    // 2. BitVMX 서비스 확인
    println!("\n🔐 BitVMX 서비스 상태 확인...");
    let bitvmx_verifier = BitVMXOptionVerifier::with_urls(
        "http://localhost:8081".to_string(),
        "http://localhost:8080".to_string(),
    );

    // 3. Option Factory 생성 (실제 서비스들과 연동)
    println!("\n🏭 Option Factory 초기화...");
    let mut factory = OptionFactory::new_with_full_integration(
        "bcrt1qtest_operator_address".to_string(),
        vec!["binance".to_string(), "coinbase".to_string()],
        Some(bitcoin_client),
        Some(bitvmx_verifier),
    );

    // 4. 테스트 옵션 상품 정의
    println!("\n📋 옵션 상품 정의:");
    let request = CreateProductRequest {
        option_type: OptionType::Call,
        underlying: "BTCUSD".to_string(),
        strike: 55000, // $55,000
        days_to_expiry: 7,
        initial_iv: 0.75, // 75% 변동성
        max_units: 100,
        premium_adjustment: Some(1.05), // 5% 마크업
    };

    println!("   타입: Call 옵션");
    println!("   기초자산: BTC/USD");
    println!("   행사가: $55,000");
    println!("   만료: 7일");
    println!("   최대 수량: 100개");
    println!("   변동성: 75%");

    // 5. 현재 BTC 가격 설정 (실제로는 오라클에서 가져옴)
    let current_btc_price = 52000.0; // $52,000
    println!("   현재 BTC 가격: ${:.2}", current_btc_price);

    // 6. 옵션 상품 등록 실행
    println!("\n🚀 옵션 상품 등록 시작...");
    println!("   1️⃣ Black-Scholes 프리미엄 계산");
    println!("   2️⃣ BitVMX 검증 프로그램 설정");
    println!("   3️⃣ Bitcoin OP_RETURN 앵커링");
    println!("   4️⃣ 상품 등록 완료");

    match factory.create_and_anchor(request, current_btc_price).await {
        Ok(response) => {
            println!("\n✅ 옵션 상품 등록 성공!");
            println!("📄 등록 결과:");
            println!("   옵션 ID: {}", response.option_id);
            println!("   프리미엄: {:.8} BTC", response.calculated_premium);
            println!("   BitVMX 프로그램 해시: {}", response.bitvmx_program_hash);
            
            if let Some(bitcoin_tx) = response.bitcoin_anchor_txid {
                println!("   Bitcoin 트랜잭션 ID: {}", bitcoin_tx);
                println!("   레그테스트 탐색기에서 확인 가능");
            }

            // 7. 등록된 상품 목록 확인
            println!("\n📜 등록된 상품 목록:");
            let products = factory.list_products(current_btc_price);
            for (index, product) in products.iter().enumerate() {
                println!("   {}. {} {} @{} 행사가", 
                    index + 1,
                    product.option_type,
                    product.strike,
                    product.underlying
                );
                println!("      프리미엄: {:.8} BTC", product.premium_per_unit);
                println!("      사용 가능 수량: {}", product.available_units);
            }

            // 8. BitVMX 세션 정보 확인
            if let Some(ref verifier) = factory.bitvmx_verifier {
                if let Some(session) = verifier.get_session(&response.option_id) {
                    println!("\n🔐 BitVMX 세션 정보:");
                    println!("   Setup UUID: {}", session.setup_uuid);
                    println!("   프로그램 해시: {}", session.program_hash);
                    println!("   상태: {:?}", session.status);
                    println!("   생성 시간: {}", session.created_at);
                }
            }

            println!("\n🎉 레그테스트 환경에서 옵션 상품 등록 완료!");
            println!("💡 이제 사용자가 이 옵션을 구매할 수 있습니다.");
        }
        Err(e) => {
            println!("\n❌ 옵션 상품 등록 실패: {}", e);
            println!("💡 원인을 확인하고 다시 시도하세요.");
        }
    }

    Ok(())
}