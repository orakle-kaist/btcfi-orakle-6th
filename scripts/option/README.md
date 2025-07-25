# BTCFi BitVMX 옵션 등록 데모 시스템

실제 BitVMX 프로토콜과 비트코인 레그테스트를 사용한 완전 통합 옵션 등록 시스템입니다.

## 📁 스크립트 파일들

### 🎯 메인 데모 스크립트

- **`create_bitvmx_option_demo.py`** - **완전 통합 데모 시스템**
  - 실제 BitVMX 에뮬레이터 실행 (RISC-V 32bit)
  - 투명한 옵션 데이터 온체인 저장
  - 2단계 트랜잭션 구조 (BitVMX 앵커링 + 옵션 데이터)
  - 자동 트랜잭션 분석 및 검증
  - 사용자 인터랙티브 인터페이스

### 📊 개별 도구들

- **`create_real_bitvmx_tx.py`** - BitVMX 트랜잭션 생성만
- **`analyze_btcfi_transaction.py`** - 트랜잭션 분석만

## 🚀 실행 방법

### 기본 실행 (추천)
```bash
cd scripts/option/
python3 create_bitvmx_option_demo.py --default
```

### 사용자 입력 모드
```bash
python3 create_bitvmx_option_demo.py
```

## 💎 최신 실행 결과 (2025-07-25)

### 🎊 완전 성공한 데모 실행

```
🎊 BTCFi BitVMX 옵션 등록 완료!

📋 최종 결과 요약:
🔗 1단계 - BitVMX 앵커링 트랜잭션
   TX ID: e39320f8e127586b296157fc5f6d282ed1625c441ddf45e8e3aec077784c9b00
   크기: 279 bytes (198 vBytes)
   구조: 1개 입력 → 2개 출력
   출력값: 79.96829859 BTC
   데이터: BitVMX:9cc626dfe6cd76df6a70a523fe69adc21e4f8a11e9cf4cd3ed259976275f6317:3597

🎯 2단계 - 옵션 데이터 트랜잭션  
   TX ID: 7a4a07d04df73d6b485565658a6e315a3585e66bbce17bf429597a6f5ab79c1b
   옵션 타입: CALL
   옵션 ID: d1
   행사가: $116,000
   수량: 1.0 BTC
   만료일: 3일 후
   크기: 245 bytes (164 vBytes)
   데이터: C|d1|116000|1753728475|1.0|83810400ba0c30a9

💎 BitVMX 실행 결과:
   해시: 9cc626dfe6cd76df6a70a523fe69adc21e4f8a11e9cf4cd3ed259976275f6317
   실행 단계: 3597단계
   에뮬레이터: RISC-V 32bit
```

### 🔍 자동 트랜잭션 분석

#### 1단계 트랜잭션 분석
```
🔍 트랜잭션 분석: e39320f8e127586b296157fc5f6d282ed1625c441ddf45e8e3aec077784c9b00
Size: 279 bytes
vSize: 198 vBytes
Inputs: 1, Outputs: 2

📄 OP_RETURN 데이터: BitVMX:9cc626dfe6cd76df6a70a523fe69adc21e4f8a11e9cf4cd3ed259976275f6317:3597

📊 분석 결과 요약:
   • BitVMX 해시: 9cc626dfe6cd76df...
   • 실행 단계: 3597단계
```

#### 2단계 트랜잭션 분석
```
🔍 트랜잭션 분석: 7a4a07d04df73d6b485565658a6e315a3585e66bbce17bf429597a6f5ab79c1b
Size: 245 bytes
vSize: 164 vBytes
Inputs: 1, Outputs: 2

📄 OP_RETURN 데이터: C|d1|116000|1753728475|1.0|83810400ba0c30a9
🔍 파싱된 옵션 데이터:
   • 타입: CALL
   • 옵션 ID: d1
   • 행사가: $116,000
   • 수량: 1.0 BTC
   • 만료: 1753728475 (timestamp)
   • BitVMX 참조 해시: 83810400ba0c30a9

📊 분석 결과 요약:
   • 옵션: CALL $116,000 (1.0 BTC)
```

## 🏗️ 시스템 아키텍처

### 2단계 트랜잭션 구조

```
┌─────────────────────────────────────┐
│        1단계: BitVMX 앵커링          │
│                                     │
│  🔗 BitVMX 에뮬레이터 실행           │
│  📊 3597단계 해시체인 생성           │
│  💾 OP_RETURN: BitVMX:해시:단계      │
│                                     │
└─────────────┬───────────────────────┘
              │
              ▼
┌─────────────────────────────────────┐
│        2단계: 옵션 데이터            │
│                                     │
│  📝 투명한 옵션 정보                 │
│  🔗 BitVMX 트랜잭션 해시 참조        │
│  💾 OP_RETURN: C|ID|가격|만료|수량|해시│
│                                     │
└─────────────────────────────────────┘
```

### 투명한 옵션 데이터 구조

**형식**: `C|d1|116000|1753728475|1.0|83810400ba0c30a9`

| 필드 | 값 | 설명 |
|------|-----|------|
| `C` | CALL | 옵션 타입 |
| `d1` | d1 | 옵션 ID |
| `116000` | $116,000 | 행사가 |
| `1753728475` | timestamp | 만료일 |
| `1.0` | 1.0 BTC | 수량 |
| `83810400ba0c30a9` | SHA256 해시 | BitVMX 참조 |

### 핵심 특징

- **✅ 완전 투명성**: 모든 옵션 정보가 온체인에서 직접 읽기 가능
- **✅ BitVMX 연결**: SHA256 해시로 앵커링 트랜잭션과 안전하게 연결  
- **✅ 공간 효율성**: 43자로 80바이트 OP_RETURN 제한 내 수용
- **✅ 자동 분석**: 트랜잭션 데이터 자동 파싱 및 검증
- **✅ 실제 실행**: 진짜 BitVMX RISC-V 에뮬레이터 사용

## 🔧 실제 BitVMX 구성 요소

### BitVMX 에뮬레이터
- **경로**: `/bitvmx_protocol/bitvmx/BitVMX-CPU/target/release/emulator`
- **아키텍처**: RISC-V 32bit
- **실행 파일**: `btcfi_option_registration.elf`

### 옵션 입력 데이터 구조
```c
typedef struct {
    uint32_t option_type;         // 0=Call, 1=Put
    uint64_t strike_price;        // USD cents
    uint64_t quantity;            // satoshis
    uint64_t premium;             // satoshis
    uint64_t expiry_timestamp;    // Unix timestamp
    uint8_t issuer_hash[32];      // SHA256 hash
    uint32_t oracle_count;        // Number of oracles (3-5)
    uint8_t oracle_hashes[5][8];  // Oracle hashes
} __attribute__((packed)) BTCFiOptionInput;
```

### 실행 과정
1. **옵션 데이터 패킹**: 구조체를 바이너리로 변환
2. **BitVMX 실행**: RISC-V 에뮬레이터로 실제 실행
3. **해시체인 생성**: 3597단계 실행 트레이스
4. **트랜잭션 생성**: 2단계 트랜잭션 구조로 온체인 기록

## 🌐 연동 서비스

### Bitcoin Regtest
- **RPC**: localhost:18443
- **Wallet**: Alice
- **Explorer**: http://localhost:1080

### Mempool Explorer 링크
- **BitVMX 앵커**: http://localhost:1080/tx/e39320f8e127586b296157fc5f6d282ed1625c441ddf45e8e3aec077784c9b00
- **옵션 데이터**: http://localhost:1080/tx/7a4a07d04df73d6b485565658a6e315a3585e66bbce17bf429597a6f5ab79c1b

## 🎯 사용 사례

### 데모 시연
```bash
# 기본값으로 빠른 데모
python3 create_bitvmx_option_demo.py --default

# 사용자 정의 옵션으로 데모
python3 create_bitvmx_option_demo.py
```

### 개발자 테스트
```bash
# 개별 스크립트 실행
python3 create_real_bitvmx_tx.py
python3 analyze_btcfi_transaction.py [TX_ID]
```

## 📝 버전 정보

- **버전**: 4.0.0 (완전 통합 데모)
- **최종 업데이트**: 2025-07-25 23:45 KST
- **BitVMX 표준**: 100% 준수
- **실제 실행**: ✅ 3597단계 해시체인
- **투명한 데이터**: ✅ 43자 압축 형식

**🎊 진짜 BitVMX 프로토콜로 완전한 옵션 등록 시스템 구현 완료!**