use rocksdb::{DB, Options};
use serde::{Serialize, Deserialize};
use std::path::Path;
use tracing::{info, error};

use crate::models::*;
use defi_primitives::options::factory::CreateAndAnchorResponse;

/// 영속적 데이터 저장을 위한 RocksDB 래퍼
pub struct OptionStorage {
    db: DB,
}

impl OptionStorage {
    /// 새로운 스토리지 인스턴스 생성
    pub async fn new<P: AsRef<Path>>(path: P) -> Result<Self, String> {
        let mut opts = Options::default();
        opts.create_if_missing(true);
        opts.set_max_open_files(1000);
        
        match DB::open(&opts, &path) {
            Ok(db) => {
                info!("✅ RocksDB initialized at: {:?}", path.as_ref());
                Ok(Self { db })
            }
            Err(e) => {
                error!("❌ Failed to initialize RocksDB: {}", e);
                Err(format!("Database initialization failed: {}", e))
            }
        }
    }

    /// 옵션 상품 저장
    pub async fn save_option_product(&self, response: &CreateAndAnchorResponse) -> Result<(), String> {
        let key = format!("option:{}", response.option_id);
        
        let option_data = StoredOptionData {
            option_id: response.option_id.clone(),
            create_tx: response.create_tx.clone(),
            calculated_premium: response.calculated_premium,
            max_units: response.max_units,
            units_sold: 0, // 초기값
            expiry_timestamp: response.expiry_timestamp,
            bitcoin_anchor_txid: response.bitcoin_anchor_txid.clone(),
            bitvmx_program_hash: response.bitvmx_program_hash.clone(),
            created_at: chrono::Utc::now().timestamp() as u64,
            status: "ACTIVE".to_string(),
        };

        let serialized = match serde_json::to_vec(&option_data) {
            Ok(data) => data,
            Err(e) => return Err(format!("Serialization failed: {}", e)),
        };

        match self.db.put(&key, serialized) {
            Ok(_) => {
                info!("💾 Option product saved: {}", response.option_id);
                Ok(())
            }
            Err(e) => {
                error!("❌ Failed to save option product: {}", e);
                Err(format!("Database write failed: {}", e))
            }
        }
    }

    /// 구매 기록 저장
    pub async fn save_purchase_record(&self, record: &PurchaseRecord) -> Result<(), String> {
        let key = format!("purchase:{}", record.purchase_id);
        
        let serialized = match serde_json::to_vec(record) {
            Ok(data) => data,
            Err(e) => return Err(format!("Serialization failed: {}", e)),
        };

        match self.db.put(&key, serialized) {
            Ok(_) => {
                info!("💾 Purchase record saved: {}", record.purchase_id);
                
                // 옵션의 판매 수량 업데이트
                if let Err(e) = self.update_option_units_sold(&record.option_id, record.quantity).await {
                    error!("⚠️ Failed to update units sold: {}", e);
                }
                
                Ok(())
            }
            Err(e) => {
                error!("❌ Failed to save purchase record: {}", e);
                Err(format!("Database write failed: {}", e))
            }
        }
    }

    /// 옵션의 판매 수량 업데이트
    async fn update_option_units_sold(&self, option_id: &str, additional_units: u32) -> Result<(), String> {
        let key = format!("option:{}", option_id);
        
        // 기존 데이터 읽기
        let existing_data = match self.db.get(&key) {
            Ok(Some(data)) => data,
            Ok(None) => return Err("Option not found".to_string()),
            Err(e) => return Err(format!("Database read failed: {}", e)),
        };

        // 역직렬화
        let mut option_data: StoredOptionData = match serde_json::from_slice(&existing_data) {
            Ok(data) => data,
            Err(e) => return Err(format!("Deserialization failed: {}", e)),
        };

        // 판매 수량 업데이트
        option_data.units_sold += additional_units;
        
        // 모든 수량이 판매되었으면 상태 변경
        if option_data.units_sold >= option_data.max_units {
            option_data.status = "SOLD_OUT".to_string();
        }

        // 다시 저장
        let serialized = match serde_json::to_vec(&option_data) {
            Ok(data) => data,
            Err(e) => return Err(format!("Serialization failed: {}", e)),
        };

        match self.db.put(&key, serialized) {
            Ok(_) => Ok(()),
            Err(e) => Err(format!("Database write failed: {}", e)),
        }
    }

    /// 활성 옵션 리스트 조회
    pub async fn get_active_options(&self) -> Result<Vec<OptionListItem>, String> {
        let mut options = Vec::new();
        let current_time = chrono::Utc::now().timestamp() as u64;
        let current_btc_price = 52000.0; // TODO: 실제 오라클 가격

        let iter = self.db.prefix_iterator("option:");
        
        for item in iter {
            match item {
                Ok((key, value)) => {
                    let option_data: StoredOptionData = match serde_json::from_slice(&value) {
                        Ok(data) => data,
                        Err(_) => continue, // 파싱 실패한 데이터는 건너뛰기
                    };

                    // 만료되지 않은 활성 옵션만 포함
                    if option_data.expiry_timestamp > current_time && option_data.status == "ACTIVE" {
                        let days_to_expiry = ((option_data.expiry_timestamp - current_time) / 86400) as u32;
                        let is_itm = self.calculate_is_itm(&option_data, current_btc_price);
                        
                        options.push(OptionListItem {
                            option_id: option_data.option_id,
                            option_type: format!("{:?}", option_data.create_tx.option_type),
                            underlying: option_data.create_tx.underlying,
                            strike: option_data.create_tx.strike,
                            expiry_date: self.format_timestamp(option_data.expiry_timestamp),
                            days_to_expiry,
                            premium_per_unit_btc: option_data.calculated_premium,
                            available_units: option_data.max_units - option_data.units_sold,
                            total_units: option_data.max_units,
                            initial_iv: option_data.create_tx.initial_iv,
                            current_btc_price,
                            is_in_the_money: is_itm,
                            estimated_max_payout: self.calculate_max_payout(&option_data, current_btc_price),
                            bitcoin_tx_id: option_data.bitcoin_anchor_txid,
                            bitvmx_verification: "SUCCESS".to_string(),
                        });
                    }
                }
                Err(_) => continue,
            }
        }

        Ok(options)
    }

    /// 특정 옵션 상세 정보 조회
    pub async fn get_option_details(&self, option_id: &str) -> Result<Option<OptionDetails>, String> {
        let key = format!("option:{}", option_id);
        
        let data = match self.db.get(&key) {
            Ok(Some(data)) => data,
            Ok(None) => return Ok(None),
            Err(e) => return Err(format!("Database read failed: {}", e)),
        };

        let option_data: StoredOptionData = match serde_json::from_slice(&data) {
            Ok(data) => data,
            Err(e) => return Err(format!("Deserialization failed: {}", e)),
        };

        let current_time = chrono::Utc::now().timestamp() as u64;
        let current_btc_price = 52000.0; // TODO: 실제 오라클 가격
        let days_to_expiry = if option_data.expiry_timestamp > current_time {
            ((option_data.expiry_timestamp - current_time) / 86400) as i64
        } else {
            0
        };

        let details = OptionDetails {
            option_id: option_data.option_id,
            option_type: format!("{:?}", option_data.create_tx.option_type),
            underlying: option_data.create_tx.underlying,
            strike: option_data.create_tx.strike,
            unit: option_data.create_tx.unit,
            expiry_timestamp: option_data.expiry_timestamp,
            expiry_date: self.format_timestamp(option_data.expiry_timestamp),
            created_at: option_data.created_at,
            premium_per_unit_btc: option_data.calculated_premium,
            max_units: option_data.max_units,
            units_sold: option_data.units_sold,
            available_units: option_data.max_units - option_data.units_sold,
            status: option_data.status,
            issuer: option_data.create_tx.issuer,
            initial_iv: option_data.create_tx.initial_iv,
            oracle_providers: option_data.create_tx.oracle_ids,
            current_btc_price,
            is_in_the_money: self.calculate_is_itm(&option_data, current_btc_price),
            estimated_max_payout: self.calculate_max_payout(&option_data, current_btc_price),
            days_to_expiry,
            bitcoin_tx_id: option_data.bitcoin_anchor_txid,
            bitvmx_program_hash: option_data.bitvmx_program_hash,
            bitvmx_verification_status: "SUCCESS".to_string(),
            bitvmx_tx_id: None, // TODO: 실제 BitVMX 트랜잭션 ID
            total_volume_btc: (option_data.units_sold as f64) * option_data.calculated_premium,
            unique_buyers: option_data.units_sold, // 단순화: 1구매자=1단위
            last_trade_at: if option_data.units_sold > 0 { Some(current_time) } else { None },
        };

        Ok(Some(details))
    }

    /// 서비스 통계 조회 (헬스체크용)
    pub async fn get_service_stats(&self) -> (u32, f64) {
        let mut active_options = 0u32;
        let mut total_volume = 0f64;
        let current_time = chrono::Utc::now().timestamp() as u64;

        let iter = self.db.prefix_iterator("option:");
        
        for item in iter {
            if let Ok((_, value)) = item {
                if let Ok(option_data) = serde_json::from_slice::<StoredOptionData>(&value) {
                    if option_data.expiry_timestamp > current_time {
                        active_options += 1;
                        total_volume += (option_data.units_sold as f64) * option_data.calculated_premium;
                    }
                }
            }
        }

        (active_options, total_volume)
    }

    // 헬퍼 메서드들
    fn calculate_is_itm(&self, option_data: &StoredOptionData, current_price: f64) -> bool {
        use defi_primitives::options::types::OptionType;
        match option_data.create_tx.option_type {
            OptionType::Call => current_price > option_data.create_tx.strike as f64,
            OptionType::Put => current_price < option_data.create_tx.strike as f64,
        }
    }

    fn calculate_max_payout(&self, option_data: &StoredOptionData, current_price: f64) -> f64 {
        use defi_primitives::options::types::OptionType;
        match option_data.create_tx.option_type {
            OptionType::Call => {
                if current_price > option_data.create_tx.strike as f64 {
                    current_price - option_data.create_tx.strike as f64
                } else {
                    0.0
                }
            },
            OptionType::Put => {
                if current_price < option_data.create_tx.strike as f64 {
                    option_data.create_tx.strike as f64 - current_price
                } else {
                    0.0
                }
            },
        }
    }

    fn format_timestamp(&self, timestamp: u64) -> String {
        chrono::DateTime::from_timestamp(timestamp as i64, 0)
            .unwrap_or_default()
            .format("%Y-%m-%dT%H:%M:%SZ")
            .to_string()
    }
}

/// 데이터베이스에 저장되는 옵션 데이터 구조
#[derive(Debug, Serialize, Deserialize)]
struct StoredOptionData {
    pub option_id: String,
    pub create_tx: defi_primitives::options::transaction::CreateOptionTx,
    pub calculated_premium: f64,
    pub max_units: u32,
    pub units_sold: u32,
    pub expiry_timestamp: u64,
    pub bitcoin_anchor_txid: Option<String>,
    pub bitvmx_program_hash: String,
    pub created_at: u64,
    pub status: String, // ACTIVE, SOLD_OUT, EXPIRED, CANCELLED
}