# BTCFi Options System - Production Architecture

## 시스템 개요

BTCFi 단방향 옵션 시스템은 BitVMX 프로토콜 위에서 완전 자동화된 옵션 거래를 구현합니다.

## 핵심 구성요소

### 1. 옵션 등록 (Registration)
- **프로그램**: `btcfi_option_registration.c`
- **목적**: 유동성 풀에서 새로운 옵션 상품 생성
- **검증 항목**:
  - 행사가격 범위: $1,000 - $10,000,000
  - 수량 범위: 0.001 - 10 BTC
  - 만기: 최대 1년
  - 오라클: 최소 3개, 최대 5개

### 2. 옵션 구매 (Purchase)
- **프로그램**: `btcfi_option_purchase.c`
- **목적**: 구매자가 옵션을 매수
- **핵심 기능**:
  - BitVMX pre-sign 생성
  - 에스크로 주소 생성
  - 리스크 점수 계산
  - 프리미엄 검증

### 3. 옵션 정산 (Settlement)
- **프로그램**: `btcfi_option_settlement.c`
- **목적**: 만기 시 자동 정산
- **정산 방식**:
  - ITM: 내재가치만큼 지급
  - OTM: 무가치 만기
  - ATM: 0.1% 임계값 적용

## 데이터 구조

### Registration Input (144 bytes)
```c
struct BTCFiOptionInput {
    uint32_t option_type;        // 4 bytes
    uint64_t strike_price;       // 8 bytes
    uint64_t quantity;           // 8 bytes
    uint64_t premium;            // 8 bytes
    uint64_t expiry_timestamp;   // 8 bytes
    uint8_t issuer_hash[32];     // 32 bytes
    uint32_t oracle_count;       // 4 bytes
    uint8_t oracle_hashes[5][8]; // 40 bytes
}; // Total: 112 bytes
```

### Purchase Input (254 bytes)
```c
struct BTCFiPurchaseInput {
    uint8_t option_id[6];         // 6 bytes
    uint8_t buyer_hash[32];       // 32 bytes
    uint64_t purchase_quantity;   // 8 bytes
    uint64_t premium_paid;        // 8 bytes
    uint64_t purchase_timestamp;  // 8 bytes
    uint8_t payment_proof[32];    // 32 bytes
    uint8_t bitvm_presign[64];    // 64 bytes
    // Option details for validation
    uint32_t option_type;         // 4 bytes
    uint64_t strike_price;        // 8 bytes
    uint64_t total_quantity;      // 8 bytes
    uint64_t expiry_timestamp;    // 8 bytes
    uint64_t minimum_premium;     // 8 bytes
}; // Total: 226 bytes
```

### Settlement Input (226 bytes)
```c
struct BTCFiSettlementInput {
    uint8_t purchase_id[8];            // 8 bytes
    uint8_t option_id[6];              // 6 bytes
    uint32_t settlement_type;          // 4 bytes
    uint64_t aggregated_price;         // 8 bytes (from Aggregator)
    uint8_t aggregator_signature[64];  // 64 bytes
    uint64_t settlement_timestamp;     // 8 bytes
    uint8_t buyer_claim[32];           // 32 bytes
    // Option details
    uint32_t option_type;              // 4 bytes
    uint64_t strike_price;             // 8 bytes
    uint64_t purchase_quantity;        // 8 bytes
    uint64_t expiry_timestamp;         // 8 bytes
    uint8_t buyer_hash[32];            // 32 bytes
    uint64_t premium_paid;             // 8 bytes
    // Aggregator metadata
    uint32_t oracle_count;             // 4 bytes (always 3)
    uint8_t aggregator_hash[32];       // 32 bytes
}; // Total: 226 bytes
```

## 프로토콜 상수

```c
// Registration
#define BTCFI_MAGIC 0x42544346         // "BTCF"
#define MIN_STRIKE_PRICE 100000         // $1,000
#define MAX_STRIKE_PRICE 1000000000     // $10M
#define MIN_QUANTITY 100000             // 0.001 BTC
#define MAX_QUANTITY 1000000000         // 10 BTC
#define SETTLEMENT_BLOCKS 144           // ~24 hours
#define COLLATERAL_RATIO 110            // 110%

// Purchase
#define BTCFI_PURCHASE_MAGIC 0x42544350 // "BTCP"
#define MIN_PURCHASE_QUANTITY 10000     // 0.0001 BTC
#define PREMIUM_TOLERANCE 105            // 105%
#define MIN_TIME_TO_EXPIRY 3600         // 1 hour

// Settlement
#define BTCFI_SETTLEMENT_MAGIC 0x42544353 // "BTCS"
#define MIN_ORACLE_CONSENSUS 3          // 3/5 oracles
#define PRICE_TOLERANCE_BPS 50          // 0.5%
#define ATM_THRESHOLD_BPS 10             // 0.1%
#define MAX_EARLY_EXERCISE_PENALTY 1000 // 10%
```

## 정산 공식

### Call Option Payout
```
if (spot_price > strike_price) {
    payout = (spot_price - strike_price) * quantity / spot_price
} else {
    payout = 0
}
```

### Put Option Payout
```
if (strike_price > spot_price) {
    payout = (strike_price - spot_price) * quantity / spot_price
} else {
    payout = 0
}
```

### Profit/Loss Calculation
```
P&L = payout - premium_paid
```

## 리스크 관리

### 리스크 점수 (1-10)
- **시간 리스크**: 만기까지 24시간 미만 (+3)
- **규모 리스크**: 전체 수량의 50% 초과 (+3)
- **프리미엄 리스크**: 20% 초과 지불 (+2)

### 담보 요구사항
- **콜옵션**: 기초자산 수량 × 110%
- **풋옵션**: (행사가 × 수량 / 100) × 110%

## BitVMX 통합

### 컴파일
```bash
# RISC-V 32bit 컴파일
riscv32-unknown-elf-gcc -march=rv32im -mabi=ilp32 \
    -nostdlib -nostartfiles -static -O2 \
    btcfi_option_registration.c \
    -o btcfi_option_registration.elf
```

### 실행
```bash
# BitVMX 에뮬레이터 실행
cargo run --release -p emulator -- execute \
    --elf btcfi_option_registration.elf \
    --input [HEX_INPUT] \
    --stdout
```

## 오라클 시스템

### 오라클 아키텍처
1. **3개 오라클 소스**: Binance, Coinbase, Kraken
2. **Oracle Aggregator**: 3개 가격 수집 후 합의 도출
3. **Settlement 입력**: Aggregator의 최종 가격만 사용

### 가격 결정 프로세스
1. Oracle Aggregator가 3개 거래소에서 가격 수집
2. Aggregator가 2/3 합의 또는 중간값 계산
3. Aggregator가 최종 가격에 서명
4. Settlement은 Aggregator의 서명된 가격만 검증

### Aggregator 데이터 구조
```c
struct AggregatorData {
    uint64_t aggregated_price;      // 최종 합의 가격
    uint8_t aggregator_signature[64]; // Aggregator 서명
    uint32_t oracle_count;          // 항상 3
    uint8_t aggregator_hash[32];    // Aggregator 식별자
}
```

## 보안 고려사항

1. **Double Spending 방지**: payment_proof 해시 검증
2. **Front-running 방지**: BitVMX pre-sign 메커니즘
3. **Oracle 조작 방지**: 다수 오라클 합의 + 서명
4. **Overflow 방지**: 수동 64비트 연산 구현
5. **Reentrancy 방지**: 상태 변경 원자성 보장

## 프로덕션 체크리스트

- [ ] 모든 C 프로그램 RISC-V 컴파일 완료
- [ ] BitVMX 에뮬레이터 테스트 통과
- [ ] 오라클 서명 검증 구현
- [ ] 에스크로 스마트 컨트랙트 배포
- [ ] 유동성 풀 자금 확보
- [ ] 리스크 관리 파라미터 조정
- [ ] 메인넷 배포 전 감사

## 성능 지표

- **Registration**: ~691 BitVMX steps
- **Purchase**: ~500 BitVMX steps  
- **Settlement**: ~800 BitVMX steps
- **Memory Usage**: < 4KB per transaction
- **Proof Size**: ~32KB per settlement

## 테스트 실행

```bash
# Python 통합 테스트
python3 test_btcfi_options.py

# 개별 프로그램 테스트
./test_registration.sh
./test_purchase.sh
./test_settlement.sh
```

## 라이선스

BTCFi Options System은 상용 서비스를 위해 설계되었으며, 프로덕션 환경에서의 사용을 권장합니다.