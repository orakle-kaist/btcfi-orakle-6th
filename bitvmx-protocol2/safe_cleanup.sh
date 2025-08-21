#!/bin/bash
# BitVMX 프로젝트 안전한 정리 스크립트
# 기존 작업을 보존하면서 정리

echo "=========================================="
echo "BitVMX 옵션 시스템 - 안전한 정리"
echo "=========================================="
echo ""
echo "⚠️  중요: 백업을 먼저 생성합니다"
echo ""

# 0. 백업 생성
if [ ! -d "../bitvmx-protocol2.backup" ]; then
    echo "백업 생성 중..."
    cp -r ../bitvmx-protocol2 ../bitvmx-protocol2.backup
    echo "✅ 백업 완료: ../bitvmx-protocol2.backup"
else
    echo "⚠️  백업이 이미 존재합니다"
fi

echo ""
echo "=========================================="
echo "정리 시작"
echo "=========================================="

# 1. 중복 디렉토리 제거 (prover_app에 이미 있는 것들)
echo ""
echo "1. 중복 디렉토리 제거..."
if [ -d "api" ] && [ -d "prover_app/api" ]; then
    rm -rf api/
    echo "   ✅ api/ 제거 (prover_app/api 사용)"
fi
if [ -d "domain" ] && [ -d "prover_app/domain" ]; then
    rm -rf domain/
    echo "   ✅ domain/ 제거 (prover_app/domain 사용)"
fi
if [ -d "dependency_injection" ] && [ -d "prover_app/dependency_injection" ]; then
    rm -rf dependency_injection/
    echo "   ✅ dependency_injection/ 제거"
fi
if [ -d "persistence" ] && [ -d "prover_app/persistence" ]; then
    rm -rf persistence/
    echo "   ✅ persistence/ 제거"
fi
if [ -d "common" ] && [ -d "blockchain_query_services/common" ]; then
    rm -rf common/
    echo "   ✅ common/ 제거"
fi
if [ -d "entities" ]; then
    rm -rf entities/
    echo "   ✅ entities/ 제거"
fi
if [ -d "services" ] && [ -d "blockchain_query_services/services" ]; then
    rm -rf services/
    echo "   ✅ services/ 제거"
fi

# 2. 루트의 테스트/임시 파일 제거
echo ""
echo "2. 테스트/임시 파일 정리..."
[ -f "btcfi_option.c" ] && rm -f btcfi_option.c && echo "   ✅ btcfi_option.c 제거"
[ -f "btcfi_option.elf" ] && rm -f btcfi_option.elf && echo "   ✅ btcfi_option.elf 제거"
[ -f "option_settlement.c" ] && rm -f option_settlement.c && echo "   ✅ option_settlement.c 제거 (중복)"
[ -f "complete_dto.json" ] && rm -f complete_dto.json && echo "   ✅ complete_dto.json 제거"
[ -f "dto_template.json" ] && rm -f dto_template.json && echo "   ✅ dto_template.json 제거"
[ -f "bitvmx_hash_chain.json" ] && rm -f bitvmx_hash_chain.json && echo "   ✅ bitvmx_hash_chain.json 제거"
[ -f "generate_hash_chain.py" ] && rm -f generate_hash_chain.py && echo "   ✅ generate_hash_chain.py 제거"
[ -f "generate_keys.py" ] && rm -f generate_keys.py && echo "   ✅ generate_keys.py 제거"
[ -f "main.py" ] && rm -f main.py && echo "   ✅ main.py 제거 (루트)"
[ -f "compile_option_elfs.sh" ] && rm -f compile_option_elfs.sh && echo "   ✅ compile_option_elfs.sh 제거"
[ -f "execution_path_selector.py" ] && rm -f execution_path_selector.py && echo "   ✅ execution_path_selector.py 제거"
[ -f "bitvmx_option_system.py" ] && rm -f bitvmx_option_system.py && echo "   ✅ bitvmx_option_system.py 제거 (통합됨)"
[ -f "run_bitvmx_option.py" ] && rm -f run_bitvmx_option.py && echo "   ✅ run_bitvmx_option.py 제거"

# 3. 테스트 파일 정리 (tests 폴더로 이동)
echo ""
echo "3. 테스트 파일 이동..."
mkdir -p tests
[ -f "test_bitvmx_option_integration.py" ] && mv test_bitvmx_option_integration.py tests/ && echo "   ✅ test_bitvmx_option_integration.py → tests/"
if [ -d "scripts" ] && [ -f "scripts/test_bitvmx_setup.py" ]; then
    mv scripts/test_bitvmx_setup.py tests/ 2>/dev/null && echo "   ✅ test_bitvmx_setup.py → tests/"
    rmdir scripts 2>/dev/null
fi

# 4. Docker 파일 정리
echo ""
echo "4. Docker 파일 정리..."
[ -f "docker-compose-team.yml" ] && rm -f docker-compose-team.yml && echo "   ✅ docker-compose-team.yml 제거"
[ -f "docker-compose.hub.yml" ] && rm -f docker-compose.hub.yml && echo "   ✅ docker-compose.hub.yml 제거"

# 5. 사용하지 않는 디렉토리 확인
echo ""
echo "5. 추가 정리 대상 확인..."
if [ -d "contracts" ]; then
    echo "   ⚠️  contracts/ - Rust 계약 (확인 필요)"
fi
if [ -d "pybitvmbinding" ]; then
    echo "   ⚠️  pybitvmbinding/ - Python 바인딩 (확인 필요)"
fi
if [ -d "wheels" ]; then
    rm -rf wheels/
    echo "   ✅ wheels/ 제거 (빌드 아티팩트)"
fi

# 6. 분석 문서 제거
[ -f "PROJECT_STRUCTURE_ANALYSIS.md" ] && rm -f PROJECT_STRUCTURE_ANALYSIS.md

# 7. 빈 디렉토리 제거
echo ""
echo "6. 빈 디렉토리 제거..."
find . -type d -empty -delete 2>/dev/null

echo ""
echo "=========================================="
echo "✅ 정리 완료!"
echo "=========================================="
echo ""
echo "📁 현재 구조:"
echo ""
ls -la | grep "^d" | awk '{print "• " $NF}' | grep -v "^\.$" | grep -v "^\.\.$"
echo ""
echo "📝 주요 파일:"
echo "• BITVMX_OPTION_SYSTEM.md - 시스템 문서"
echo "• README.md - 프로젝트 문서"
echo "• docker-compose.yml - Docker 설정"
echo "• Dockerfile - Docker 이미지"
echo ""
echo "✅ 보존된 작업:"
echo "• 옵션 API (prover_app/api/v1/option/)"
echo "• Pre-sign 서비스 (bitvmx_native_presign_service.py)"
echo "• 옵션 C 파일 (option_*.c)"
echo "• 옵션 ELF 파일 (option_*.elf)"
echo ""
echo "💾 백업 위치: ../bitvmx-protocol2.backup"