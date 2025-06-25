use anyhow::Result;
use std::collections::HashMap;
use std::sync::{Arc, Mutex};
use tonic::{transport::Server, Request, Response, Status};
use tracing::{info, warn};
use chrono::Utc;

// gRPC 서비스 정의 (tonic-build로 자동 생성됨)
pub mod oracle {
    tonic::include_proto!("oracle");
}

use oracle::{
    oracle_service_server::{OracleService, OracleServiceServer},
    PriceRequest, PriceResponse, HealthRequest, HealthResponse,
    ConfigRequest, ConfigResponse, GetPriceRequest, GetPriceResponse,
    AggregatedPriceUpdate, PriceDataPoint,
};

use futures::Stream;
use std::pin::Pin;

/// 가격 데이터 저장 구조체
#[derive(Clone, Debug)]
struct StoredPriceData {
    price: f64,
    timestamp: u64,
    source: String,
    node_id: String,
    received_at: u64,
}

/// Aggregator 서비스 구현
#[derive(Default)]
pub struct AggregatorService {
    // 메모리에 가격 데이터 저장 (실제로는 DB 사용)
    price_data: Arc<Mutex<Vec<StoredPriceData>>>,
    // 활성 노드 추적
    active_nodes: Arc<Mutex<HashMap<String, u64>>>,
}

impl AggregatorService {
    pub fn new() -> Self {
        Self {
            price_data: Arc::new(Mutex::new(Vec::new())),
            active_nodes: Arc::new(Mutex::new(HashMap::new())),
        }
    }
    
    /// 집계된 가격 계산 (최근 5분 내 데이터 중앙값)
    fn calculate_aggregated_price(&self) -> Option<f64> {
        let price_data = self.price_data.lock().unwrap();
        let now = Utc::now().timestamp() as u64;
        
        // 최근 5분 내 데이터만 사용
        let recent_prices: Vec<f64> = price_data
            .iter()
            .filter(|data| now - data.received_at <= 300) // 5분 = 300초
            .map(|data| data.price)
            .collect();
        
        if recent_prices.is_empty() {
            return None;
        }
        
        // 중앙값 계산
        let mut sorted_prices = recent_prices;
        sorted_prices.sort_by(|a, b| a.partial_cmp(b).unwrap());
        
        let len = sorted_prices.len();
        if len % 2 == 0 {
            Some((sorted_prices[len / 2 - 1] + sorted_prices[len / 2]) / 2.0)
        } else {
            Some(sorted_prices[len / 2])
        }
    }
    
    /// 활성 노드 업데이트
    fn update_active_node(&self, node_id: &str) {
        let mut active_nodes = self.active_nodes.lock().unwrap();
        let now = Utc::now().timestamp() as u64;
        active_nodes.insert(node_id.to_string(), now);
        
        // 5분 이상 비활성 노드 제거
        active_nodes.retain(|_, &mut last_seen| now - last_seen <= 300);
    }
}

#[tonic::async_trait]
impl OracleService for AggregatorService {
    /// 스트림 타입 정의
    type StreamPricesStream = Pin<Box<dyn Stream<Item = Result<AggregatedPriceUpdate, Status>> + Send>>;
    /// 가격 데이터 제출 처리
    async fn submit_price(
        &self,
        request: Request<PriceRequest>,
    ) -> Result<Response<PriceResponse>, Status> {
        let price_request = request.into_inner();
        
        info!("📨 Received price: ${:.2} from {} (node: {})", 
              price_request.price, 
              price_request.source, 
              price_request.node_id);
        
        // 가격 검증
        if price_request.price <= 0.0 {
            warn!("❌ Invalid price: {}", price_request.price);
            return Ok(Response::new(PriceResponse {
                success: false,
                message: "Price must be positive".to_string(),
                aggregated_price: None,
                timestamp: Utc::now().timestamp() as u64,
            }));
        }
        
        // 데이터 저장
        let stored_data = StoredPriceData {
            price: price_request.price,
            timestamp: price_request.timestamp,
            source: price_request.source,
            node_id: price_request.node_id.clone(),
            received_at: Utc::now().timestamp() as u64,
        };
        
        {
            let mut price_data = self.price_data.lock().unwrap();
            price_data.push(stored_data);
            
            // 최근 100개만 보관 (메모리 절약)
            if price_data.len() > 100 {
                price_data.remove(0);
            }
        }
        
        // 활성 노드 업데이트
        self.update_active_node(&price_request.node_id);
        
        // 집계 가격 계산
        let aggregated_price = self.calculate_aggregated_price();
        
        if let Some(agg_price) = aggregated_price {
            info!("📊 Aggregated price: ${:.2}", agg_price);
        }
        
        Ok(Response::new(PriceResponse {
            success: true,
            message: "Price data received".to_string(),
            aggregated_price,
            timestamp: Utc::now().timestamp() as u64,
        }))
    }
    
    /// 헬스체크 처리
    async fn health_check(
        &self,
        request: Request<HealthRequest>,
    ) -> Result<Response<HealthResponse>, Status> {
        let health_request = request.into_inner();
        
        // 활성 노드 업데이트
        self.update_active_node(&health_request.node_id);
        
        let active_nodes = self.active_nodes.lock().unwrap();
        let active_count = active_nodes.len() as u32;
        
        info!("💚 Health check from {} (active nodes: {})", 
              health_request.node_id, active_count);
        
        Ok(Response::new(HealthResponse {
            healthy: true,
            timestamp: Utc::now().timestamp() as u64,
            active_nodes: active_count,
            version: "1.0.0".to_string(),
        }))
    }
    
    /// 집계 가격 조회
    async fn get_aggregated_price(
        &self,
        _request: Request<GetPriceRequest>,
    ) -> Result<Response<GetPriceResponse>, Status> {
        let aggregated_price = self.calculate_aggregated_price();
        
        match aggregated_price {
            Some(price) => {
                let price_data = self.price_data.lock().unwrap();
                let data_points = price_data.len() as u32;
                let last_update = price_data
                    .last()
                    .map(|data| data.received_at)
                    .unwrap_or(0);
                
                // 최근 5개 데이터 포함
                let recent_prices: Vec<PriceDataPoint> = price_data
                    .iter()
                    .rev()
                    .take(5)
                    .map(|data| PriceDataPoint {
                        price: data.price,
                        timestamp: data.timestamp,
                        source: data.source.clone(),
                        node_id: data.node_id.clone(),
                    })
                    .collect();
                
                Ok(Response::new(GetPriceResponse {
                    success: true,
                    aggregated_price: price,
                    data_points,
                    last_update,
                    recent_prices,
                }))
            }
            None => {
                Ok(Response::new(GetPriceResponse {
                    success: false,
                    aggregated_price: 0.0,
                    data_points: 0,
                    last_update: 0,
                    recent_prices: vec![],
                }))
            }
        }
    }
    
    /// 설정 업데이트 (미구현)
    async fn update_config(
        &self,
        _request: Request<ConfigRequest>,
    ) -> Result<Response<ConfigResponse>, Status> {
        // TODO: 설정 업데이트 로직 구현
        Ok(Response::new(ConfigResponse {
            success: false,
            message: "Not implemented yet".to_string(),
        }))
    }
    
    /// 스트림 처리 (미구현)
    async fn stream_prices(
        &self,
        _request: Request<tonic::Streaming<PriceRequest>>,
    ) -> Result<Response<Self::StreamPricesStream>, Status> {
        Err(Status::unimplemented("Stream prices not implemented yet"))
    }
}

#[tokio::main]
async fn main() -> Result<()> {
    // 로깅 초기화
    tracing_subscriber::fmt::init();
    
    info!("🚀 Starting gRPC Aggregator on port 50051...");
    
    let addr = "0.0.0.0:50051".parse().unwrap();
    let aggregator_service = AggregatorService::new();
    
    info!("🔗 gRPC Aggregator listening on {}", addr);
    info!("📋 Available gRPC methods:");
    info!("   - SubmitPrice: 가격 데이터 제출");
    info!("   - HealthCheck: 헬스체크");
    info!("   - GetAggregatedPrice: 집계 가격 조회");
    
    Server::builder()
        .add_service(OracleServiceServer::new(aggregator_service))
        .serve(addr)
        .await?;
    
    Ok(())
}