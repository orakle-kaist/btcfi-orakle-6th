# 팀원용 BitVMX Protocol2 실행 가이드

## 🚨 ModuleNotFoundError 해결 방법

### 문제 원인
`ModuleNotFoundError: No module named 'bitvmx_protocol_library'` 에러는 Python이 모듈을 찾지 못해서 발생합니다.

## 📋 해결 방법

### 방법 1: Docker 사용 (권장) ✅

```bash
# wooss97의 이미지 사용
docker pull wooss97/bitvmx-verifier:latest
docker pull wooss97/bitvmx-prover:latest

# 컨테이너 실행
docker run -d --name bitvmx-verifier -p 8080:80 wooss97/bitvmx-verifier:latest
docker run -d --name bitvmx-prover -p 8081:80 wooss97/bitvmx-prover:latest

# 확인
curl http://localhost:8080/healthcheck
curl http://localhost:8081/healthcheck
```

### 방법 2: 로컬 실행 (Python 경로 설정 필요) 🐍

```bash
# 1. bitvmx-protocol2 디렉토리로 이동
cd bitvmx-protocol2

# 2. PYTHONPATH 설정 (중요!)
export PYTHONPATH="${PYTHONPATH}:$(pwd)"

# 3. 실행 스크립트 사용
./run_local.sh verifier  # Verifier 실행 (새 터미널)
./run_local.sh prover    # Prover 실행 (새 터미널)
./run_local.sh test      # 테스트 실행
```

### 방법 3: 직접 Python 실행

```bash
# PYTHONPATH 설정 후
cd bitvmx-protocol2
export PYTHONPATH="$(pwd):$PYTHONPATH"

# Verifier 실행
python3 -m uvicorn verifier_app.main:app --host 0.0.0.0 --port 8080

# Prover 실행 (새 터미널에서)
python3 -m uvicorn prover_app.main:app --host 0.0.0.0 --port 8081
```

## 🔧 환경 설정

### 필수 패키지 설치

```bash
# requirements 설치
pip3 install -r requirements/base.txt
pip3 install -r requirements/prover.txt
pip3 install -r requirements/verifier.txt
```

### 환경 변수 파일

```bash
# .env_common 생성
cat > .env_common << EOF
PROVER_HOST=localhost
PROVER_PORT=8081
VERIFIER_HOST=localhost
VERIFIER_PORT=8080
NETWORK=mutinynet
EOF
```

## 🧪 테스트

```bash
# 옵션 등록 트랜잭션 테스트
cd bitvmx-protocol2
export PYTHONPATH="$(pwd)"
python3 scripts/option/create_real_bitvmx_tx.py
```

## ⚠️ 주의사항

1. **PYTHONPATH 설정이 핵심입니다!**
   - 터미널을 새로 열 때마다 다시 설정해야 함
   - `export PYTHONPATH="$(pwd)"`

2. **포트 충돌 확인**
   - 8080, 8081 포트가 사용 중이면 안 됨
   - `lsof -i :8080` 로 확인

3. **Docker가 더 쉽습니다**
   - 복잡한 설정 없이 바로 실행 가능
   - wooss97 이미지 사용 권장

## 📞 문제 발생 시

1. Python 버전 확인: `python3 --version` (3.10 이상)
2. 현재 경로 확인: `pwd` (bitvmx-protocol2 디렉토리여야 함)
3. PYTHONPATH 확인: `echo $PYTHONPATH`
4. Docker 상태 확인: `docker ps`

---

**💡 Tip**: Docker를 사용하면 이런 경로 문제를 피할 수 있습니다!