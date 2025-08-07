# Docker Hub 이미지 사용 가이드

## 빠른 시작 (빌드 없이 바로 실행)

Docker Hub에서 사전 빌드된 이미지를 사용하여 빌드 시간을 절약할 수 있습니다.

### 1. 환경 파일 설정
```bash
cp .env_common.example .env_common
cp .env_prover.example .env_prover  
cp .env_verifier.example .env_verifier
```

### 2. docker-compose.hub.yml 수정
`YOUR_USERNAME`을 실제 Docker Hub 사용자명으로 변경:
```yaml
image: YOUR_USERNAME/prover-backend:latest
image: YOUR_USERNAME/verifier-backend:latest
```

### 3. 실행
```bash
# Docker Hub에서 이미지 pull & 실행
docker compose -f docker-compose.hub.yml up

# 또는 백그라운드 실행
docker compose -f docker-compose.hub.yml up -d
```

### 4. 확인
- Prover API: http://localhost:8081
- Verifier API: http://localhost:8080

## 이미지 정보
- `prover-backend`: ~3.99GB
- `verifier-backend`: ~3.98GB
- 포함된 내용:
  - BitVMX-CPU (Rust 빌드 완료)
  - Python dependencies
  - pybitvmbinding wheel
  - 모든 필요한 실행 파일

## 주의사항
- 첫 pull 시 시간이 걸립니다 (각 4GB)
- execution_files/ 폴더는 여전히 로컬에 필요합니다
- .env 파일들도 로컬에 설정해야 합니다