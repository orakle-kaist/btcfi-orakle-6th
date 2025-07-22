use serde::{Deserialize, Serialize};
use uuid::Uuid;

/// 사용자가 요청하는 CREATE 스키마
#[derive(Debug, Deserialize)]
pub struct CreateOptionRequest {
    pub tx_type: String,         // "CREATE"
    pub option_id: String,       // "abc123"
    pub option_type: String,     // "CALL" or "PUT"
    pub strike: u64,             // 52000
    pub expiry: u64,             // Unix timestamp
    pub unit: f64,               // 1.0
    
    // 추가 필수 파라미터
    pub max_units: Option<u32>,              // 최대 수량 (기본값: 100)
    pub initial_iv: Option<f64>,             // 초기 변동성 (기본값: 0.75)
    pub premium_adjustment: Option<f64>,      // 프리미엄 조정 (기본값: 1.0)
    pub underlying: Option<String>,          // 기초자산 (기본값: "BTCUSD")
}

/// API 응답 구조체
#[derive(Debug, Serialize)]
pub struct CreateOptionResponse {
    pub success: bool,
    pub option_id: String,
    pub bitcoin_tx_id: Option<String>,
    pub bitvmx_tx_id: Option<String>,
    pub bitvmx_program_hash: String,
    pub calculated_premium_btc: f64,
    pub max_units: u32,
    pub expiry_timestamp: u64,
    pub verification_status: String,
    pub message: String,
}

/// 옵션 구매 요청
#[derive(Debug, Deserialize)]
pub struct BuyOptionRequest {
    pub option_id: String,
    pub quantity: u32,
    pub max_premium_btc: f64,    // 슬리피지 보호
    pub buyer_address: String,   // 구매자 주소
}

/// 옵션 구매 응답
#[derive(Debug, Serialize)]
pub struct BuyOptionResponse {
    pub success: bool,
    pub purchase_id: String,
    pub option_id: String,
    pub quantity: u32,
    pub total_premium_btc: f64,
    pub average_price_btc: f64,
    pub buyer_address: String,
    pub expires_at: u64,
    pub current_btc_price: f64,
    pub is_in_the_money: bool,
    pub estimated_payout: f64,
    pub message: String,
}

/// 옵션 리스트 아이템 (공개 정보)
#[derive(Debug, Serialize)]
pub struct OptionListItem {
    pub option_id: String,
    pub option_type: String,
    pub underlying: String,
    pub strike: u64,
    pub expiry_date: String,
    pub days_to_expiry: u32,
    pub premium_per_unit_btc: f64,
    pub available_units: u32,
    pub total_units: u32,
    pub initial_iv: f64,
    pub current_btc_price: f64,
    pub is_in_the_money: bool,
    pub estimated_max_payout: f64,
    pub bitcoin_tx_id: Option<String>,
    pub bitvmx_verification: String,
}

/// 옵션 상세 정보
#[derive(Debug, Serialize)]
pub struct OptionDetails {
    pub option_id: String,
    pub option_type: String,
    pub underlying: String,
    pub strike: u64,
    pub unit: f64,
    pub expiry_timestamp: u64,
    pub expiry_date: String,
    pub created_at: u64,
    pub premium_per_unit_btc: f64,
    pub max_units: u32,
    pub units_sold: u32,
    pub available_units: u32,
    pub status: String,
    pub issuer: String,
    pub initial_iv: f64,
    pub oracle_providers: Vec<String>,
    pub current_btc_price: f64,
    pub is_in_the_money: bool,
    pub estimated_max_payout: f64,
    pub days_to_expiry: i64,
    
    // 블록체인 정보
    pub bitcoin_tx_id: Option<String>,
    pub bitvmx_program_hash: String,
    pub bitvmx_verification_status: String,
    pub bitvmx_tx_id: Option<String>,
    
    // 성과 지표
    pub total_volume_btc: f64,
    pub unique_buyers: u32,
    pub last_trade_at: Option<u64>,
}

/// 헬스체크 응답
#[derive(Debug, Serialize)]
pub struct HealthResponse {
    pub status: String,
    pub timestamp: u64,
    pub version: String,
    pub bitcoin_node_connected: bool,
    pub bitvmx_service_healthy: bool,
    pub database_connected: bool,
    pub active_options: u32,
    pub total_volume_btc: f64,
}

/// 에러 응답
#[derive(Debug, Serialize)]
pub struct ErrorResponse {
    pub success: bool,
    pub error: String,
    pub error_code: String,
    pub details: Option<String>,
}

/// 내부 구매 기록
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PurchaseRecord {
    pub purchase_id: String,
    pub option_id: String,
    pub buyer_address: String,
    pub quantity: u32,
    pub premium_btc_per_unit: f64,
    pub total_premium_btc: f64,
    pub purchased_at: u64,
    pub expires_at: u64,
    pub btc_price_at_purchase: f64,
}

impl CreateOptionRequest {
    /// 내부 OptionFactory 형식으로 변환
    pub fn to_internal_request(&self) -> Result<defi_primitives::options::factory::CreateProductRequest, String> {
        use defi_primitives::options::types::OptionType;
        
        let option_type = match self.option_type.to_uppercase().as_str() {
            "CALL" => OptionType::Call,
            "PUT" => OptionType::Put,
            _ => return Err("Invalid option_type: must be CALL or PUT".to_string()),
        };
        
        let now = chrono::Utc::now().timestamp() as u64;
        let days_to_expiry = ((self.expiry - now) / 86400) as u32;
        
        if days_to_expiry == 0 {
            return Err("Option has already expired".to_string());
        }
        
        if days_to_expiry > 365 {
            return Err("Option expiry cannot be more than 1 year".to_string());
        }
        
        Ok(defi_primitives::options::factory::CreateProductRequest {
            option_type,
            underlying: self.underlying.clone().unwrap_or("BTCUSD".to_string()),
            strike: self.strike,
            days_to_expiry,
            initial_iv: self.initial_iv.unwrap_or(0.75),
            max_units: self.max_units.unwrap_or(100),
            premium_adjustment: self.premium_adjustment,
        })
    }
}