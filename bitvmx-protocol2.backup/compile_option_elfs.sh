#!/bin/bash
"""
옵션 관련 C 파일들을 RISC-V ELF로 컴파일하는 스크립트

BitVMX는 이 ELF 파일들을 실행합니다:
1. option_registration.elf - 옵션 상품 등록
2. option_purchase.elf - 옵션 구매
3. option_settlement.elf - 옵션 정산
"""

echo "=========================================="
echo "Compiling Option C files to RISC-V ELF"
echo "=========================================="

# BitVMX docker-riscv32 디렉토리로 이동
cd BitVMX-CPU/docker-riscv32

# Docker 이미지 빌드 (없으면)
if [[ "$(docker images -q bitvmx-docker-riscv32 2> /dev/null)" == "" ]]; then
    echo "Building Docker image..."
    ./docker-build.sh
fi

# 1. 옵션 등록 컴파일
echo ""
echo "1. Compiling option_registration.c..."
./docker-run.sh src/option_registration.c
if [ -f "src/option_registration.elf" ]; then
    cp src/option_registration.elf ../../execution_files/
    echo "   ✅ option_registration.elf created"
else
    echo "   ❌ Failed to compile option_registration.c"
fi

# 2. 옵션 구매 컴파일
echo ""
echo "2. Compiling option_purchase.c..."
./docker-run.sh src/option_purchase.c
if [ -f "src/option_purchase.elf" ]; then
    cp src/option_purchase.elf ../../execution_files/
    echo "   ✅ option_purchase.elf created"
else
    echo "   ❌ Failed to compile option_purchase.c"
fi

# 3. 옵션 정산 컴파일
echo ""
echo "3. Compiling option_settlement.c..."
./docker-run.sh src/option_settlement.c
if [ -f "src/option_settlement.elf" ]; then
    cp src/option_settlement.elf ../../execution_files/
    echo "   ✅ option_settlement.elf created"
else
    echo "   ❌ Failed to compile option_settlement.c"
fi

# execution_files 디렉토리로 돌아가기
cd ../../

# 결과 확인
echo ""
echo "=========================================="
echo "Checking compiled ELF files..."
echo "=========================================="
ls -la execution_files/*.elf

echo ""
echo "✅ All option ELF files are ready!"
echo ""
echo "Now BitVMX can execute:"
echo "• option_registration.elf - When registering products"
echo "• option_purchase.elf - When users purchase options"
echo "• option_settlement.elf - When settling at expiry"