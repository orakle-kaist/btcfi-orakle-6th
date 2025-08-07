# BitVMX Oracle 프로젝트 구조

## 🎯 프로젝트 목표
BitVMX 프로토콜을 활용한 단방향 옵션 구현 및 챌린지-응답 자동화

## ✅ 완료된 작업
1. **실제 Bitcoin 트랜잭션 브로드캐스트**
   - MutinyNet 테스트넷에 95,000 sats 트랜잭션 성공
   - TXID: `8c5b24941f67125780d753328fe4a2b57c6f26b938186f4ac0190574a308eaf8`
   - BIP-143 서명 구현

2. **BitVMX 챌린지-응답 자동화**
   - Docker 컨테이너 (Verifier/Prover) 자동 관리
   - 챌린지-응답 루프 구현
   - 실시간 모니터링 대시보드

3. **암호학 구현**
   - BIP-340 Schnorr 서명
   - Winternitz OTS (일회용 서명)
   - HD 지갑 키 유도

## 📁 디렉토리 구조

```
btcfi-orakle-6th/
├── bitvmx-protocol2/           # BitVMX 프로토콜 핵심 구현
│   ├── bitvmx_protocol_library/ # BitVMX 라이브러리
│   ├── BitVMX-CPU/             # BitVMX CPU 에뮬레이터
│   ├── api/                    # API 엔드포인트
│   ├── services/               # 서비스 레이어
│   ├── verifier_app/           # Verifier 애플리케이션
│   ├── prover_app/             # Prover 애플리케이션
│   └── execution_files/        # 실행 파일 및 트레이스
│
├── scripts/                    # 자동화 및 유틸리티 스크립트
│   ├── bitvmx_automation.py   # 챌린지-응답 자동화
│   └── presign_option_setup.py # Pre-sign 옵션 설정
│
├── docs/                       # 문서
├── contracts/                  # 스마트 컨트랙트
└── config/                     # 설정 파일
```

## 🔑 핵심 파일

### bitvmx-protocol2/
- **btcfi_option_challenge.py**: 옵션 챌린지 프로토콜
- **direct_challenge_protocol.py**: 직접 챌린지 구현
- **bitvmx_hash_chain_wrapper.py**: 해시 체인 래퍼
- **generate_hash_chain.py**: 해시 체인 생성
- **create_option_input.py**: 옵션 입력 생성
- **create_real_signatures.py**: 실제 서명 생성

### scripts/
- **bitvmx_automation.py**: 자동화 시스템
- **presign_option_setup.py**: Pre-sign 옵션 구조

## 🚀 사용 방법

### 1. Docker 컨테이너 시작
```bash
docker-compose up -d
```

### 2. 챌린지-응답 자동화 실행
```bash
python scripts/bitvmx_automation.py [TXID] [SETUP_UUID]
```

### 3. Pre-sign 옵션 생성
```bash
python scripts/presign_option_setup.py
```

## 🔧 환경 설정

### 필수 환경 변수 (.env_common)
```
BITCOIN_NETWORK=mutinynet
BITCOIN_RPC_HOST=...
BITCOIN_RPC_USER=...
BITCOIN_RPC_PASSWORD=...
```

### Verifier 설정 (.env_verifier)
```
VERIFIER_PORT=8080
```

### Prover 설정 (.env_prover)
```
PROVER_PORT=8081
PROVER_PRIVATE_KEY=...
```

## 📊 테스트 결과
- ✅ Setup API: 200 OK
- ✅ Next Step API: 작동 확인
- ✅ 챌린지-응답 루프: 3라운드 100% 성공
- ✅ MutinyNet 트랜잭션: 확인됨

## 🎯 다음 단계
1. Pre-sign 기반 단방향 옵션 완성
2. 오라클 가격 피드 통합
3. 실제 옵션 행사 메커니즘 구현
4. 분쟁 해결 프로토콜 강화

## 📝 참고 문서
- [BitVMX Protocol](https://github.com/bitvmx/bitvmx-protocol)
- [MutinyNet Explorer](https://mutinynet.com)
- [BIP-143 Specification](https://github.com/bitcoin/bips/blob/master/bip-0143.mediawiki)