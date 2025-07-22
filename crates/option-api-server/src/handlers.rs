use std::sync::Arc;
use tokio::sync::Mutex;
use warp::{Reply, reply};
use tracing::{info, error, warn};
use uuid::Uuid;

use crate::models::*;
use crate::storage::OptionStorage;
use defi_primitives::options::{
    factory::{OptionFactory, CreateProductRequest},
    buy_service::{OptionBuyService, BuyOptionRequest as InternalBuyRequest},
    types::OptionType,
};
use bitcoin_client::{BitcoinClient, BitcoinConfig};

pub type StorageRef = Arc<Mutex<OptionStorage>>;

/// 새로운 옵션 상품 생성 핸들러
pub async fn create_option_handler(
    request: CreateOptionRequest,
    storage: StorageRef,
) -> Result<impl Reply, warp::Rejection> {
    info!("🎯 Creating new option product: {:?}", request.option_id);
    
    // 입력 유효성 검사
    if request.tx_type != "CREATE" {
        return Ok(reply::with_status(
            reply::json(&ErrorResponse {
                success: false,
                error: "Invalid tx_type".to_string(),
                error_code: "INVALID_TX_TYPE".to_string(),
                details: Some("tx_type must be 'CREATE'".to_string()),
            }),
            warp::http::StatusCode::BAD_REQUEST,
        ));
    }

    // 내부 형식으로 변환
    let internal_request = match request.to_internal_request() {
        Ok(req) => req,
        Err(e) => {
            return Ok(reply::with_status(
                reply::json(&ErrorResponse {
                    success: false,
                    error: e,
                    error_code: "REQUEST_VALIDATION_ERROR".to_string(),
                    details: None,
                }),
                warp::http::StatusCode::BAD_REQUEST,
            ));
        }
    };

    // Bitcoin 클라이언트 설정 (regtest)
    let bitcoin_config = BitcoinConfig {
        rpc_url: "http://localhost:18443".to_string(),
        rpc_user: "bitcoin".to_string(),
        rpc_password: "bitcoin".to_string(),
        network: bitcoin_client::Network::Regtest,
    };

    // OptionFactory 초기화 (Bitcoin + BitVMX 통합)
    let mut factory = OptionFactory::new_with_full_integration(
        "bc1q_service_operator".to_string(),
        bitcoin_config,
    );

    // 현재 BTC 가격 (실제로는 오라클에서 가져와야 함)
    let current_btc_price = 52000.0;

    // 옵션 상품 생성 및 앵커링
    // TODO: 오라클에서 실제 BTC 가격 가져오기
    match factory.create_and_anchor(internal_request, current_btc_price).await {
        Ok(response) => {
            info!("✅ Option product created successfully: {}", response.option_id);
            
            // 데이터베이스에 저장
            let mut storage_guard = storage.lock().await;
            if let Err(e) = storage_guard.save_option_product(&response).await {
                error!("❌ Failed to save option to database: {}", e);
            }

            // 응답 생성
            let api_response = CreateOptionResponse {
                success: true,
                option_id: response.option_id.clone(),
                bitcoin_tx_id: response.bitcoin_anchor_txid.clone(),
                bitvmx_tx_id: None, // BitVMX 트랜잭션 ID는 별도로 추적 필요
                bitvmx_program_hash: response.bitvmx_program_hash,
                calculated_premium_btc: response.calculated_premium,
                max_units: response.max_units,
                expiry_timestamp: response.expiry_timestamp,
                verification_status: "SUCCESS".to_string(),
                message: format!("Option product {} created and anchored to Bitcoin", response.option_id),
            };

            Ok(reply::with_status(
                reply::json(&api_response),
                warp::http::StatusCode::CREATED,
            ))
        }
        Err(e) => {
            error!("❌ Failed to create option product: {}", e);
            Ok(reply::with_status(
                reply::json(&ErrorResponse {
                    success: false,
                    error: e,
                    error_code: "OPTION_CREATION_FAILED".to_string(),
                    details: None,
                }),
                warp::http::StatusCode::INTERNAL_SERVER_ERROR,
            ))
        }
    }
}

/// 옵션 구매 핸들러
pub async fn buy_option_handler(
    request: BuyOptionRequest,
    storage: StorageRef,
) -> Result<impl Reply, warp::Rejection> {
    info!("💰 Processing option purchase: {} units of {}", request.quantity, request.option_id);

    // 구매 서비스 초기화
    let mut buy_service = OptionBuyService::new(1000.0); // 1000 BTC 초기 풀

    // 내부 요청으로 변환
    let internal_request = InternalBuyRequest {
        option_id: request.option_id.clone(),
        quantity: request.quantity,
        max_premium_per_unit: request.max_premium_btc / request.quantity as f64,
        buyer_address: request.buyer_address.clone(),
    };

    let current_btc_price = 52000.0; // 실제로는 오라클에서

    match buy_service.buy_option(internal_request, current_btc_price).await {
        Ok(response) => {
            info!("✅ Option purchase successful: {}", response.purchase_id);

            // 구매 기록을 데이터베이스에 저장
            let purchase_record = PurchaseRecord {
                purchase_id: response.purchase_id.clone(),
                option_id: request.option_id,
                buyer_address: request.buyer_address,
                quantity: request.quantity,
                premium_btc_per_unit: response.total_premium_btc / request.quantity as f64,
                total_premium_btc: response.total_premium_btc,
                purchased_at: chrono::Utc::now().timestamp() as u64,
                expires_at: response.expires_at,
                btc_price_at_purchase: current_btc_price,
            };

            let mut storage_guard = storage.lock().await;
            if let Err(e) = storage_guard.save_purchase_record(&purchase_record).await {
                error!("❌ Failed to save purchase record: {}", e);
            }

            // API 응답 생성
            let api_response = BuyOptionResponse {
                success: true,
                purchase_id: response.purchase_id,
                option_id: response.option_id,
                quantity: response.quantity,
                total_premium_btc: response.total_premium_btc,
                average_price_btc: response.total_premium_btc / response.quantity as f64,
                buyer_address: response.buyer_address,
                expires_at: response.expires_at,
                current_btc_price,
                is_in_the_money: response.is_itm,
                estimated_payout: response.estimated_payout,
                message: "Option purchase completed successfully".to_string(),
            };

            Ok(reply::with_status(
                reply::json(&api_response),
                warp::http::StatusCode::OK,
            ))
        }
        Err(e) => {
            error!("❌ Option purchase failed: {}", e);
            Ok(reply::with_status(
                reply::json(&ErrorResponse {
                    success: false,
                    error: e,
                    error_code: "PURCHASE_FAILED".to_string(),
                    details: None,
                }),
                warp::http::StatusCode::BAD_REQUEST,
            ))
        }
    }
}

/// 활성 옵션 리스트 조회
pub async fn list_options_handler(
    storage: StorageRef,
) -> Result<impl Reply, warp::Rejection> {
    info!("📋 Fetching active option products");

    let storage_guard = storage.lock().await;
    
    match storage_guard.get_active_options().await {
        Ok(options) => {
            info!("✅ Retrieved {} active option products", options.len());
            Ok(reply::json(&options))
        }
        Err(e) => {
            error!("❌ Failed to retrieve options: {}", e);
            Ok(reply::with_status(
                reply::json(&ErrorResponse {
                    success: false,
                    error: e,
                    error_code: "DATABASE_ERROR".to_string(),
                    details: None,
                }),
                warp::http::StatusCode::INTERNAL_SERVER_ERROR,
            ))
        }
    }
}

/// 특정 옵션 상세 조회
pub async fn get_option_handler(
    option_id: String,
    storage: StorageRef,
) -> Result<impl Reply, warp::Rejection> {
    info!("🔍 Fetching option details: {}", option_id);

    let storage_guard = storage.lock().await;
    
    match storage_guard.get_option_details(&option_id).await {
        Ok(Some(details)) => {
            info!("✅ Retrieved option details: {}", option_id);
            Ok(reply::json(&details))
        }
        Ok(None) => {
            warn!("⚠️ Option not found: {}", option_id);
            Ok(reply::with_status(
                reply::json(&ErrorResponse {
                    success: false,
                    error: "Option not found".to_string(),
                    error_code: "OPTION_NOT_FOUND".to_string(),
                    details: None,
                }),
                warp::http::StatusCode::NOT_FOUND,
            ))
        }
        Err(e) => {
            error!("❌ Failed to retrieve option details: {}", e);
            Ok(reply::with_status(
                reply::json(&ErrorResponse {
                    success: false,
                    error: e,
                    error_code: "DATABASE_ERROR".to_string(),
                    details: None,
                }),
                warp::http::StatusCode::INTERNAL_SERVER_ERROR,
            ))
        }
    }
}

/// 헬스체크 핸들러
pub async fn health_handler(
    storage: StorageRef,
) -> Result<impl Reply, warp::Rejection> {
    let storage_guard = storage.lock().await;
    let stats = storage_guard.get_service_stats().await;

    let health = HealthResponse {
        status: "healthy".to_string(),
        timestamp: chrono::Utc::now().timestamp() as u64,
        version: "1.0.0".to_string(),
        bitcoin_node_connected: true, // TODO: 실제 연결 확인
        bitvmx_service_healthy: true, // TODO: 실제 상태 확인
        database_connected: true,
        active_options: stats.0,
        total_volume_btc: stats.1,
    };

    Ok(reply::json(&health))
}