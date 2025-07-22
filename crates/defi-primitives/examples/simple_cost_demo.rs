//! 간단한 비용 처리 데모
//! 
//! 트랜잭션 비용을 프리미엄에 반영하는 방법을 보여줍니다.

use tracing::info;
use defi_primitives::options::{
    pricing::BlackScholesPricing,
    types::OptionType,
};

// 간단한 비용 계산기 구현
#[derive(Debug, Clone, Copy)]
pub enum AnchoringTier {
    Instant,
    Batched, 
    Delayed,
}

impl AnchoringTier {
    pub fn fee_multiplier(&self) -> f64 {
        match self {
            AnchoringTier::Instant => 1.5,
            AnchoringTier::Batched => 1.0,
            AnchoringTier::Delayed => 0.7,
        }
    }

    pub fn estimated_time_minutes(&self) -> u32 {
        match self {
            AnchoringTier::Instant => 2,
            AnchoringTier::Batched => 10,
            AnchoringTier::Delayed => 60,
        }
    }
}

pub struct AnchoringCostCalculator;

impl AnchoringCostCalculator {
    pub fn estimate_cost(tier: AnchoringTier, base_tx_fee: f64) -> f64 {
        match tier {
            AnchoringTier::Instant => base_tx_fee * tier.fee_multiplier(),
            AnchoringTier::Batched => base_tx_fee / 10.0 * tier.fee_multiplier(), 
            AnchoringTier::Delayed => base_tx_fee / 50.0 * tier.fee_multiplier(),
        }
    }

    pub fn recommend_tier(premium_btc: f64, urgency: bool) -> AnchoringTier {
        if urgency || premium_btc > 0.1 {
            AnchoringTier::Instant
        } else if premium_btc > 0.01 {
            AnchoringTier::Batched
        } else {
            AnchoringTier::Delayed
        }
    }
}

#[tokio::main]
async fn main() {
    tracing_subscriber::fmt::init();

    info!("💰 BTCFi 트랜잭션 비용 처리 데모");
    info!("===============================");

    let current_btc_price = 52000.0;
    let strike_price = 55000.0;
    let time_to_expiry = 7.0 / 365.0; // 7일
    let volatility = 0.75;

    // 1. 기본 Black-Scholes 프리미엄 계산
    info!("\n📊 Step 1: 기본 프리미엄 계산");
    let mut pricing = BlackScholesPricing::new(
        current_btc_price,
        strike_price,
        time_to_expiry,
        0.04, // 무위험 이자율
        volatility
    );

    let base_premium = pricing.calculate_base_premium(OptionType::Call);
    let final_premium = pricing.calculate_premium(OptionType::Call);

    info!("🎯 Call Option (Strike: ${}, 7일 만료):", strike_price);
    info!("   기본 Black-Scholes 프리미엄: {} BTC", base_premium);
    info!("   최종 프리미엄 (비용 포함): {} BTC", final_premium);
    info!("   추가된 비용: {} BTC", final_premium - base_premium);

    // 2. 앵커링 계층별 비용 분석
    info!("\n💸 Step 2: 앵커링 계층별 비용 분석");
    let base_tx_fee = 0.0002; // 기본 트랜잭션 수수료

    let tiers = [
        AnchoringTier::Instant,
        AnchoringTier::Batched,
        AnchoringTier::Delayed,
    ];

    for tier in tiers {
        let cost = AnchoringCostCalculator::estimate_cost(tier, base_tx_fee);
        let total_premium = base_premium * tier.fee_multiplier() + cost;
        
        info!("🔸 {:?} 계층:", tier);
        info!("   앵커링 비용: {} BTC", cost);
        info!("   계층 수수료 배수: {}x", tier.fee_multiplier());
        info!("   예상 앵커링 시간: {}분", tier.estimated_time_minutes());
        info!("   최종 프리미엄: {} BTC", total_premium);
        info!("   비용 절감: {}%", 
              ((AnchoringCostCalculator::estimate_cost(AnchoringTier::Instant, base_tx_fee) - cost) 
               / AnchoringCostCalculator::estimate_cost(AnchoringTier::Instant, base_tx_fee) * 100.0) as u32);
        println!();
    }

    // 3. 프리미엄별 권장 계층
    info!("🤖 Step 3: 프리미엄별 권장 계층");
    let test_premiums = vec![
        (0.001, "저가 옵션"),
        (0.01, "일반 옵션"), 
        (0.1, "고가 옵션"),
        (0.5, "프리미엄 옵션"),
    ];

    for (premium, desc) in test_premiums {
        let recommended_normal = AnchoringCostCalculator::recommend_tier(premium, false);
        let recommended_urgent = AnchoringCostCalculator::recommend_tier(premium, true);
        
        info!("💎 {} (프리미엄: {} BTC):", desc, premium);
        info!("   일반 처리 권장: {:?}", recommended_normal);
        info!("   긴급 처리 권장: {:?}", recommended_urgent);
    }

    // 4. 비즈니스 모델별 전략
    info!("\n🎯 Step 4: 비즈니스 모델별 비용 처리 전략");
    
    info!("💡 전략 1: 프리미엄에 비용 포함");
    info!("   - 장점: 간단한 구현, 예측 가능한 수익");
    info!("   - 단점: 고객에게 비용 전가");

    info!("💡 전략 2: 배치 처리로 비용 절약");
    info!("   - 장점: 최대 {}% 비용 절약", 
          ((AnchoringCostCalculator::estimate_cost(AnchoringTier::Instant, base_tx_fee) - 
            AnchoringCostCalculator::estimate_cost(AnchoringTier::Delayed, base_tx_fee)) /
           AnchoringCostCalculator::estimate_cost(AnchoringTier::Instant, base_tx_fee) * 100.0) as u32);
    info!("   - 단점: 앵커링 지연 시간");

    info!("💡 전략 3: 계층화 서비스");
    info!("   - 즉시 앵커링: 프리미엄 고객 대상");
    info!("   - 배치 앵커링: 일반 고객 대상");
    info!("   - 지연 앵커링: 가격 민감 고객 대상");

    // 5. 실제 비용 시뮬레이션
    info!("\n📈 Step 5: 일일 거래량별 비용 시뮬레이션");
    
    let daily_volumes = vec![10, 100, 1000];
    
    for volume in daily_volumes {
        let instant_cost = volume as f64 * AnchoringCostCalculator::estimate_cost(AnchoringTier::Instant, base_tx_fee);
        let batched_cost = (volume / 10) as f64 * base_tx_fee; // 10개씩 배치
        let delayed_cost = (volume / 50) as f64 * base_tx_fee; // 50개씩 배치
        
        info!("📊 일일 거래량 {}개 옵션:", volume);
        info!("   즉시 앵커링 총 비용: {} BTC", instant_cost);
        info!("   배치 앵커링 총 비용: {} BTC (절약: {} BTC)", batched_cost, instant_cost - batched_cost);
        info!("   지연 앵커링 총 비용: {} BTC (절약: {} BTC)", delayed_cost, instant_cost - delayed_cost);
    }

    info!("\n🎉 비용 처리 데모 완료!");
    info!("✅ 주요 인사이트:");
    info!("   - 배치 처리로 90% 이상 비용 절약 가능");
    info!("   - 계층화 서비스로 다양한 고객 니즈 충족");
    info!("   - 거래량이 많을수록 배치 처리의 효과 극대화");
    info!("   - 트랜잭션 비용을 프리미엄에 적절히 반영 중요");
}