use std::sync::Arc;
use anyhow::Result;
use crate::connectors_real::{OracleConnector, CalculationConnector, ContractConnector, BitVMXConnector};
use crate::events::{EventBus, Event};

/// Update 사이클 플로우: Oracle → Calculation → Frontend
#[derive(Clone)]
pub struct UpdateFlow {
    oracle: Arc<OracleConnector>,
    calc: Arc<CalculationConnector>,
    event_bus: Arc<EventBus>,
}

impl UpdateFlow {
    pub fn new(
        oracle: Arc<OracleConnector>,
        calc: Arc<CalculationConnector>,
        event_bus: Arc<EventBus>,
    ) -> Self {
        Self { oracle, calc, event_bus }
    }

    pub async fn execute(&self) -> Result<f64> {
        // 1. Oracle에서 가격 가져오기
        let price = self.oracle.get_consensus_price().await?;
        
        // 2. Calculation 모듈 업데이트
        self.calc.update_price(price).await?;
        
        // 3. 이벤트 발행
        self.event_bus.emit(Event::PriceUpdate { 
            price,
            timestamp: chrono::Utc::now(),
        }).await;
        
        Ok(price)
    }
}

/// Trading 플로우: 옵션 생성 및 거래
#[derive(Clone)]
pub struct TradingFlow {
    calc: Arc<CalculationConnector>,
    contract: Arc<ContractConnector>,
    event_bus: Arc<EventBus>,
}

impl TradingFlow {
    pub fn new(
        calc: Arc<CalculationConnector>,
        contract: Arc<ContractConnector>,
        event_bus: Arc<EventBus>,
    ) -> Self {
        Self { calc, contract, event_bus }
    }

    pub async fn create_option(&self, params: OptionParams) -> Result<String> {
        // 1. Calculation에서 프리미엄 계산
        let premium = self.calc.calculate_premium(&params).await?;
        
        // 2. Contract에서 옵션 생성
        let option_id = self.contract.create_option(params.clone(), premium).await?;
        
        // 3. 이벤트 발행
        self.event_bus.emit(Event::OptionCreated { 
            option_id: option_id.clone(),
            params,
        }).await;
        
        Ok(option_id)
    }

    pub async fn check_new_options(&self) {
        // 실제로는 API 요청이나 WebSocket으로 처리
        tracing::debug!("Checking for new option requests...");
    }
}

/// Settlement 플로우: 만기 시 정산
#[derive(Clone)]
pub struct SettlementFlow {
    oracle: Arc<OracleConnector>,
    bitvmx: Arc<BitVMXConnector>,
    contract: Arc<ContractConnector>,
}

impl SettlementFlow {
    pub fn new(
        oracle: Arc<OracleConnector>,
        bitvmx: Arc<BitVMXConnector>,
        contract: Arc<ContractConnector>,
    ) -> Self {
        Self { oracle, bitvmx, contract }
    }

    pub async fn execute_settlement(&self, option_id: &str) -> Result<()> {
        // 1. Oracle에서 최종 가격 확인
        let final_price = self.oracle.get_consensus_price().await?;
        
        // 2. BitVMX에서 증명 생성
        let proof = self.bitvmx.generate_settlement_proof(option_id, final_price).await?;
        
        // 3. Contract에 정산 실행
        self.contract.execute_settlement(option_id, proof).await?;
        
        // 4. Calculation 모듈에 상태 업데이트
        // (Pool 상태 갱신 등)
        
        tracing::info!("Settlement completed for option {}", option_id);
        Ok(())
    }
}

#[derive(Clone, Debug)]
pub struct OptionParams {
    pub option_type: String,
    pub strike: f64,
    pub expiry: u32,
    pub quantity: f64,
}