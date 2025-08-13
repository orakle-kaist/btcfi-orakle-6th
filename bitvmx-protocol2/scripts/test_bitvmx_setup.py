#!/usr/bin/env python3
"""
BitVMX Setup 테스트 스크립트
실제 Challenge-Response 사이클 실행
"""

import requests
import json
import time
import sys

# API 엔드포인트
PROVER_URL = "http://localhost:8081"  # Prover 포트 8081로 수정
VERIFIER_URL = "http://localhost:8080"

def create_setup():
    """Setup 생성 및 초기화"""
    print("🚀 BitVMX Setup 생성 중...")
    
    # 실제 funding 트랜잭션 정보 (이미 브로드캐스트된 트랜잭션)
    # Setup 생성 요청 - 모든 필수 파라미터 포함
    response = requests.post(
        f"{PROVER_URL}/api/v1/setup",
        headers={"Content-Type": "application/json"},
        json={
            "network": "mutinynet",
            "max_amount_of_steps": 100,
            "amount_of_bits_wrong_step_search": 3,
            "funding_tx_id": "2e0e1d328d59a0eba058d0da24e5b2b8e7b7b9c8184e96b0c9b244ee623e36fc",
            "funding_index": 1,
            "secret_origin_of_funds": "d8a1e1224e63135765bde9dc8a2c8e403eee8be73d3589d58c5ddbf9dce3fdf4",
            "prover_destination_address": "tb1qt8rdur557nz338g3lekc6458pj0dl63c0s9904",
            "prover_signature_private_key": "d8a1e1224e63135765bde9dc8a2c8e403eee8be73d3589d58c5ddbf9dce3fdf4",
            "prover_signature_public_key": "0279be667ef9dcbbac55a06295ce870b07029bfcdb2dce28d959f2815b16f81798",
            "amount_of_input_words": 2
        }
    )
    
    if response.status_code == 200:
        setup_data = response.json()
        setup_uuid = setup_data.get("setup_uuid")
        print(f"✅ Setup 생성 완료: {setup_uuid}")
        return setup_uuid
    else:
        print(f"❌ Setup 생성 실패: {response.status_code}")
        print(response.text)
        return None

def trigger_challenge_response(setup_uuid):
    """Challenge-Response 사이클 실행"""
    print(f"\n🔄 Challenge-Response 사이클 시작...")
    
    # Next step 트리거
    response = requests.post(
        f"{PROVER_URL}/api/v1/next_step",
        headers={"Content-Type": "application/json"},
        json={"setup_uuid": setup_uuid}
    )
    
    if response.status_code == 200:
        result = response.json()
        print(f"✅ Next step 실행 완료")
        print(f"   Transaction ID: {result.get('txid', 'N/A')}")
        print(f"   Step Type: {result.get('step_type', 'N/A')}")
        return result
    else:
        print(f"❌ Next step 실패: {response.status_code}")
        print(response.text)
        return None

def check_verifier_status(setup_uuid):
    """Verifier 상태 확인"""
    print(f"\n🔍 Verifier 상태 확인...")
    
    response = requests.get(
        f"{VERIFIER_URL}/api/v1/status/{setup_uuid}",
        headers={"Content-Type": "application/json"}
    )
    
    if response.status_code == 200:
        status = response.json()
        print(f"✅ Verifier 상태:")
        print(f"   Status: {status.get('status', 'N/A')}")
        print(f"   Current Step: {status.get('current_step', 'N/A')}")
        return status
    else:
        print(f"⚠️  Verifier 상태 확인 실패: {response.status_code}")
        return None

def main():
    """메인 실행 함수"""
    print("="*60)
    print("BitVMX Challenge-Response 사이클 테스트")
    print("="*60)
    
    # 1. Setup 생성
    setup_uuid = create_setup()
    if not setup_uuid:
        print("Setup 생성 실패. 종료합니다.")
        sys.exit(1)
    
    # 2. 잠시 대기 (Setup 초기화 완료 대기)
    print("\n⏳ Setup 초기화 대기 중... (5초)")
    time.sleep(5)
    
    # 3. Verifier 상태 확인
    check_verifier_status(setup_uuid)
    
    # 4. Challenge-Response 사이클 실행
    for i in range(3):  # 최대 3번 시도
        print(f"\n📍 Step {i+1}/3")
        result = trigger_challenge_response(setup_uuid)
        
        if result and result.get("status") == "completed":
            print("\n🎉 Challenge-Response 사이클 완료!")
            print(f"   최종 트랜잭션: {result.get('final_txid')}")
            break
        
        time.sleep(3)  # 다음 스텝 전 대기
    
    # 5. 최종 상태 확인
    print("\n📊 최종 상태:")
    final_status = check_verifier_status(setup_uuid)
    
    if final_status:
        print(f"\n🔗 BitVMX Explorer에서 확인:")
        print(f"   https://bitvmx-explorer.com/protocol?network=mutinynet&txid={setup_uuid}")
    
    print("\n" + "="*60)
    print("테스트 완료")
    print("="*60)

if __name__ == "__main__":
    main()