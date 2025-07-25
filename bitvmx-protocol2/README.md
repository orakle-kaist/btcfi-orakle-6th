# BitVMX Integration

이 디렉토리는 BitVMX 프로토콜의 핵심 컴포넌트를 포함합니다.

## 구조

### 1. Docker 기반 Two-Track 시스템
- **prover-backend**: 증명 생성 서버 (포트 8081)
- **verifier-backend**: 검증 서버 (포트 8080)
- **bitcoin-regtest-node**: 로컬 Bitcoin 테스트넷

### 2. RISC-V Toolchain
- `rv32im` 아키텍처 지원
- Docker 컨테이너 내에서 C → RISC-V ELF 컴파일
- BitVMX-CPU 에뮬레이터로 실행

### 3. 핵심 컴포넌트
- **BitVMX-CPU**: Rust 기반 RISC-V 에뮬레이터
- **bitvmx_protocol_library**: Python 프로토콜 라이브러리
- **execution_files**: 컴파일된 RISC-V 프로그램들

## 실행 방법

1. Docker 환경 시작:
```bash
cd bitvmx
docker-compose up -d
```

2. RISC-V 프로그램 컴파일:
```bash
docker-compose run --rm prover-backend /app/scripts/compile_program.sh option_settlement
```

3. 증명 생성:
```bash
curl -X POST http://localhost:8081/prove \
  -H "Content-Type: application/json" \
  -d '{"program": "option_settlement", "input": "..."}'
```

## 주의사항
- 서브모듈이 아닌 직접 포함된 코드입니다
- 모든 수정사항은 메인 레포지토리에 직접 커밋됩니다