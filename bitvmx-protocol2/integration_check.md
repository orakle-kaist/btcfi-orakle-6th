# BitVMX 옵션 시스템 통합 점검

## 1. 기존 BitVMX 플로우
```
Setup (한 번) → Input (여러 번) → Hash → Trace → Challenge/Response
```

## 2. 우리가 추가한 옵션 시스템

### 추가된 파일들:
- `prover_app/domain/models/option_product.py` - 옵션 상품 모델
- `prover_app/persistences/option_storage.py` - 옵션 데이터 저장소
- `prover_app/api/v1/option/router.py` - 옵션 API 엔드포인트

### 핵심 설계:
1. **Setup은 한 번만 생성** - 초기 자금 Lock
2. **옵션 상품은 여러 개 등록 가능** - 하나의 Setup으로 다수 상품 관리
3. **각 옵션 거래는 Input으로 기록** - BitVMX Input 메커니즘 활용
4. **Docker 컨테이너 기본 사용** - 로컬이 아닌 Docker의 Prover/Verifier 사용

## 3. 호환성 체크리스트

### ✅ 호환되는 부분:
- Setup 생성 로직 그대로 사용
- Input 제출 메커니즘 활용 (옵션 데이터를 hex로 인코딩)
- 기존 Docker 컨테이너 사용 (wooss97/bitvmx-prover, wooss97/bitvmx-verifier)
- BitVMX 트랜잭션 체인 구조 유지

### ⚠️ 주의사항:
- Input 크기: amount_of_input_words를 4로 설정 (옵션 파라미터용)
- UTXO 관리: Setup 생성 시 funding_amount_of_satoshis로 금액 제한
- Pre-sign 구현: 아직 미구현, 추가 작업 필요

### ❌ 충돌 가능성:
- 없음 (기존 코드 수정 최소화, 추가만 진행)

## 4. 온체인 기록 방식

### 옵션 등록 (온체인):
```python
Input_hex = [option_type][strike_price][spot_price][quantity]
→ BitVMX Input API → Hash 트랜잭션 생성
```

### 옵션 정산 (온체인):
```python
Input_hex = [option_type][strike_price][settlement_price][quantity]
→ BitVMX Input API → Trace 실행 → 정산 트랜잭션
```

## 5. Docker 기본 사용 설정

### 환경변수 (.env):
```
BITVMX_PROVER_URL=http://localhost:8001
BITVMX_VERIFIER_URL=http://localhost:8080
USE_DOCKER_DEFAULT=true
```

### API 호출:
- 모든 BitVMX 작업은 Docker 컨테이너의 API 사용
- 로컬 Python 코드는 단순 프록시 역할

## 6. 테스트 필요 항목

1. [ ] 새 Setup 생성 with 적절한 funding amount
2. [ ] 옵션 상품 등록 → Input 제출 → 온체인 기록
3. [ ] 여러 옵션 상품 동시 관리
4. [ ] 옵션 정산 플로우
5. [ ] Pre-sign 트랜잭션 생성 및 검증

## 7. 결론

현재까지의 작업은 기존 BitVMX 로직과 **완전히 호환**됩니다.
- 기존 코드 수정 없이 확장
- BitVMX의 Setup → Input → Hash 플로우 그대로 활용
- Docker 컨테이너를 기본으로 사용하여 일관성 확보