use anyhow::Result;
use chrono::Utc;
use std::collections::HashMap;
use std::sync::{Arc, Mutex};
use tonic::{transport::Server, Request, Response, Status};
use tracing::{info, warn};

// gRPC 서비스 정의 (tonic-build로 자동 생성됨)
pub mod oracle {
    tonic::include_proto!("oracle");
}

use oracle::{
    oracle_service_server::{OracleService, OracleServiceServer},
    AggregatedPriceUpdate, ConfigRequest, ConfigResponse, GetPriceRequest, GetPriceResponse,
    HealthRequest, HealthResponse, PriceDataPoint, PriceRequest, PriceResponse,
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

    /// 안전한 집계 가격 계산 (엄격한 조건 검증)
    fn calculate_aggregated_price(&self) -> Option<f64> {
        let price_data = self.price_data.lock().unwrap();
        let now = Utc::now().timestamp() as u64;

        // Step 1: 각 거래소별 최신 데이터 수집 (거래소 이름으로 그룹핑)
        let mut latest_per_exchange: std::collections::HashMap<String, (f64, u64)> =
            std::collections::HashMap::new();

        for data in price_data.iter() {
            // 최근 120초 내 데이터만 사용 (1분 주기에 맞춘 윈도우)
            if now - data.received_at <= 120 {
                // 120초
                latest_per_exchange
                    .entry(data.source.clone()) // source = exchange name
                    .and_modify(|(existing_price, existing_time)| {
                        // 더 최신 데이터라면 업데이트
                        if data.timestamp > *existing_time {
                            *existing_price = data.price;
                            *existing_time = data.timestamp;
                        }
                    })
                    .or_insert((data.price, data.timestamp));
            }
        }

        // Step 2: 2/3 이상 합의 조건 검증
        let required_exchanges = vec!["binance", "coinbase", "kraken"];
        let total_exchanges = required_exchanges.len();
        let min_required = (total_exchanges * 2 + 2) / 3; // ceil(2/3) = 2개 이상

        // 2.1 최소 필요 거래소 수 확인 (3개 중 2개 이상)
        if latest_per_exchange.len() < min_required {
            let missing: Vec<&str> = required_exchanges
                .iter()
                .filter(|&exchange| !latest_per_exchange.contains_key(*exchange))
                .cloned()
                .collect();
            warn!(
                "⚠️ Insufficient consensus: {} of {} exchanges (need at least {}). Missing: {:?}",
                latest_per_exchange.len(),
                total_exchanges,
                min_required,
                missing
            );
            return None;
        }

        info!(
            "✅ Consensus achieved: {} of {} exchanges participating",
            latest_per_exchange.len(),
            total_exchanges
        );

        // 2.2 timestamp 동일성 검증 (1분 이내 차이만 허용)
        let timestamps: Vec<u64> = latest_per_exchange
            .values()
            .map(|(_, timestamp)| *timestamp)
            .collect();
        let min_timestamp = *timestamps.iter().min().unwrap();
        let max_timestamp = *timestamps.iter().max().unwrap();

        if max_timestamp - min_timestamp > 60 {
            // 60초 초과 차이 (1분 수집 주기 고려)
            warn!(
                "⚠️ Timestamp mismatch: {} second difference. Min: {}, Max: {}",
                max_timestamp - min_timestamp,
                min_timestamp,
                max_timestamp
            );
            return None;
        }

        // Step 3: 가격 이상치 검증
        let prices: Vec<f64> = latest_per_exchange
            .values()
            .map(|(price, _)| *price)
            .collect();
        let avg_price = prices.iter().sum::<f64>() / prices.len() as f64;

        // 3.1 개별 가격이 평균에서 5% 이상 벗어나는지 확인
        for (exchange, (price, _)) in &latest_per_exchange {
            let deviation = ((price - avg_price) / avg_price * 100.0).abs();
            if deviation > 5.0 {
                // 5% 초과 편차
                warn!(
                    "⚠️ Price anomaly detected: {} = ${:.2} ({}% deviation from average ${:.2})",
                    exchange, price, deviation, avg_price
                );
                return None;
            }
        }

        // 3.2 가격 범위 상식선 검증
        if avg_price < 10000.0 || avg_price > 500000.0 {
            warn!("⚠️ Unrealistic average price: ${:.2}", avg_price);
            return None;
        }

        // Step 4: 모든 검증 통과 시 집계 수행
        let participating_exchanges: Vec<&String> = latest_per_exchange.keys().collect();
        info!(
            "✅ All validations passed. Participating exchanges: {:?}",
            participating_exchanges
        );
        info!(
            "📊 Consensus aggregated price: ${:.2} from {}/{} exchanges",
            avg_price,
            prices.len(),
            total_exchanges
        );

        // 개별 가격 로깅
        for (exchange, (price, timestamp)) in &latest_per_exchange {
            info!("   {}: ${:.2} (timestamp: {})", exchange, price, timestamp);
        }

        Some(avg_price)
    }

    /// 활성 노드 업데이트
    fn update_active_node(&self, node_id: &str) {
        let mut active_nodes = self.active_nodes.lock().unwrap();
        let now = Utc::now().timestamp() as u64;
        active_nodes.insert(node_id.to_string(), now);

        // 2분 이상 비활성 노드 제거 (1분 수집 + 1분 여유)
        active_nodes.retain(|_, &mut last_seen| now - last_seen <= 120);
    }
}

#[tonic::async_trait]
impl OracleService for AggregatorService {
    /// 스트림 타입 정의
    type StreamPricesStream =
        Pin<Box<dyn Stream<Item = Result<AggregatedPriceUpdate, Status>> + Send>>;
    /// 가격 데이터 제출 처리
    async fn submit_price(
        &self,
        request: Request<PriceRequest>,
    ) -> Result<Response<PriceResponse>, Status> {
        let price_request = request.into_inner();

        info!(
            "📨 Received price: ${:.2} from {} (node: {})",
            price_request.price, price_request.source, price_request.node_id
        );

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

        info!(
            "💚 Health check from {} (active nodes: {})",
            health_request.node_id, active_count
        );

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
                let last_update = price_data.last().map(|data| data.received_at).unwrap_or(0);

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
            None => Ok(Response::new(GetPriceResponse {
                success: false,
                aggregated_price: 0.0,
                data_points: 0,
                last_update: 0,
                recent_prices: vec![],
            })),
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
    info!("   - HealthCheck: 상태체크");
    info!("   - GetAggregatedPrice: 집계 가격 조회");

    Server::builder()
        .add_service(OracleServiceServer::new(aggregator_service))
        .serve(addr)
        .await?;

    Ok(())
}
