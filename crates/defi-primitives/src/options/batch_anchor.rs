//! 배치 앵커링 서비스 - 트랜잭션 비용 절약
//! 
//! 여러 옵션을 하나의 트랜잭션으로 묶어서 앵커링하여 비용을 절약합니다.

use std::collections::HashMap;
use tokio::sync::Mutex;
use tokio::time::{interval, Duration};
use tracing::{info, error, warn};
use serde::{Serialize, Deserialize};

use bitcoin_client::BitcoinClient;
use super::transaction::CreateOptionTx;

/// 앵커링 계층 - 비용과 속도의 트레이드오프
#[derive(Debug, Clone, Copy, Serialize, Deserialize)]
pub enum AnchoringTier {
    /// 즉시 앵커링 (고비용, 1-2분)
    Instant,
    /// 배치 앵커링 (중간비용, 10분마다)
    Batched,
    /// 지연 앵커링 (저비용, 1시간마다)
    Delayed,
}

impl AnchoringTier {
    /// 계층별 추가 수수료
    pub fn fee_multiplier(&self) -> f64 {
        match self {
            AnchoringTier::Instant => 1.5,  // 50% 프리미엄
            AnchoringTier::Batched => 1.0,   // 기본
            AnchoringTier::Delayed => 0.7,   // 30% 할인
        }
    }

    /// 예상 앵커링 시간 (분)
    pub fn estimated_time_minutes(&self) -> u32 {
        match self {
            AnchoringTier::Instant => 2,
            AnchoringTier::Batched => 10,
            AnchoringTier::Delayed => 60,
        }
    }
}

/// 배치 앵커링 대기 중인 옵션
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PendingOption {
    pub option_id: String,
    pub create_tx: CreateOptionTx,
    pub tier: AnchoringTier,
    pub submitted_at: u64,
    pub callback_url: Option<String>,
}

/// 배치 앵커링 관리자
pub struct BatchAnchoringService {
    bitcoin_client: BitcoinClient,
    pending_batched: Mutex<Vec<PendingOption>>,
    pending_delayed: Mutex<Vec<PendingOption>>,
    anchored_results: Mutex<HashMap<String, String>>, // option_id -> txid
}

impl BatchAnchoringService {
    pub fn new(bitcoin_client: BitcoinClient) -> Self {
        Self {
            bitcoin_client,
            pending_batched: Mutex::new(Vec::new()),
            pending_delayed: Mutex::new(Vec::new()),
            anchored_results: Mutex::new(HashMap::new()),
        }
    }

    /// 배치 서비스 시작 (백그라운드 태스크)
    pub async fn start_batch_processing(&self) {
        let batched_interval = interval(Duration::from_secs(600)); // 10분
        let delayed_interval = interval(Duration::from_secs(3600)); // 1시간

        tokio::spawn({
            let service = self.clone();
            async move {
                let mut batched_timer = batched_interval;
                loop {
                    batched_timer.tick().await;
                    if let Err(e) = service.process_batched_queue().await {
                        error!("❌ Batched anchoring failed: {}", e);
                    }
                }
            }
        });

        tokio::spawn({
            let service = self.clone();
            async move {
                let mut delayed_timer = delayed_interval;
                loop {
                    delayed_timer.tick().await;
                    if let Err(e) = service.process_delayed_queue().await {
                        error!("❌ Delayed anchoring failed: {}", e);
                    }
                }
            }
        });

        info!("✅ Batch anchoring service started");
    }

    /// 옵션을 큐에 추가
    pub async fn add_to_queue(&self, pending: PendingOption) -> Result<(), String> {
        match pending.tier {
            AnchoringTier::Instant => {
                // 즉시 앵커링 수행
                self.anchor_immediately(&pending).await
            }
            AnchoringTier::Batched => {
                let mut queue = self.pending_batched.lock().await;
                queue.push(pending);
                info!("📝 Added to batched queue (size: {})", queue.len());
                Ok(())
            }
            AnchoringTier::Delayed => {
                let mut queue = self.pending_delayed.lock().await;
                queue.push(pending);
                info!("📝 Added to delayed queue (size: {})", queue.len());
                Ok(())
            }
        }
    }

    /// 즉시 앵커링 처리
    async fn anchor_immediately(&self, pending: &PendingOption) -> Result<(), String> {
        info!("🚀 Immediate anchoring: {}", pending.option_id);

        let op_return_data = self.create_option_op_return(&pending.create_tx);
        
        match self.bitcoin_client.send_op_return_transaction(&op_return_data).await {
            Ok(txid) => {
                let mut results = self.anchored_results.lock().await;
                results.insert(pending.option_id.clone(), txid.clone());
                info!("✅ Immediate anchoring successful: {} -> {}", pending.option_id, txid);
                Ok(())
            }
            Err(e) => {
                error!("❌ Immediate anchoring failed: {}", e);
                Err(e)
            }
        }
    }

    /// 배치 큐 처리 (10분마다)
    async fn process_batched_queue(&self) -> Result<(), String> {
        let mut queue = self.pending_batched.lock().await;
        
        if queue.is_empty() {
            return Ok(());
        }

        info!("🔄 Processing batched queue: {} options", queue.len());

        // 배치 데이터 생성 (최대 10개씩)
        let batch_size = 10.min(queue.len());
        let batch: Vec<PendingOption> = queue.drain(0..batch_size).collect();
        drop(queue); // 락 해제

        let combined_data = batch.iter()
            .map(|opt| format!("CREATE:{}:{}", opt.option_id, opt.create_tx.strike))
            .collect::<Vec<_>>()
            .join("|");

        match self.bitcoin_client.send_op_return_transaction(&combined_data).await {
            Ok(txid) => {
                // 모든 배치 옵션의 결과 저장
                let mut results = self.anchored_results.lock().await;
                for option in batch {
                    results.insert(option.option_id.clone(), txid.clone());
                    info!("✅ Batched anchoring: {} -> {}", option.option_id, txid);
                }
                Ok(())
            }
            Err(e) => {
                // 실패한 경우 다시 큐에 추가
                let mut queue = self.pending_batched.lock().await;
                queue.extend(batch);
                error!("❌ Batched anchoring failed, re-queued {} options", queue.len());
                Err(e)
            }
        }
    }

    /// 지연 큐 처리 (1시간마다)
    async fn process_delayed_queue(&self) -> Result<(), String> {
        let mut queue = self.pending_delayed.lock().await;
        
        if queue.is_empty() {
            return Ok(());
        }

        info!("🔄 Processing delayed queue: {} options", queue.len());

        // 대량 배치 처리 (최대 50개)
        let batch_size = 50.min(queue.len());
        let batch: Vec<PendingOption> = queue.drain(0..batch_size).collect();
        drop(queue);

        // 압축된 형태로 데이터 생성
        let combined_data = format!("BATCH_CREATE:{}", 
            batch.iter()
                .map(|opt| format!("{}:{}", opt.option_id, opt.create_tx.strike))
                .collect::<Vec<_>>()
                .join(",")
        );

        match self.bitcoin_client.send_op_return_transaction(&combined_data).await {
            Ok(txid) => {
                let mut results = self.anchored_results.lock().await;
                for option in batch {
                    results.insert(option.option_id.clone(), txid.clone());
                    info!("✅ Delayed anchoring: {} -> {}", option.option_id, txid);
                }
                Ok(())
            }
            Err(e) => {
                let mut queue = self.pending_delayed.lock().await;
                queue.extend(batch);
                error!("❌ Delayed anchoring failed, re-queued {} options", queue.len());
                Err(e)
            }
        }
    }

    /// 앵커링 결과 조회
    pub async fn get_anchoring_result(&self, option_id: &str) -> Option<String> {
        let results = self.anchored_results.lock().await;
        results.get(option_id).cloned()
    }

    /// 대기 중인 옵션 수 조회
    pub async fn get_queue_sizes(&self) -> (usize, usize) {
        let batched = self.pending_batched.lock().await.len();
        let delayed = self.pending_delayed.lock().await.len();
        (batched, delayed)
    }

    /// OP_RETURN 데이터 생성
    fn create_option_op_return(&self, create_tx: &CreateOptionTx) -> String {
        format!("CREATE:{}:{}:{}", 
            create_tx.option_type as u8,
            create_tx.strike,
            chrono::Utc::now().timestamp() as u64 + 86400
        )
    }
}

// Clone trait 구현 (Arc 사용을 위해) - BitcoinClient가 Clone을 지원하지 않으므로 제거

/// 비용 계산기
pub struct AnchoringCostCalculator;

impl AnchoringCostCalculator {
    /// 계층별 예상 비용 계산
    pub fn estimate_cost(tier: AnchoringTier, base_tx_fee: f64) -> f64 {
        match tier {
            AnchoringTier::Instant => base_tx_fee * tier.fee_multiplier(), // 개별 트랜잭션
            AnchoringTier::Batched => base_tx_fee / 10.0 * tier.fee_multiplier(), // 10개 배치
            AnchoringTier::Delayed => base_tx_fee / 50.0 * tier.fee_multiplier(), // 50개 배치
        }
    }

    /// 옵션 생성 시 권장 계층 제안
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