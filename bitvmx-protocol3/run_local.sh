#!/bin/bash
# 로컬 실행 스크립트 - Python 경로 설정 포함

echo "🚀 BitVMX Protocol 로컬 실행 스크립트"
echo "======================================"

# 현재 디렉토리를 PYTHONPATH에 추가
export PYTHONPATH="${PYTHONPATH}:$(pwd)"

echo "📁 작업 디렉토리: $(pwd)"
echo "🐍 Python 경로: $PYTHONPATH"

# 어떤 서비스를 실행할지 선택
if [ "$1" = "verifier" ]; then
    echo "🔵 Verifier 서비스 시작 (포트 8080)..."
    python3 -m uvicorn verifier_app.main:app --host 0.0.0.0 --port 8080 --reload
elif [ "$1" = "prover" ]; then
    echo "🟢 Prover 서비스 시작 (포트 8081)..."
    python3 -m uvicorn prover_app.main:app --host 0.0.0.0 --port 8081 --reload
elif [ "$1" = "test" ]; then
    echo "🧪 테스트 스크립트 실행..."
    python3 scripts/run_bitvmx_setup.py
else
    echo "사용법: ./run_local.sh [verifier|prover|test]"
    echo ""
    echo "예시:"
    echo "  ./run_local.sh verifier  # Verifier 실행"
    echo "  ./run_local.sh prover    # Prover 실행"
    echo "  ./run_local.sh test      # 테스트 실행"
fi