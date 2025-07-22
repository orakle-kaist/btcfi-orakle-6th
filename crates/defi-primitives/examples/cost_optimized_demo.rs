//! 비용 최적화된 상용 옵션 서비스 데모
//! 
//! 이 데모는 트랜잭션 비용 처리와 배치 앵커링을 포함한 실제 상용서비스를 보여줍니다.

use std::sync::Arc;
use tokio::sync::Mutex;
use tokio::time::{sleep, Duration};
use tracing::{info, warn, error};

use defi_primitives::options::{
    factory::{OptionFactory, CreateProductRequest},
    types::OptionType,
    batch_anchor::{BatchAnchoringService, AnchoringTier, PendingOption, AnchoringCostCalculator},
    transaction::CreateOptionTx,
    pricing::BlackScholesPricing,
};
use bitcoin_client::{BitcoinClient, BitcoinConfig};

#[derive(Debug)]
struct CostOptimizedOptionService {
    factory: OptionFactory,
    batch_service: Arc<BatchAnchoringService>,
}

impl CostOptimizedOptionService {
    pub async fn new() -> Self {
        // Bitcoin 클라이언트 설정
        let bitcoin_config = BitcoinConfig {
            rpc_url: "http://localhost:18443".to_string(),
            rpc_user: "bitcoin".to_string(),
            rpc_password: "bitcoin".to_string(),
            network: bitcoin_client::Network::Regtest,
            wallet_name: Some("default".to_string()),
        };

        let bitcoin_client = BitcoinClient::new(bitcoin_config);
        let batch_service = Arc::new(BatchAnchoringService::new(bitcoin_client.clone()));

        // 배치 처리 시작
        batch_service.start_batch_processing().await;

        let factory = OptionFactory::new_with_full_integration(
            "bc1q_cost_optimized_operator".to_string(),
            vec!["binance".to_string(), "coinbase".to_string()],
            Some(bitcoin_client),
            None,
        );

        Self {
            factory,
            batch_service,
        }
    }

    /// 계층별 옵션 생성
    pub async fn create_option_with_tier(
        &mut self, 
        request: CreateProductRequest, 
        tier: AnchoringTier,
        current_btc_price: f64
    ) -> Result<String, String> {
        info!("🎯 Creating option with {} tier", match tier {
            AnchoringTier::Instant => "INSTANT",
            AnchoringTier::Batched => "BATCHED", 
            AnchoringTier::Delayed => "DELAYED",
        });

        // 1. 기본 옵션 생성 (앵커링 없이)
        let option_id = format!("{}{}{}D_{}_{}", 
            if request.option_type == OptionType::Call { "BTCCALL" } else { "BTCPUT" },
            request.strike,
            match tier {
                AnchoringTier::Instant => "I",
                AnchoringTier::Batched => "B",
                AnchoringTier::Delayed => "D",
            },
            request.days_to_expiry,
            chrono::Utc::now().timestamp()
        );

        // 2. 비용 계산
        let base_tx_fee = 0.0002; // 기본 트랜잭션 비용
        let estimated_cost = AnchoringCostCalculator::estimate_cost(tier, base_tx_fee);
        let tier_multiplier = tier.fee_multiplier();

        info!("💰 Cost estimation for {:?}:", tier);
        info!("   Base TX fee: {} BTC", base_tx_fee);
        info!("   Estimated cost: {} BTC", estimated_cost);
        info!("   Tier multiplier: {}x", tier_multiplier);

        // 3. 프리미엄 계산 (비용 포함)
        let time_to_expiry = request.days_to_expiry as f64 / 365.0;
        let mut pricing = BlackScholesPricing::new(
            current_btc_price,
            request.strike as f64,
            time_to_expiry,
            0.04, // risk-free rate
            request.initial_iv
        );

        let premium = pricing.calculate_premium(request.option_type) * tier_multiplier;
        info!("💎 Calculated premium: {} BTC (includes {} cost)", premium, match tier {
            AnchoringTier::Instant => "instant anchoring",
            AnchoringTier::Batched => "batched anchoring",
            AnchoringTier::Delayed => "delayed anchoring",
        });

        // 4. CreateOptionTx 생성
        let create_tx = CreateOptionTx {
            option_id: option_id.clone(),
            option_type: request.option_type,
            underlying: request.underlying,
            strike: request.strike,
            unit: 1.0,
            expiry_timestamp: chrono::Utc::now().timestamp() as u64 + (request.days_to_expiry as u64 * 86400),
            max_units: request.max_units,
            issuer: "bc1q_cost_optimized_operator".to_string(),
            initial_iv: request.initial_iv,
            oracle_ids: vec!["binance".to_string(), "coinbase".to_string()],
        };

        // 5. 배치 큐에 추가
        let pending = PendingOption {
            option_id: option_id.clone(),
            create_tx,
            tier,
            submitted_at: chrono::Utc::now().timestamp() as u64,
            callback_url: None,
        };

        self.batch_service.add_to_queue(pending).await?;

        info!("✅ Option {} queued for {} anchoring", option_id, match tier {
            AnchoringTier::Instant => "immediate",
            AnchoringTier::Batched => "batched (10min)",
            AnchoringTier::Delayed => "delayed (1hr)",
        });

        Ok(option_id)
    }

    /// 앵커링 상태 확인
    pub async fn check_anchoring_status(&self, option_id: &str) -> Option<String> {
        self.batch_service.get_anchoring_result(option_id).await
    }

    /// 큐 상태 조회
    pub async fn get_queue_status(&self) -> (usize, usize) {
        self.batch_service.get_queue_sizes().await
    }
}

#[tokio::main]
async fn main() {
    // 로깅 초기화
    tracing_subscriber::fmt::init();

    info!("🚀 Cost-Optimized BTCFi Option Service Demo");
    info!("============================================");

    let mut service = CostOptimizedOptionService::new().await;
    let current_btc_price = 52000.0;

    // 1. 고가 옵션 - 즉시 앵커링
    info!("\n📈 Step 1: Creating high-value option (INSTANT tier)");
    let high_value_request = CreateProductRequest {
        option_type: OptionType::Call,
        underlying: "BTCUSD".to_string(),
        strike: 60000,
        days_to_expiry: 14,
        initial_iv: 0.9,
        max_units: 10,
        premium_adjustment: Some(1.2),
    };

    match service.create_option_with_tier(high_value_request, AnchoringTier::Instant, current_btc_price).await {
        Ok(option_id) => {
            info!("✅ High-value option created: {}", option_id);
            
            // 즉시 앵커링이므로 잠시 후 결과 확인
            sleep(Duration::from_secs(3)).await;
            if let Some(txid) = service.check_anchoring_status(&option_id).await {
                info!("✅ Instantly anchored: {}", txid);
            }
        }
        Err(e) => error!("❌ High-value option failed: {}", e),
    }

    // 2. 중간 가치 옵션들 - 배치 앵커링
    info!("\n📊 Step 2: Creating multiple medium-value options (BATCHED tier)");
    
    let medium_requests = vec![
        ("55000", 55000),
        ("56000", 56000), 
        ("57000", 57000),
    ];

    for (name, strike) in medium_requests {
        let request = CreateProductRequest {
            option_type: OptionType::Call,
            underlying: "BTCUSD".to_string(),
            strike,
            days_to_expiry: 7,
            initial_iv: 0.75,
            max_units: 25,
            premium_adjustment: Some(1.0),
        };

        match service.create_option_with_tier(request, AnchoringTier::Batched, current_btc_price).await {
            Ok(option_id) => info!("✅ Medium option {} queued: {}", name, option_id),
            Err(e) => error!("❌ Medium option {} failed: {}", name, e),
        }
    }

    // 3. 저가 옵션들 - 지연 앵커링
    info!("\n📉 Step 3: Creating low-value options (DELAYED tier)");
    
    let low_requests = vec![
        ("PUT_45000", OptionType::Put, 45000),
        ("PUT_48000", OptionType::Put, 48000),
        ("CALL_65000", OptionType::Call, 65000),
    ];

    for (name, option_type, strike) in low_requests {
        let request = CreateProductRequest {
            option_type,
            underlying: "BTCUSD".to_string(),
            strike,
            days_to_expiry: 30,
            initial_iv: 0.6,
            max_units: 100,
            premium_adjustment: Some(0.8),
        };

        match service.create_option_with_tier(request, AnchoringTier::Delayed, current_btc_price).await {
            Ok(option_id) => info!("✅ Low-value option {} queued: {}", name, option_id),
            Err(e) => error!("❌ Low-value option {} failed: {}", name, e),
        }
    }

    // 4. 큐 상태 확인
    info!("\n📋 Step 4: Queue status check");
    let (batched_count, delayed_count) = service.get_queue_status().await;
    info!("📊 Current queue sizes:");
    info!("   Batched queue: {} options", batched_count);
    info!("   Delayed queue: {} options", delayed_count);
    info!("   Batched options will be anchored every 10 minutes");
    info!("   Delayed options will be anchored every hour");

    // 5. 비용 분석
    info!("\n💰 Step 5: Cost analysis");
    let base_fee = 0.0002;
    
    info!("💡 Transaction cost comparison:");
    info!("   Instant: {} BTC per option (individual TX)", 
          AnchoringCostCalculator::estimate_cost(AnchoringTier::Instant, base_fee));
    info!("   Batched: {} BTC per option (10 options per TX)", 
          AnchoringCostCalculator::estimate_cost(AnchoringTier::Batched, base_fee));
    info!("   Delayed: {} BTC per option (50 options per TX)", 
          AnchoringCostCalculator::estimate_cost(AnchoringTier::Delayed, base_fee));

    info!("\n🎯 Cost optimization achieved:");
    let instant_cost = AnchoringCostCalculator::estimate_cost(AnchoringTier::Instant, base_fee);
    let delayed_cost = AnchoringCostCalculator::estimate_cost(AnchoringTier::Delayed, base_fee);
    let savings = ((instant_cost - delayed_cost) / instant_cost * 100.0) as u32;
    info!("   Delayed tier saves {}% compared to instant", savings);

    // 6. 권장 계층 데모
    info!("\n🤖 Step 6: Tier recommendation demo");
    let test_premiums = vec![0.001, 0.01, 0.1, 0.5];
    
    for premium in test_premiums {
        let recommended = AnchoringCostCalculator::recommend_tier(premium, false);
        info!("   Premium {} BTC -> Recommended: {:?}", premium, recommended);
    }

    info!("\n🎉 Cost-optimized service demo completed!");
    info!("✅ Key features demonstrated:");
    info!("   - Tier-based anchoring (Instant/Batched/Delayed)");
    info!("   - Cost optimization up to {}% savings", savings);
    info!("   - Queue management and batch processing");
    info!("   - Automatic tier recommendation");
    info!("   - Real-time cost calculation");

    warn!("⏰ Note: This demo shows queue management. In production:");
    warn!("   - Batched options anchor every 10 minutes");
    warn!("   - Delayed options anchor every hour");
    warn!("   - Instant options anchor immediately (higher cost)");
}