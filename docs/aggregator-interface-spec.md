# 📋 Aggregator Interface 규격서

Oracle Node와 Aggregator 간의 통신 규격을 정의합니다.

## 1. 📡 통신 방식

### 기본 정보
- **프로토콜**: HTTP REST API
- **데이터 형식**: JSON
- **포트**: 8081 (기본값)
- **인증**: 없음 (PoC 단계)

## 2. 📤 Oracle Node → Aggregator

### 2.1 가격 데이터 전송

**엔드포인트**: `POST /submit-price`

**요청 헤더**:
```
Content-Type: application/json
```

**요청 본문**:
```json
{
  "price": 43521.50,
  "timestamp": 1704110460,
  "source": "binance",
  "node_id": "oracle-node-12345",
  "signature": "optional_crypto_signature"
}
```

**필드 설명**:
- `price` (number): BTC 가격 (USD)
- `timestamp` (number): Unix timestamp (초 단위)
- `source` (string): 데이터 소스 ("binance", "coinbase" 등)
- `node_id` (string): Oracle Node 고유 ID
- `signature` (string): 선택사항, 나중에 보안용

**성공 응답** (200 OK):
```json
{
  "status": "success",
  "message": "Price data received",
  "aggregated_price": 43520.75
}
```

**에러 응답** (400 Bad Request):
```json
{
  "status": "error",
  "message": "Invalid price data",
  "details": "Price must be positive"
}
```

### 2.2 헬스체크

**엔드포인트**: `GET /health`

**응답**:
```json
{
  "status": "healthy",
  "timestamp": 1704110460,
  "active_nodes": 3
}
```

## 3. 📥 Aggregator → Oracle Node

### 3.1 설정 업데이트 (선택사항)

**엔드포인트**: Oracle Node가 `GET /config` 제공

**응답**:
```json
{
  "fetch_interval": 60,
  "aggregator_url": "http://localhost:8081",
  "timeout": 10
}
```

## 4. 📊 Aggregator 내부 로직 (참고용)

### 4.1 가격 집계 알고리즘
```
1. 최근 5분 내 가격 데이터만 사용
2. 중앙값(median) 계산
3. 이상치 제거 (3-sigma rule)
4. 최소 2개 노드의 데이터 필요
```

### 4.2 데이터 저장
```
- 최근 1시간 데이터는 메모리에 보관
- 그 이전 데이터는 DB 저장 (선택사항)
```

## 5. 🛠️ 구현 가이드

### 5.1 Aggregator 개발자가 구현해야 할 것

#### 필수 기능:
1. **가격 수집**: Oracle Node들로부터 가격 데이터 받기
2. **가격 집계**: 중앙값 계산
3. **API 제공**: 집계된 가격을 외부에 제공

#### 선택 기능:
1. **웹 대시보드**: 실시간 가격 모니터링
2. **알림**: 이상 상황 감지 시 알림
3. **데이터 저장**: 히스토리 데이터 저장

### 5.2 추천 기술 스택

**백엔드**:
- **Node.js**: Express.js
- **Python**: FastAPI
- **Go**: Gin
- **Rust**: Axum (우리와 같은 언어)

**데이터베이스** (선택):
- Redis (캐시용)
- InfluxDB (시계열 데이터)
- PostgreSQL (관계형 데이터)

## 6. 📋 테스트 시나리오

### 6.1 정상 케이스
```bash
# 1. Aggregator 실행
curl -X GET http://localhost:8081/health

# 2. Oracle Node에서 가격 전송
curl -X POST http://localhost:8081/submit-price \
  -H "Content-Type: application/json" \
  -d '{
    "price": 43521.50,
    "timestamp": 1704110460,
    "source": "binance", 
    "node_id": "test-node"
  }'

# 3. 집계된 가격 조회
curl -X GET http://localhost:8081/aggregated-price
```

### 6.2 에러 케이스
```bash
# 잘못된 가격 데이터
curl -X POST http://localhost:8081/submit-price \
  -H "Content-Type: application/json" \
  -d '{
    "price": -100,
    "timestamp": 1704110460,
    "source": "binance",
    "node_id": "test-node"
  }'
# 응답: 400 Bad Request
```

## 7. 🔗 Oracle Node 연동 방법

Oracle Node에서 Aggregator 클라이언트 추가:

```rust
// aggregator_client.rs 파일 생성 필요
pub struct AggregatorClient {
    client: Client,
    aggregator_url: String,
    node_id: String,
}

impl AggregatorClient {
    pub async fn submit_price(&self, price_data: &PriceData) -> Result<()> {
        // POST /submit-price 호출
    }
}
```

## 8. 📈 확장 계획

### Phase 1 (현재)
- 기본 가격 수집 및 집계
- HTTP REST API

### Phase 2 (나중에)
- WebSocket 실시간 통신
- 암호화 서명 검증
- 다중 거래소 지원

### Phase 3 (미래)
- gRPC 지원
- 분산 Aggregator
- 고가용성 구성

## 9. 🤝 협업 방법

1. **이 규격서 공유** → Aggregator 개발자가 읽고 이해
2. **Mock Aggregator 구현** → 테스트용 간단한 서버
3. **통합 테스트** → Oracle Node + Aggregator 함께 테스트
4. **피드백 및 수정** → 필요시 규격 업데이트

## 10. 📞 연락처

- **Oracle Node 개발자**: [연락처]
- **프로젝트 저장소**: https://github.com/97woo/OracleVM
- **문의사항**: GitHub Issues 활용

---

**이 규격서를 Aggregator 개발자에게 전달하면, 우리 Oracle Node와 완벽하게 연동되는 Aggregator를 만들 수 있습니다!** 🚀