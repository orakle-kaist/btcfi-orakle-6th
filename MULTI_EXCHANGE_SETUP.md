# BTCFi Oracle - 다중 거래소 시스템 가이드

## 📋 개요

BTCFi Oracle 시스템이 이제 3개의 거래소에서 동시에 BTC 가격을 수집할 수 있습니다:

- **Binance**: K-line API (1분 캔들스틱)
- **Coinbase**: K-line API (1분 캔들스틱)  
- **Kraken**: OHLC API (1분 캔들스틱)

모든 거래소는 1분마다 동시에 동기화된 시점(XX:00초)에서 가격을 수집합니다.

## 🚀 사용 방법

### 1. Aggregator 실행

```bash
cargo run -p aggregator
```

### 2. 개별 Oracle Node 실행

```bash
# Node 1: Binance
cargo run -p oracle-node -- --exchange binance --node-id oracle-node-1

# Node 2: Coinbase  
cargo run -p oracle-node -- --exchange coinbase --node-id oracle-node-2

# Node 3: Kraken
cargo run -p oracle-node -- --exchange kraken --node-id oracle-node-3
```

### 3. 자동 다중 노드 실행

```bash
# 모든 노드를 백그라운드에서 실행
./scripts/run_multi_nodes.sh

# 모든 노드 중지
./scripts/stop_nodes.sh
```

### 4. 개별 거래소 테스트

```bash
# 대화형 테스트
./scripts/test_exchanges.sh
```

## 📊 모니터링

### 실시간 로그 확인

```bash
# 각 노드별 로그
tail -f logs/node1_binance.log
tail -f logs/node2_coinbase.log  
tail -f logs/node3_kraken.log
```

### Aggregator 상태 확인

```bash
# Python gRPC 클라이언트로 테스트
python3 scripts/test_aggregator.py
```

## 🔧 설정 옵션

```bash
oracle-node [OPTIONS]

옵션:
  --exchange <EXCHANGE>          # binance, coinbase, kraken
  --node-id <NODE_ID>           # 노드 고유 ID
  --aggregator-url <URL>        # Aggregator gRPC 주소
  --interval <SECONDS>          # 수집 간격 (기본: 60초)
```

## 📈 동작 방식

1. **동기화된 수집**: 모든 노드가 매분 00초에 동시 수집
2. **평균 집계**: Aggregator가 3개 거래소 가격의 평균값 계산
3. **실시간 업데이트**: 1분마다 집계된 가격 업데이트
4. **자동 재시도**: 네트워크 오류 시 지수적 백오프로 재시도

## 🌐 API 엔드포인트

### Binance
- **URL**: `https://api.binance.com/api/v3/klines`
- **파라미터**: `?symbol=BTCUSDT&interval=1m&limit=1`
- **데이터**: 1분 K-line 캔들스틱 배열

### Coinbase
- **URL**: `https://api.exchange.coinbase.com/products/BTC-USD/candles`
- **파라미터**: `?start=<timestamp>&end=<timestamp>&granularity=60`
- **데이터**: [timestamp, low, high, open, close, volume] 배열

### Kraken
- **URL**: `https://api.kraken.com/0/public/OHLC`
- **파라미터**: `?pair=XBTUSD&interval=1`
- **데이터**: OHLC (Open, High, Low, Close) 배열

## ⚡ 성능 특징

- **지연시간**: 각 거래소별 평균 응답시간 < 1초
- **동기화**: 모든 노드가 정확히 매분 00초에 수집
- **내결함성**: 개별 거래소 장애 시에도 다른 거래소로 계속 서비스
- **집계 방식**: 평균값 (Mean) 계산으로 이상치 완화

## 🔍 디버깅

### 일반적인 문제

1. **Aggregator 연결 실패**
   ```
   ❌ Cannot connect to gRPC Aggregator
   💡 Make sure to run: cargo run -p aggregator
   ```

2. **거래소 API 오류**
   ```
   ❌ Rate limit exceeded - Too many requests
   💡 잠시 후 자동으로 재시도됩니다
   ```

3. **가격 검증 실패**
   ```
   ⚠️ Unusually low/high BTC price: $X
   💡 정상적인 경고입니다, 계속 진행됩니다
   ```

## 📚 코드 구조

```
crates/oracle-node/src/
├── main.rs           # 메인 진입점, ExchangeClient enum
├── binance.rs        # Binance K-line API 클라이언트  
├── coinbase.rs       # Coinbase candles API 클라이언트
└── kraken.rs         # Kraken OHLC API 클라이언트
```

이제 3개의 거래소에서 동시에 가격을 수집하여 더욱 신뢰성 높은 BTC 가격 오라클을 운영할 수 있습니다! 🎯