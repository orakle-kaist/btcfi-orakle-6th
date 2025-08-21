# BitVMX 프로젝트 구조 분석 및 정리 계획

## 🔍 현재 구조 분석

### ✅ **핵심 - 반드시 유지**
```
bitvmx-protocol2/
├── prover_app/              # ✅ 메인 FastAPI 웹서비스 (포트 8001)
├── verifier_app/            # ✅ Verifier 서비스 (포트 8002)
├── bitvmx_protocol_library/ # ✅ BitVMX 핵심 라이브러리
├── BitVMX-CPU/              # ✅ RISC-V 실행 엔진
├── execution_files/         # ✅ ELF 파일 위치 (BitVMX 필수)
├── blockchain_query_services/ # ✅ Bitcoin 네트워크 연동
├── prover_files/            # ✅ Prover 데이터 저장
├── verifier_files/          # ✅ Verifier 데이터 저장
└── requirements/            # ✅ Python 의존성
```

### ⚠️ **중복 파일/폴더 - 정리 필요**
```
루트에 있는 중복:
├── api/                     # ❌ prover_app/api와 중복
├── domain/                  # ❌ prover_app/domain과 중복  
├── dependency_injection/    # ❌ prover_app/dependency_injection과 중복
├── persistence/             # ❌ prover_app/persistence와 중복
├── common/                  # ❌ blockchain_query_services/common과 중복
├── entities/                # ❌ 다른 곳과 중복
├── services/                # ❌ blockchain_query_services/services와 중복
```

### 📝 **우리가 추가한 옵션 관련 파일**
```
✅ 유지해야 할 파일:
├── prover_app/api/v1/option/router.py  # 옵션 API
├── prover_app/dependency_injection/api/v1/option.py  # 옵션 DI
├── bitvmx_protocol_library/transaction_generation/services/
│   ├── bitvmx_native_presign_service.py  # Pre-sign 서비스
│   ├── generate_option_presign_service.py  # 옵션 Pre-sign
│   └── presign_transaction_service.py  # Pre-sign TX
├── BitVMX-CPU/docker-riscv32/src/
│   ├── option_registration.c  # 옵션 등록 로직
│   ├── option_purchase.c      # 옵션 구매 로직
│   └── option_settlement.c    # 옵션 정산 로직
├── execution_files/
│   ├── option_registration.elf  # 컴파일된 등록 로직
│   ├── option_purchase.elf      # 컴파일된 구매 로직
│   └── option_settlement.elf    # 컴파일된 정산 로직
```

### 🗑️ **테스트/임시 파일 - 제거 가능**
```
루트의 테스트 파일:
├── btcfi_option.c           # 테스트 C 파일
├── btcfi_option.elf         # 테스트 ELF
├── option_settlement.c      # 중복 (BitVMX-CPU/src에 있음)
├── complete_dto.json        # 테스트 데이터
├── dto_template.json        # 테스트 템플릿
├── bitvmx_hash_chain.json   # 테스트 데이터
├── generate_hash_chain.py   # 테스트 스크립트
├── generate_keys.py         # 테스트 스크립트
├── main.py                  # 루트의 불필요한 main
├── compile_option_elfs.sh   # 임시 스크립트
├── execution_path_selector.py  # 테스트 파일
├── test_bitvmx_option_integration.py  # 테스트 파일
├── run_bitvmx_option.py     # 테스트 실행 파일
├── bitvmx_option_system.py  # 이미 prover_app에 통합
```

### 🔧 **Docker 파일**
```
유지:
├── docker-compose.yml       # ✅ 메인 Docker 설정
├── Dockerfile              # ✅ 메인 Dockerfile

제거 가능:
├── docker-compose-team.yml  # ❌ 중복
├── docker-compose.hub.yml   # ❌ 중복
```

### 📦 **기타**
```
검토 필요:
├── contracts/              # Rust 계약 - 사용 여부 확인
├── pybitvmbinding/         # Python 바인딩 - 사용 여부 확인
├── wheels/                 # 빌드 아티팩트 - 제거 가능
├── option_products/        # 옵션 상품 저장 - 유지
├── scripts/                # 스크립트 - tests/로 이동
```

## 🎯 정리 원칙

1. **BitVMX 핵심 구조 유지**
   - prover_app, verifier_app 구조 유지
   - execution_files 위치 고정
   - bitvmx_protocol_library 보존

2. **우리 작업 보존**
   - 옵션 관련 모든 파일 유지
   - Pre-sign 서비스 유지
   - C 파일과 ELF 파일 유지

3. **중복 제거**
   - 루트의 중복 폴더 제거
   - 테스트 파일 정리
   - 임시 파일 제거

## 📋 정리 계획

### Phase 1: 백업
```bash
# 전체 백업 먼저
cp -r bitvmx-protocol2 bitvmx-protocol2.backup
```

### Phase 2: 중복 제거
```bash
# 중복 폴더만 제거 (prover_app에 있는 것들)
rm -rf api/ domain/ dependency_injection/ persistence/ common/ entities/ services/
```

### Phase 3: 테스트 파일 정리
```bash
# tests 폴더 생성 후 이동
mkdir -p tests
mv test_*.py tests/
mv scripts/*.py tests/
```

### Phase 4: 임시 파일 제거
```bash
# 루트의 테스트/임시 파일 제거
rm -f btcfi_option.* option_settlement.c *.json generate_*.py main.py
rm -f compile_option_elfs.sh execution_path_selector.py run_bitvmx_option.py
rm -f bitvmx_option_system.py  # 이미 통합됨
```

### Phase 5: Docker 정리
```bash
# 중복 Docker 파일 제거
rm -f docker-compose-team.yml docker-compose.hub.yml
```

## ⚠️ 주의사항

1. **execution_files/ 절대 건드리지 않기**
   - BitVMX가 ELF를 읽는 고정 위치

2. **prover_app/api/v1/option/ 유지**
   - 우리가 추가한 옵션 API

3. **bitvmx_native_presign_service.py 유지**
   - 핵심 Pre-sign 구현

4. **C 파일들 유지**
   - BitVMX-CPU/docker-riscv32/src/option_*.c

## ✅ 최종 구조 (정리 후)

```
bitvmx-protocol2/
├── prover_app/              # FastAPI 웹서비스
├── verifier_app/            # Verifier 서비스
├── bitvmx_protocol_library/ # 핵심 라이브러리
├── BitVMX-CPU/              # RISC-V 엔진
├── execution_files/         # ELF 파일들
├── blockchain_query_services/ # Bitcoin 연동
├── prover_files/            # Prover 데이터
├── verifier_files/          # Verifier 데이터
├── option_products/         # 옵션 상품 데이터
├── tests/                   # 테스트 파일
├── requirements/            # 의존성
├── docker-compose.yml       # Docker 설정
├── Dockerfile              # Docker 이미지
├── README.md               # 문서
├── BITVMX_OPTION_SYSTEM.md # 옵션 시스템 문서
└── .gitignore              # Git 설정
```

이렇게 정리하면:
- BitVMX 원칙 준수 ✅
- 우리 작업 보존 ✅
- 깔끔한 구조 ✅