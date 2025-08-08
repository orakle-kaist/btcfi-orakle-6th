# BitVMX Protocol - BTCFi 옵션 등록 시스템

## 🚀 개요

BitVMX 프로토콜을 활용한 Bitcoin Layer 1 옵션 등록 시스템입니다. MutinyNet 테스트넷에서 실제 트랜잭션을 생성하고 브로드캐스트할 수 있습니다.

## ✅ 주요 기능

- **BitVMX 통합**: BitVMX 프로토콜을 통한 옵션 데이터 앵커링
- **실제 트랜잭션**: MutinyNet에 실제 Bitcoin 트랜잭션 브로드캐스트
- **BIP-143 서명**: SegWit (P2WPKH) 트랜잭션 지원
- **Docker 지원**: 팀원 간 동일한 환경 보장

## 📋 사전 요구사항

- Docker & Docker Compose
- Python 3.11+ (로컬 테스트용)
- MutinyNet 지갑 및 테스트 BTC

## 🛠 설치 및 설정

### 1. 레포지토리 클론

```bash
git clone [repository-url]
cd bitvmx-protocol3
```

### 2. 환경변수 설정

```bash
cp .env.example .env
```

`.env` 파일을 열어 필요한 값들을 설정:
- `PRIVATE_KEY`: 본인의 프라이빗 키 (테스트넷용!)
- `ADDRESS`: 프라이빗 키에 대응하는 주소

### 3. Docker 환경 실행 (선택사항)

```bash
# 이미지 빌드
docker-compose build

# 서비스 실행
docker-compose up -d
```

### 4. 로컬 환경 설정 (Docker 없이)

```bash
# 가상환경 생성
python3 -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 의존성 설치
pip install -r requirements.txt
```

## 🎯 사용 방법

### 옵션 등록 트랜잭션 생성

```bash
cd domain/option
python3 create_real_tx.py
```

성공 시 출력 예시:
```
🎯 BitVMX 옵션 등록 - 실제 트랜잭션
============================================================
  UTXO: a3948d735b2a2a88...:1
  금액: 100,000 sats
  옵션: CALL $122,000
  BitVMX: 9cc626dfe6cd76df...
  
✅ 브로드캐스트 성공!
  TXID: 2e0e1d328d59a0eba058d0da24e5b2b8...
  Explorer: https://mutinynet.com/tx/2e0e1d328d59a0eba058d0da24e5b2b8...
```

## 📂 프로젝트 구조

```
bitvmx-protocol3/
├── domain/
│   └── option/
│       ├── create_real_tx.py      # 메인 트랜잭션 생성 스크립트
│       ├── registration.py         # 옵션 등록 로직
│       └── bitvmx_setup.py        # BitVMX 셋업 관리
├── blockchain_query_services/      # 블록체인 쿼리 서비스
├── bitvmx_protocol_library/        # BitVMX 프로토콜 라이브러리
├── .env.example                    # 환경변수 템플릿
├── requirements.txt                # Python 의존성
└── README.md                       # 이 파일
```

## 🔑 테스트넷 자금 확보

MutinyNet Faucet에서 테스트 BTC를 받으세요:
- https://faucet.mutinynet.com/

최소 100,000 sats 이상 보유 권장

## 🧪 테스트 가이드

### 1. UTXO 확인

```python
# domain/option/create_real_tx.py 파일 수정
UTXO = {
    'txid': 'your_txid_here',
    'vout': 1,
    'amount': 100000,
    'address': 'your_address_here'
}
```

### 2. 프라이빗 키 설정

```python
PRIVATE_KEY = 'your_private_key_here'  # 테스트넷 전용!
```

### 3. 트랜잭션 실행

```bash
python3 domain/option/create_real_tx.py
```

## 📡 트랜잭션 확인

브로드캐스트된 트랜잭션 확인:
- MutinyNet Explorer: https://mutinynet.com/
- BitVMX Explorer: https://bitvmx-explorer.com/

## ⚠️ 주의사항

- **테스트넷 전용**: 메인넷에서 절대 사용하지 마세요
- **프라이빗 키 보안**: `.env` 파일을 절대 커밋하지 마세요
- **UTXO 소유권**: 사용하려는 UTXO를 실제로 소유하고 있는지 확인

## 🤝 기여 방법

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## 📊 성공 사례

실제 브로드캐스트된 트랜잭션:
- TXID: `2e0e1d328d59a0eba058d0da24e5b2b8e7b7b9c8184e96b0c9b244ee623e36fc`
- [Explorer Link](https://mutinynet.com/tx/2e0e1d328d59a0eba058d0da24e5b2b8e7b7b9c8184e96b0c9b244ee623e36fc)

## 🐛 문제 해결

### "witness 구조 오류" 발생 시
- P2WPKH witness는 정확히 2개 아이템 필요 (서명 + 공개키)
- BIP-143 sighash 계산이 올바른지 확인

### "UTXO not found" 오류
- UTXO가 이미 사용되었는지 확인
- 주소가 올바른지 확인
- Explorer에서 잔액 확인

## 📚 참고 자료

- [BitVMX Protocol](https://github.com/FairgateLabs/bitvmx_protocol)
- [BIP-143 Specification](https://github.com/bitcoin/bips/blob/master/bip-0143.mediawiki)
- [MutinyNet Documentation](https://mutinynet.com/docs)

## 📝 라이센스

MIT License

## 👥 팀

BTCFi Oracle Team - 6th Project

---

**문의사항이 있으시면 이슈를 생성해주세요!**