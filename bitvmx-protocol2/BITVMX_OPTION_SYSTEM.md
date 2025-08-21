# BitVMX 옵션 시스템 - 웹서비스

## 🏗️ 시스템 구조

```
bitvmx-protocol2/
├── prover_app/              # FastAPI 웹서비스 (포트 8001)
│   ├── api/v1/
│   │   ├── setup/          # 옵션 등록
│   │   ├── input/          # 옵션 구매  
│   │   ├── next-step/      # 옵션 정산
│   │   └── option/         # 옵션 전용 API
│   │
├── execution_files/         # ⭐ BitVMX가 실행하는 ELF 파일 위치 (고정)
│   ├── option_registration.elf  # 등록 로직
│   ├── option_purchase.elf      # 구매 로직  
│   ├── option_settlement.elf    # 정산 로직
│   ├── instruction_mapping.txt  # Bitcoin Script 매핑
│   └── instruction_commitment.txt # ROM commitment
│
└── BitVMX-CPU/docker-riscv32/src/  # C 소스 코드
    ├── option_registration.c
    ├── option_purchase.c
    └── option_settlement.c
```

### ⚠️ **중요: 파일 위치**
- **ELF 파일**: 반드시 `execution_files/` 디렉토리에 위치
- **C 파일**: `BitVMX-CPU/docker-riscv32/src/`에서 컴파일
- BitVMX는 `execution_files/`에서만 ELF를 읽음

## 🔄 전체 플로우

### 1️⃣ **옵션 상품 등록**

```javascript
// Frontend
POST http://localhost:8001/api/v1/option/register
{
    "option_type": "CALL",
    "strike_price": 50000,
    "expiry_days": 7,
    "pool_btc": 0.01
}

// Backend 처리
1. API 요청 수신
2. BitVMX Setup 호출
3. option_registration.elf 실행
4. Bitcoin 트랜잭션 생성
5. Setup UUID 반환
```

**실행되는 C 코드**: `option_registration.c`
- 옵션 파라미터 검증
- 풀 자금 Lock 스크립트 생성
- Bitcoin에 실제 등록

### 2️⃣ **옵션 구매**

```javascript
// Frontend
POST http://localhost:8001/api/v1/option/purchase
{
    "setup_uuid": "xxx-xxx",
    "buyer_address": "tb1q..."
}

// Backend 처리
1. API 요청 수신
2. BitVMX Input 호출
3. option_purchase.elf 실행
4. 프리미엄 계산
5. Pre-sign 트랜잭션 생성
6. Pre-sign 그래프 반환
```

**실행되는 C 코드**: `option_purchase.c`
- 프리미엄 계산 (Black-Scholes)
- Pre-sign 준비
- 구매자 검증

### 3️⃣ **옵션 정산**

```javascript
// Frontend
POST http://localhost:8001/api/v1/option/settle
{
    "setup_uuid": "xxx-xxx",
    "oracle_price": 52000,
    "presign_graph": {...}
}

// Backend 처리
1. API 요청 수신
2. BitVMX Next Step 호출
3. option_settlement.elf 실행
4. ITM/OTM 판단
5. Pre-sign 실행 또는 Challenge-Response
6. Bitcoin 정산 트랜잭션 브로드캐스트
```

**실행되는 C 코드**: `option_settlement.c`
- ITM/OTM 계산
- 정산 금액 결정
- 트랜잭션 실행

## 📡 웹서비스 API

### **Backend 서버**
```bash
# 실행
cd prover_app
uvicorn main:app --port 8001

# API 문서
http://localhost:8001/docs
```

### **Frontend 연동**
```javascript
// React/Vue/Next.js
const API = 'http://localhost:8001/api/v1';

// 옵션 목록 조회
const products = await fetch(`${API}/option/products`);

// 옵션 구매
const purchase = await fetch(`${API}/option/purchase`, {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({...})
});

// WebSocket 실시간 가격
const ws = new WebSocket('ws://localhost:8001/ws/prices');
ws.onmessage = (event) => {
    const price = JSON.parse(event.data);
    updatePrice(price.btc_usd);
};
```

## 🔧 핵심 컴포넌트

### **ELF 파일 (RISC-V 바이너리)**
- BitVMX가 실행하는 실제 로직
- C 코드를 컴파일한 결과물
- 각 단계별로 다른 ELF 실행

### **BitVMX 실행 엔진**
- ELF 파일 실행
- 실행 트레이스 생성
- Bitcoin Script로 검증

### **Pre-sign 메커니즘**
- 운영자가 미리 서명한 트랜잭션
- Oracle 가격 증명만 추가하면 실행
- Challenge-Response 우회 (95% 케이스)

## ✅ Bitcoin 네트워크 연동

1. **MutinyNet (Testnet)**: 테스트 환경
2. **실제 트랜잭션**: BitVMX Setup으로 생성
3. **브로드캐스트**: MutinyNet API 사용

```python
# 실제 Bitcoin 트랜잭션
setup_tx = create_setup_transaction(...)
txid = broadcast_to_mutinynet(setup_tx)
```

## 🚀 실행 방법

```bash
# 1. 의존성 설치
pip install -r requirements/prover.txt

# 2. Prover 서버 실행
PYTHONPATH=. uvicorn prover_app.main:app --port 8001

# 3. API 테스트
curl http://localhost:8001/api/v1/option/register \
  -X POST \
  -H "Content-Type: application/json" \
  -d '{"option_type":"CALL","strike_price":50000}'
```

## 📊 데이터 흐름

```
User → Frontend → API → BitVMX → ELF실행 → Bitcoin TX → Blockchain
                    ↓
                 Oracle (가격)
```

## 🎯 핵심 포인트

1. **BitVMX 원칙 준수**: Setup → Input → Next Step
2. **웹서비스 구조**: FastAPI + REST API + WebSocket
3. **실제 Bitcoin**: MutinyNet에 실제 배포
4. **ELF 실행**: 각 단계별 C 로직 실행

---

**이제 BitVMX의 정석 구조로 완전한 옵션 웹서비스가 작동합니다!**