# 🚨 BitVMX Protocol2 문제 해결 가이드

## 자주 발생하는 문제들과 해결법

### 1. ModuleNotFoundError: No module named 'bitvmx_protocol_library'

**원인**: Docker 이미지에 라이브러리가 포함되지 않음

**해결법**:
```bash
# 볼륨 마운트로 실행
docker run -d \
  --name bitvmx-verifier \
  -p 8080:80 \
  -v $(pwd):/bitvmx-backend \
  wooss97/bitvmx-verifier:latest
```

### 2. FileNotFoundError: '.env_prover' 또는 '.env_verifier'

**원인**: 환경 설정 파일 누락

**해결법**:
```bash
# .env_prover 생성
cat > .env_prover << EOF
PROVER_HOST=0.0.0.0
PROVER_PORT=80
VERIFIER_URL=http://verifier-backend:80
NETWORK=mutinynet
EOF

# .env_verifier 생성
cat > .env_verifier << EOF
VERIFIER_HOST=0.0.0.0
VERIFIER_PORT=80
PROVER_URL=http://prover-backend:80
NETWORK=mutinynet
EOF
```

### 3. ImportError: cannot import name 'BitcoinNetwork'

**원인**: 의존성 패키지 누락

**해결법**:
```bash
pip install bitcoinutils==1.0.5
pip install ecdsa==0.18.0
pip install pydantic==2.5.3
```

### 4. Connection refused to localhost:8080

**원인**: 컨테이너 간 통신 문제

**해결법**:
- `localhost` 대신 컨테이너 이름 사용
- Docker network 확인: `docker network ls`
- 같은 네트워크에 있는지 확인

### 5. BitVMX-CPU build failed

**원인**: Rust/Cargo 빌드 실패

**해결법**:
```bash
# BitVMX-CPU 서브모듈 초기화
git submodule update --init --recursive

# 또는 스킵하고 미리 빌드된 버전 사용
```

### 6. Port already in use

**원인**: 8080, 8081 포트 이미 사용 중

**해결법**:
```bash
# 사용 중인 포트 확인
lsof -i :8080
lsof -i :8081

# 기존 프로세스 종료
kill -9 [PID]

# 또는 다른 포트 사용
docker run -p 9080:80 ...
```

## 🎯 빠른 해결 체크리스트

1. ✅ 현재 디렉토리가 `bitvmx-protocol2`인가?
2. ✅ Docker가 실행 중인가? (`docker ps`)
3. ✅ 필요한 파일들이 있는가?
   - `bitvmx_protocol_library/`
   - `.env_prover`
   - `.env_verifier`
   - `requirements/`
4. ✅ 포트가 열려있는가? (8080, 8081)
5. ✅ Python 버전이 3.10 이상인가?

## 💡 완전 초기화 방법

문제가 계속되면 완전히 다시 시작:

```bash
# 1. 기존 컨테이너 정리
docker stop $(docker ps -aq)
docker rm $(docker ps -aq)

# 2. 이미지 다시 받기
docker pull wooss97/bitvmx-verifier:latest
docker pull wooss97/bitvmx-prover:latest

# 3. 볼륨 마운트로 실행
docker run -d \
  --name verifier \
  -p 8080:80 \
  -v $(pwd):/bitvmx-backend \
  wooss97/bitvmx-verifier:latest

docker run -d \
  --name prover \
  -p 8081:80 \
  -v $(pwd):/bitvmx-backend \
  wooss97/bitvmx-prover:latest

# 4. 로그 확인
docker logs verifier
docker logs prover
```

## 📞 그래도 안 되면?

1. Docker 로그 전체 확인: `docker logs [container] --tail 100`
2. Python 에러 전체 확인: 스크린샷 첨부
3. 시스템 정보 공유: OS, Docker 버전, Python 버전

---

**작성자**: BTCFi Oracle Team
**최종 업데이트**: 2025-08-08