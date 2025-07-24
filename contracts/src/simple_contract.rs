use anyhow::Result;
use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use oracle_vm_common::types::OptionType;

/// 옵션 상태
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum OptionStatus {
    Active,
    Expired,
    Settled,
}

/// 간단한 옵션 데이터
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SimpleOption {
    pub option_id: String,
    pub option_type: OptionType,
    pub strike_price: u64, // USD cents
    pub quantity: u64,     // satoshis
    pub premium_paid: u64, // satoshis
    pub expiry_height: u32,
    pub status: OptionStatus,
    pub user_id: String, // 사용자 식별자
}

/// 간단한 풀 상태
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SimplePoolState {
    pub total_liquidity: u64,         // satoshis
    pub locked_collateral: u64,       // satoshis
    pub available_liquidity: u64,     // satoshis
    pub total_premium_collected: u64, // satoshis
    pub total_payout: u64,            // satoshis
    pub active_options: u32,
}

impl SimplePoolState {
    pub fn new() -> Self {
        Self {
            total_liquidity: 0,
            locked_collateral: 0,
            available_liquidity: 0,
            total_premium_collected: 0,
            total_payout: 0,
            active_options: 0,
        }
    }

    pub fn utilization_rate(&self) -> f64 {
        if self.total_liquidity == 0 {
            return 0.0;
        }
        (self.locked_collateral as f64 / self.total_liquidity as f64) * 100.0
    }
}

impl Default for SimplePoolState {
    fn default() -> Self {
        Self::new()
    }
}

/// 간단한 컨트랙트 관리자
pub struct SimpleContractManager {
    pub options: HashMap<String, SimpleOption>,
    pub pool_state: SimplePoolState,
}

impl SimpleContractManager {
    pub fn new() -> Self {
        Self {
            options: HashMap::new(),
            pool_state: SimplePoolState::new(),
        }
    }

}

impl Default for SimpleContractManager {
    fn default() -> Self {
        Self::new()
    }
}

impl SimpleContractManager {
    /// 유동성 추가
    pub fn add_liquidity(&mut self, amount: u64) -> Result<()> {
        self.pool_state.total_liquidity += amount;
        self.pool_state.available_liquidity += amount;
        Ok(())
    }

    /// 옵션 생성
    #[allow(clippy::too_many_arguments)]
    pub fn create_option(
        &mut self,
        option_id: String,
        option_type: OptionType,
        strike_price: u64,
        quantity: u64,
        premium: u64,
        expiry_height: u32,
        user_id: String,
    ) -> Result<()> {
        // 담보금 계산
        let collateral = match option_type {
            OptionType::Call => quantity,
            OptionType::Put => (strike_price * quantity) / 100_000_000, // USD to BTC conversion
        };

        // 사용 가능한 유동성 확인
        if self.pool_state.available_liquidity < collateral {
            return Err(anyhow::anyhow!("Insufficient liquidity"));
        }

        // 옵션 생성
        let option = SimpleOption {
            option_id: option_id.clone(),
            option_type,
            strike_price,
            quantity,
            premium_paid: premium,
            expiry_height,
            status: OptionStatus::Active,
            user_id,
        };

        // 상태 업데이트
        self.options.insert(option_id, option);
        self.pool_state.available_liquidity -= collateral;
        self.pool_state.locked_collateral += collateral;
        self.pool_state.total_premium_collected += premium;
        self.pool_state.total_liquidity += premium;
        self.pool_state.available_liquidity += premium; // 프리미엄은 사용 가능한 유동성에 추가
        self.pool_state.active_options += 1;

        Ok(())
    }

    /// 옵션 생성 with OP_RETURN anchoring
    #[allow(clippy::too_many_arguments)]
    pub async fn create_option_with_anchor(
        &mut self,
        option_id: String,
        option_type: OptionType,
        strike_price: u64,
        quantity: u64,
        premium: u64,
        expiry_height: u32,
        user_id: String,
        anchoring_service: &crate::bitcoin_anchoring::BitcoinAnchoringService,
    ) -> Result<String> {
        // 먼저 옵션을 생성
        self.create_option(
            option_id.clone(),
            option_type,
            strike_price,
            quantity,
            premium,
            expiry_height,
            user_id,
        )?;

        // 생성된 옵션을 가져와서 앵커링
        let option = self.options.get(&option_id)
            .ok_or_else(|| anyhow::anyhow!("Option not found after creation"))?;
        
        // Bitcoin에 앵커링
        let txid = anchoring_service.anchor_option(option).await?;
        
        log::info!("Option {} anchored with txid: {}", option_id, txid);
        
        Ok(txid)
    }

    /// 옵션 정산
    pub fn settle_option(&mut self, option_id: &str, spot_price: u64) -> Result<u64> {
        let option = self
            .options
            .get_mut(option_id)
            .ok_or_else(|| anyhow::anyhow!("Option not found"))?;

        if option.status != OptionStatus::Active {
            return Err(anyhow::anyhow!("Option not active"));
        }

        // ITM 여부 확인
        let is_itm = match option.option_type {
            OptionType::Call => spot_price > option.strike_price,
            OptionType::Put => spot_price < option.strike_price,
        };

        let payout = if is_itm {
            let intrinsic_value = match option.option_type {
                OptionType::Call => spot_price - option.strike_price,
                OptionType::Put => option.strike_price - spot_price,
            };
            // USD cents를 satoshis로 변환
            (intrinsic_value * option.quantity) / 100_000_000
        } else {
            0
        };

        // 담보금 계산
        let collateral = match option.option_type {
            OptionType::Call => option.quantity,
            OptionType::Put => (option.strike_price * option.quantity) / 100_000_000,
        };

        // 상태 업데이트
        option.status = OptionStatus::Settled;
        self.pool_state.locked_collateral -= collateral;

        if payout > 0 {
            self.pool_state.total_payout += payout;
            self.pool_state.total_liquidity -= payout;
            // 잔여 담보금은 풀로 반환
            self.pool_state.available_liquidity += collateral - payout;
        } else {
            // OTM인 경우 전체 담보금이 풀로 반환
            self.pool_state.available_liquidity += collateral;
        }

        self.pool_state.active_options -= 1;

        Ok(payout)
    }

    /// 만료된 옵션 조회
    pub fn get_expired_options(&self, current_height: u32) -> Vec<&SimpleOption> {
        self.options
            .values()
            .filter(|option| {
                option.status == OptionStatus::Active && current_height >= option.expiry_height
            })
            .collect()
    }

    /// 시스템 상태 조회
    pub fn get_system_status(&self) -> serde_json::Value {
        serde_json::json!({
            "pool_state": self.pool_state,
            "total_options": self.options.len(),
            "active_options": self.pool_state.active_options,
            "utilization_rate": format!("{:.2}%", self.pool_state.utilization_rate()),
            "profit_loss": self.pool_state.total_premium_collected as i64 - self.pool_state.total_payout as i64
        })
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_call_option_itm() {
        let mut manager = SimpleContractManager::new();

        // 유동성 추가: 1 BTC
        manager.add_liquidity(100_000_000).unwrap();

        // Call 옵션 생성: Strike $70,000, Quantity 0.1 BTC, Premium 0.0025 BTC
        manager
            .create_option(
                "CALL-001".to_string(),
                OptionType::Call,
                7_000_000,  // $70,000 in cents
                10_000_000, // 0.1 BTC in sats
                250_000,    // 0.0025 BTC premium
                800_000,
                "user1".to_string(),
            )
            .unwrap();

        // 정산: Spot $72,000 (ITM)
        let payout = manager.settle_option("CALL-001", 7_200_000).unwrap();

        // $2,000 profit on 0.1 BTC ≈ 277,777 sats (assuming $72k BTC price)
        assert!(payout > 0);
        assert_eq!(manager.pool_state.active_options, 0);

        println!("Call ITM Payout: {} sats", payout);
        println!(
            "Pool utilization: {:.2}%",
            manager.pool_state.utilization_rate()
        );
    }

    #[test]
    fn test_put_option_itm() {
        let mut manager = SimpleContractManager::new();

        // 유동성 추가: 1 BTC
        manager.add_liquidity(100_000_000).unwrap();

        // Put 옵션 생성: Strike $65,000, Quantity 0.2 BTC
        manager
            .create_option(
                "PUT-001".to_string(),
                OptionType::Put,
                6_500_000,  // $65,000 in cents
                20_000_000, // 0.2 BTC in sats
                180_000,    // 0.0018 BTC premium
                800_000,
                "user2".to_string(),
            )
            .unwrap();

        // 정산: Spot $63,000 (ITM)
        let payout = manager.settle_option("PUT-001", 6_300_000).unwrap();

        // $2,000 profit on 0.2 BTC
        assert!(payout > 0);

        println!("Put ITM Payout: {} sats", payout);
        println!("System status: {}", manager.get_system_status());
    }

    #[test]
    fn test_option_otm() {
        let mut manager = SimpleContractManager::new();

        manager.add_liquidity(100_000_000).unwrap();

        // Call 옵션 생성
        manager
            .create_option(
                "CALL-OTM".to_string(),
                OptionType::Call,
                7_500_000,  // $75,000 strike
                10_000_000, // 0.1 BTC
                300_000,    // premium
                800_000,
                "user3".to_string(),
            )
            .unwrap();

        // 정산: Spot $73,000 (OTM)
        let payout = manager.settle_option("CALL-OTM", 7_300_000).unwrap();

        assert_eq!(payout, 0);
        assert_eq!(manager.pool_state.active_options, 0);

        println!("Call OTM Payout: {} sats (should be 0)", payout);
    }
}
