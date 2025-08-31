#!/usr/bin/env python3
"""
BTCFi 옵션 상품 등록을 위한 BitVMX Setup
========================================

BitVMX 원칙에 따라:
1. 옵션 상품 데이터는 오프체인에 저장
2. 온체인에는 32바이트 커밋먼트만 저장
3. 실제 실행은 btcfi_option_registration_v2.elf 사용
"""

import json
import uuid
import hashlib
import time
import os
from typing import Dict, Optional

def create_option_registration_setup(
    funding_tx_id: str,
    funding_index: int = 0,
    funding_amount: int = 100000,
    private_key: str = None
) -> str:
    """
    옵션 상품 등록을 위한 BitVMX Setup 생성
    
    Args:
        funding_tx_id: 펀딩 트랜잭션 ID
        funding_index: 펀딩 출력 인덱스
        funding_amount: 펀딩 금액 (satoshis)
        private_key: 펀딩 UTXO의 private key
    
    Returns:
        setup_uuid: 생성된 Setup의 UUID
    """
    
    setup_uuid = str(uuid.uuid4())
    print(f"\n{'='*60}")
    print(f"BitVMX 옵션 상품 등록 Setup 생성")
    print(f"{'='*60}")
    print(f"UUID: {setup_uuid}")
    
    # 1. 옵션 상품 데이터 (오프체인)
    option_product = {
        "product_id": f"BTCOPT_{int(time.time())}",
        "name": "BTC Call Option Feb 2025",
        "type": "CALL",
        "strike_price": 65000,
        "expiry": "2025-02-01T00:00:00Z",
        "pool_size": 10.0,  # 10 BTC pool
        "min_purchase": 0.001,  # 0.001 BTC minimum
        "max_purchase": 1.0,  # 1 BTC maximum
        "created_at": int(time.time()),
        "creator": "tb1qt8rdur557nz338g3lekc6458pj0dl63c0s9904"
    }
    
    print(f"\n📊 옵션 상품 정보 (오프체인):")
    print(json.dumps(option_product, indent=2))
    
    # 2. 32바이트 커밋먼트 생성 (BitVMX 원칙)
    product_json = json.dumps(option_product, sort_keys=True, separators=(',', ':'))
    commitment_full = hashlib.sha256(product_json.encode()).hexdigest()
    
    # BitVMX는 32-bit (4 bytes) 입력을 사용하므로 처음 8자리(4바이트)만 사용
    commitment_onchain = commitment_full[:8]
    
    print(f"\n🔒 커밋먼트:")
    print(f"  전체 (32 bytes): {commitment_full}")
    print(f"  온체인 (4 bytes): {commitment_onchain}")
    
    # 3. Setup 데이터 구성
    setup_data = {
        "setup_uuid": setup_uuid,
        "network": "mutinynet",
        "name": "BTCFi Option Product Registration",
        
        # BitVMX 파라미터
        "max_amount_of_steps": 50000,
        "amount_of_bits_wrong_step_search": 1,
        
        # Funding 정보
        "funding_tx_id": funding_tx_id,
        "funding_index": funding_index,
        "funding_amount_of_satoshis": funding_amount,
        "secret_origin_of_funds": private_key or "d8a1e1224e63135765bde9dc8a2c8e403eee8be73d3589d58c5ddbf9dce3fdf4",
        
        # Prover/Verifier 주소 및 키
        "prover_destination_address": "tb1qt8rdur557nz338g3lekc6458pj0dl63c0s9904",
        "prover_signature_private_key": "0000000000000000000000000000000000000000000000000000000000000001",
        "prover_signature_public_key": "0279be667ef9dcbbac55a06295ce870b07029bfcdb2dce28d959f2815b16f81798",
        
        # Verifier (dummy for now)
        "verifier_signature_private_key": "0000000000000000000000000000000000000000000000000000000000000002",
        "verifier_signature_public_key": "02c6047f9441ed7d6d3045406e95c07cd85c778e4b8cef3ca7abac09b95c709ee5",
        
        # 입력 데이터: 커밋먼트만 (BitVMX 원칙)
        "amount_of_input_words": 1,
        "amount_of_public_inputs": 1,
        "list_of_public_inputs": [commitment_onchain],
        
        # 실행 파일 (이미 준비된 파일)
        "rom_commitment_file": "execution_files/instruction_commitment_option_registration.txt",
        "elf_file": "execution_files/btcfi_option_registration_v2.elf",
        
        # 수수료
        "step_fees_satoshis": 3000,
        "max_fee_allowed": 100000,
        
        # Verifier list (empty for single prover mode)
        "verifier_list": [],
        "prover_publishing_transaction_id": None
    }
    
    # 4. 디렉토리 생성 및 파일 저장
    prover_dir = f"prover_files/{setup_uuid}"
    os.makedirs(prover_dir, exist_ok=True)
    
    # 오프체인 옵션 데이터 저장
    option_file = f"{prover_dir}/option_product.json"
    with open(option_file, 'w') as f:
        json.dump({
            "product_data": option_product,
            "commitment": {
                "full": commitment_full,
                "onchain": commitment_onchain
            },
            "created_at": time.time()
        }, f, indent=2)
    
    # Setup 파일 저장
    setup_file = f"{prover_dir}/setup.json"
    with open(setup_file, 'w') as f:
        json.dump(setup_data, f, indent=2)
    
    print(f"\n✅ Setup 생성 완료!")
    print(f"  📁 Setup 파일: {setup_file}")
    print(f"  📁 옵션 데이터: {option_file}")
    
    # 5. 요약
    print(f"\n{'='*60}")
    print(f"요약")
    print(f"{'='*60}")
    print(f"Setup UUID: {setup_uuid}")
    print(f"Funding UTXO: {funding_tx_id}:{funding_index}")
    print(f"Amount: {funding_amount} sats")
    print(f"온체인 데이터: {commitment_onchain} (4 bytes)")
    print(f"ELF 파일: btcfi_option_registration_v2.elf")
    
    return setup_uuid


def verify_option_registration(setup_uuid: str) -> bool:
    """
    등록된 옵션 상품의 커밋먼트 검증
    """
    print(f"\n{'='*60}")
    print(f"옵션 상품 등록 검증")
    print(f"{'='*60}")
    
    # Setup 파일 읽기
    setup_file = f"prover_files/{setup_uuid}/setup.json"
    option_file = f"prover_files/{setup_uuid}/option_product.json"
    
    if not os.path.exists(setup_file) or not os.path.exists(option_file):
        print("❌ Setup 파일을 찾을 수 없습니다.")
        return False
    
    with open(setup_file, 'r') as f:
        setup_data = json.load(f)
    
    with open(option_file, 'r') as f:
        option_data = json.load(f)
    
    # 온체인 커밋먼트
    onchain_commitment = setup_data["list_of_public_inputs"][0]
    
    # 옵션 데이터로부터 커밋먼트 재계산
    product_json = json.dumps(option_data["product_data"], sort_keys=True, separators=(',', ':'))
    recalc_commitment = hashlib.sha256(product_json.encode()).hexdigest()[:8]
    
    # 검증
    is_valid = (onchain_commitment == recalc_commitment)
    
    print(f"온체인 커밋먼트: {onchain_commitment}")
    print(f"재계산 커밋먼트: {recalc_commitment}")
    print(f"검증 결과: {'✅ 성공' if is_valid else '❌ 실패'}")
    
    if is_valid:
        print(f"\n✅ 검증된 옵션 상품:")
        print(json.dumps(option_data["product_data"], indent=2))
    
    return is_valid


def main():
    """메인 실행 함수"""
    
    print("\n" + "🚀 "*20)
    print("BTCFi 옵션 상품 등록 시스템")
    print("BitVMX 원칙: 커밋먼트만 온체인")
    print("🚀 "*20)
    
    # 테스트용 funding TX (실제로는 이미 생성된 TX 사용)
    test_funding = {
        "tx_id": "f4d15aa4bf034ae7338e9ae7176f369dd77ae068bb527d96c233d39db0df80ce",
        "index": 0,
        "amount": 100000,
        "private_key": "d8a1e1224e63135765bde9dc8a2c8e403eee8be73d3589d58c5ddbf9dce3fdf4"
    }
    
    # 1. 옵션 상품 등록 Setup 생성
    setup_uuid = create_option_registration_setup(
        funding_tx_id=test_funding["tx_id"],
        funding_index=test_funding["index"],
        funding_amount=test_funding["amount"],
        private_key=test_funding["private_key"]
    )
    
    # 2. 검증
    print("\n" + "⚡ "*20)
    print("Challenge/Response 시뮬레이션")
    print("⚡ "*20)
    
    verify_option_registration(setup_uuid)
    
    # 3. 효율성 비교
    print(f"\n{'='*60}")
    print("📈 BitVMX 원칙의 효과")
    print(f"{'='*60}")
    
    # 옵션 데이터 크기
    with open(f"prover_files/{setup_uuid}/option_product.json", 'r') as f:
        option_data = json.load(f)
    
    full_data_size = len(json.dumps(option_data["product_data"]))
    onchain_size = 4  # 4 bytes commitment
    
    print(f"전체 옵션 데이터: {full_data_size} bytes (오프체인)")
    print(f"온체인 데이터: {onchain_size} bytes (커밋먼트만)")
    print(f"절감률: {((full_data_size - onchain_size) / full_data_size * 100):.1f}%")
    
    print("\n✅ 완료!")
    print("  - 옵션 상품이 등록되었습니다")
    print("  - 온체인에는 4바이트 커밋먼트만 저장")
    print("  - 실제 데이터는 오프체인에 안전하게 보관")
    print(f"  - Setup UUID: {setup_uuid}")


if __name__ == "__main__":
    main()