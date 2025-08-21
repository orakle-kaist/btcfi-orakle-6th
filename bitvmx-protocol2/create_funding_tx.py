#!/usr/bin/env python3
"""
BitVMX Funding Transaction 생성 (Mutinynet)
"""

import requests
import json
import hashlib
import time

# Mutinynet API
MUTINYNET_API = "https://mutinynet.com/api"

def get_utxos(address):
    """주소의 UTXO 조회"""
    url = f"{MUTINYNET_API}/address/{address}/utxo"
    response = requests.get(url)
    if response.status_code == 200:
        return response.json()
    return []

def create_funding_transaction():
    """Funding 트랜잭션 정보 준비"""
    
    address = "tb1qt8rdur557nz338g3lekc6458pj0dl63c0s9904"
    private_key = "d8a1e1224e63135765bde9dc8a2c8e403eee8be73d3589d58c5ddbf9dce3fdf4"
    
    print(f"📍 주소: {address}")
    
    # UTXO 조회
    utxos = get_utxos(address)
    if not utxos:
        print("❌ 사용 가능한 UTXO가 없습니다.")
        return None
    
    print(f"✅ 사용 가능한 UTXO: {len(utxos)}개")
    
    # 첫 번째 UTXO 사용
    utxo = utxos[0]
    
    funding_info = {
        "txid": utxo["txid"],
        "vout": utxo["vout"],
        "value": utxo["value"],
        "private_key": private_key,
        "address": address
    }
    
    print(f"\n📊 Funding UTXO:")
    print(f"  - TXID: {funding_info['txid']}")
    print(f"  - Output Index: {funding_info['vout']}")
    print(f"  - Value: {funding_info['value']} sats")
    
    return funding_info

def create_bitvmx_setup(funding_info):
    """BitVMX Setup 생성"""
    
    print("\n🚀 BitVMX Setup 생성 중...")
    
    # Setup 요청 데이터
    setup_data = {
        "network": "mutinynet",
        "max_amount_of_steps": 1000,  # 옵션 등록은 단순하므로 1000 스텝
        "amount_of_bits_wrong_step_search": 3,  # 8개 구간으로 나눔
        "funding_tx_id": funding_info["txid"],
        "funding_index": funding_info["vout"],
        "secret_origin_of_funds": funding_info["private_key"],
        "prover_destination_address": funding_info["address"],
        "prover_signature_private_key": funding_info["private_key"],
        "prover_signature_public_key": "0279be667ef9dcbbac55a06295ce870b07029bfcdb2dce28d959f2815b16f81798",
        "amount_of_input_words": 5  # 옵션 데이터 입력 (20 bytes = 5 words)
    }
    
    # Prover API 호출
    try:
        response = requests.post(
            "http://localhost:8001/api/v1/setup",
            json=setup_data,
            headers={"Content-Type": "application/json"},
            timeout=30
        )
        
        if response.status_code == 200:
            result = response.json()
            print("✅ Setup 생성 성공!")
            print(f"  - Setup UUID: {result.get('setup_uuid')}")
            return result
        else:
            print(f"❌ Setup 생성 실패: {response.status_code}")
            print(f"  응답: {response.text}")
            return None
            
    except Exception as e:
        print(f"❌ 에러 발생: {e}")
        return None

def main():
    print("=" * 60)
    print("BitVMX 옵션 등록 - Funding Transaction 생성")
    print("=" * 60)
    
    # 1. Funding 트랜잭션 정보 준비
    funding_info = create_funding_transaction()
    if not funding_info:
        print("Funding 트랜잭션 생성 실패")
        return
    
    # 2. BitVMX Setup 생성
    setup_result = create_bitvmx_setup(funding_info)
    
    if setup_result:
        # 결과 저장
        with open("bitvmx_setup.json", "w") as f:
            json.dump(setup_result, f, indent=2)
        print(f"\n💾 Setup 정보 저장: bitvmx_setup.json")
        
        print("\n다음 단계:")
        print("1. Verifier와 Challenge-Response 프로토콜 실행")
        print("2. 옵션 등록 트랜잭션 Mutinynet에 브로드캐스트")

if __name__ == "__main__":
    main()