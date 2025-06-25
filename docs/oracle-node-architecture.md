# Oracle Node 아키텍처 설계

## 1. 개요

Oracle Node는 외부 거래소로부터 BTC 가격 데이터를 수집하고, 이를 검증하여 Aggregator에 전달하는 분산 노드입니다.

## 2. 핵심 컴포넌트

### 2.1 Price Fetcher Module
```
┌─────────────────────────────────────────┐
│           Price Fetcher                 │
├─────────────────────────────────────────┤
│ - Exchange Adapters                     │
│   ├── Binance WebSocket/REST          │
│   ├── Bithumb REST API                │
│   └── Coinbase WebSocket              │
│ - Rate Limiter                         │
│ - Retry Logic                          │
│ - Data Validation                      │
└─────────────────────────────────────────┘
```

**책임:**
- 각 거래소별 API 어댑터 관리
- 실시간 가격 스트리밍 (WebSocket)
- 폴백을 위한 REST API 지원
- API Rate Limit 관리
- 네트워크 오류 시 재시도 로직

### 2.2 Data Storage Module
```
┌─────────────────────────────────────────┐
│          Data Storage                   │
├─────────────────────────────────────────┤
│ - In-Memory Cache (Redis)              │
│ - Time-Series DB (InfluxDB)           │
│ - Price History Buffer                 │
│ - Snapshot Manager                     │
└─────────────────────────────────────────┘
```

**책임:**
- 최근 가격 데이터 캐싱
- 히스토리컬 데이터 저장
- 빠른 조회를 위한 인메모리 버퍼
- 주기적 스냅샷 생성

### 2.3 Validation Module
```
┌─────────────────────────────────────────┐
│          Validation Engine              │
├─────────────────────────────────────────┤
│ - Price Sanity Check                   │
│ - Timestamp Verification               │
│ - Source Reliability Score             │
│ - Anomaly Detection                    │
└─────────────────────────────────────────┘
```

**책임:**
- 가격 데이터 유효성 검증
- 타임스탬프 검증 (stale data 방지)
- 소스 신뢰도 평가
- 이상치 탐지 (급격한 가격 변동)

### 2.4 Communication Module
```
┌─────────────────────────────────────────┐
│       Communication Layer               │
├─────────────────────────────────────────┤
│ - gRPC Server                          │
│ - P2P Network (libp2p)                │
│ - Aggregator Client                    │
│ - Heartbeat Manager                    │
└─────────────────────────────────────────┘
```

**책임:**
- Aggregator와의 안전한 통신
- 다른 Oracle Node와의 P2P 통신
- 주기적 헬스체크 및 하트비트
- 암호화된 데이터 전송

### 2.5 Security Module
```
┌─────────────────────────────────────────┐
│          Security Layer                 │
├─────────────────────────────────────────┤
│ - Ed25519 Key Management               │
│ - Message Signing                      │
│ - TLS/mTLS Support                     │
│ - API Key Rotation                     │
└─────────────────────────────────────────┘
```

**책임:**
- 노드 신원 관리 (Ed25519 키페어)
- 모든 가격 데이터 서명
- 안전한 통신 채널 확립
- API 키 안전한 저장 및 로테이션

## 3. 데이터 흐름

```
Exchange APIs → Price Fetcher → Validation → Storage → Communication → Aggregator
      ↓              ↓             ↓           ↓            ↓
   WebSocket     Rate Limit    Sanity     Redis/DB    gRPC/P2P
   REST API      Retry Logic   Check      Buffer      Signed Msg
```

## 4. 주요 데이터 구조

### 4.1 Price Data
```rust
struct PriceData {
    source: Exchange,
    symbol: String,           // "BTC/USD"
    price: u64,              // in satoshis or cents
    volume: u64,             // 24h volume
    timestamp: u64,          // Unix timestamp
    bid: u64,               // Best bid
    ask: u64,               // Best ask
    signature: Signature,    // Ed25519 signature
}
```

### 4.2 Oracle Node State
```rust
struct OracleNodeState {
    node_id: PublicKey,
    status: NodeStatus,
    last_heartbeat: u64,
    reputation_score: u32,
    total_submissions: u64,
    successful_submissions: u64,
}
```

## 5. 고가용성 설계

### 5.1 Failover Strategy
- Primary/Secondary 거래소 설정
- WebSocket 연결 실패 시 REST API 폴백
- 다중 거래소 동시 모니터링

### 5.2 Data Redundancy
- 최소 3개 이상의 가격 소스 유지
- 로컬 캐시 + 영구 저장소 이중화
- 주기적 백업 및 복구 메커니즘

### 5.3 Monitoring & Alerting
- Prometheus 메트릭 수집
- Grafana 대시보드
- 이상 상황 자동 알림

## 6. 성능 요구사항

- **지연시간:** < 100ms (거래소 → Oracle Node)
- **처리량:** 1000+ price updates/sec
- **가용성:** 99.9% uptime
- **메모리:** < 1GB RAM
- **저장소:** 100GB (1년 히스토리)

## 7. 보안 고려사항

### 7.1 네트워크 보안
- 모든 외부 통신 TLS 암호화
- IP 화이트리스트
- DDoS 방어 메커니즘

### 7.2 데이터 무결성
- 모든 가격 데이터 암호학적 서명
- Merkle Tree 기반 데이터 검증
- 체인 형태의 가격 히스토리

### 7.3 접근 제어
- Role-based Access Control
- API 키 관리 및 로테이션
- 감사 로그 (Audit Trail)

## 8. 확장성 설계

### 8.1 수평 확장
- 거래소별 독립적 워커 프로세스
- 로드 밸런싱 지원
- 동적 노드 추가/제거

### 8.2 모듈화
- 플러그인 방식의 거래소 어댑터
- 독립적인 마이크로서비스 구조
- 언어 중립적 gRPC 인터페이스

## 9. 에러 처리 전략

### 9.1 거래소 연결 실패
- Exponential Backoff 재시도
- Circuit Breaker 패턴
- 대체 거래소 자동 전환

### 9.2 데이터 이상치
- 3-sigma rule 적용
- 이전 가격 대비 임계값 체크
- 수동 개입 알림

### 9.3 네트워크 파티션
- 로컬 버퍼링
- 재연결 시 자동 동기화
- Conflict Resolution 로직

## 10. 배포 아키텍처

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│  Oracle Node 1  │     │  Oracle Node 2  │     │  Oracle Node 3  │
│   (Primary)     │     │   (Secondary)   │     │   (Tertiary)   │
├─────────────────┤     ├─────────────────┤     ├─────────────────┤
│ - Binance       │     │ - Coinbase      │     │ - Bithumb       │
│ - Backup: CB    │     │ - Backup: Bin   │     │ - Backup: Bin   │
└────────┬────────┘     └────────┬────────┘     └────────┬────────┘
         │                       │                        │
         └───────────────────────┴────────────────────────┘
                                 │
                          ┌──────┴──────┐
                          │  Aggregator │
                          └─────────────┘
```

---

*이 설계는 고가용성, 보안성, 확장성을 고려한 분산 Oracle Node 시스템을 목표로 합니다.*