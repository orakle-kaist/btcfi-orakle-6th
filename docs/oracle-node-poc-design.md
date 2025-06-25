# Oracle Node PoC 설계 (단일 거래소)

## 1. 목표
Binance에서 BTC/USDT 가격을 가져와서 Aggregator에 전달하는 최소 기능 구현

## 2. 심플한 구조

```
┌─────────────────────────────┐
│      Oracle Node (PoC)      │
├─────────────────────────────┤
│  1. Price Fetcher           │
│     └─ Binance REST API     │
│                             │
│  2. Data Store              │
│     └─ In-memory (Vec)      │
│                             │
│  3. HTTP Server             │
│     └─ Simple REST endpoint │
└─────────────────────────────┘
```

## 3. 핵심 컴포넌트만

### 3.1 Price Fetcher (최소 기능)
- Binance REST API 호출 (1분마다)
- BTC/USDT 현재가만 가져오기
- 간단한 재시도 로직 (3회)

### 3.2 Data Store (메모리)
- 최근 100개 가격만 메모리에 보관
- 오래된 데이터는 자동 삭제
- DB 없이 Vec<PriceData>로 관리

### 3.3 API Server
- GET /price - 현재 가격
- GET /prices - 최근 100개 가격
- 인증 없이 로컬에서만 접근

## 4. 간단한 데이터 구조

```rust
struct PriceData {
    price: f64,        // BTC 가격 (USD)
    timestamp: u64,    // Unix timestamp
    source: String,    // "binance"
}

struct OracleNode {
    prices: Vec<PriceData>,  // 최근 가격들
    config: Config,
}

struct Config {
    binance_api_url: String,
    fetch_interval: u64,  // 초 단위
}
```

## 5. 동작 흐름

```
1. 1분마다 Binance API 호출
   GET https://api.binance.com/api/v3/ticker/price?symbol=BTCUSDT

2. 응답 파싱
   {
     "symbol": "BTCUSDT",
     "price": "43521.50"
   }

3. 메모리에 저장
   prices.push(PriceData { ... })

4. Aggregator가 요청하면 전달
   GET http://localhost:8080/price
```

## 6. 구현 우선순위

1. **Phase 1 (1일)**
   - Binance API 클라이언트
   - 가격 가져오기 함수
   - 메모리 저장

2. **Phase 2 (1일)**
   - HTTP 서버
   - API 엔드포인트
   - 주기적 실행 (tokio 타이머)

3. **Phase 3 (나중에)**
   - 에러 처리 개선
   - 로깅 추가
   - 설정 파일

## 7. 필요한 크레이트

```toml
[dependencies]
tokio = { version = "1", features = ["full"] }
reqwest = { version = "0.11", features = ["json"] }
serde = { version = "1.0", features = ["derive"] }
serde_json = "1.0"
axum = "0.7"  # 간단한 웹 서버
```

## 8. 파일 구조 (심플)

```
crates/oracle-node/
├── src/
│   ├── main.rs         # 진입점
│   ├── binance.rs      # Binance API 클라이언트
│   └── server.rs       # HTTP 서버
└── Cargo.toml
```

## 9. 예상 코드 라인
- 전체: ~200줄
- main.rs: 50줄
- binance.rs: 80줄  
- server.rs: 70줄

## 10. 테스트 방법

1. Oracle Node 실행
   ```bash
   cargo run --bin oracle-node
   ```

2. 가격 확인
   ```bash
   curl http://localhost:8080/price
   ```

3. 로그 확인
   ```
   [2024-01-01 12:00:00] Fetched BTC price: $43,521.50
   [2024-01-01 12:01:00] Fetched BTC price: $43,525.30
   ```

---

이 PoC 버전은 복잡한 기능 없이 핵심만 구현합니다. 나중에 필요하면 기능을 추가할 수 있습니다.