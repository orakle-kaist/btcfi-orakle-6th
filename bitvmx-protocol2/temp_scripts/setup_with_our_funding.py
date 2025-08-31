#!/usr/bin/env python3
"""
BitVMX Setup using our existing funding
tb1qt8rdur557nz338g3lekc6458pj0dl63c0s9904 주소의 자금 사용
"""
import json
import requests
import time

def main():
    API_BASE = "http://localhost:8081"
    
    # 우리 주소와 자금 정보
    setup_input = {
        # 기본 파라미터
        "max_amount_of_steps": 10,
        "amount_of_bits_wrong_step_search": 1,
        "amount_of_input_words": 1,
        
        # 우리 funding 정보 (새로운 UTXO)
        "funding_tx_id": "00c57240bf32c053bcc6f2ca37a45609064051ed7c10023a99af670db9beb24f",
        "funding_index": 0,
        "funding_amount_of_satoshis": 149998922,
        "secret_origin_of_funds": "d8a1e1224e63135765bde9dc8a2c8e403eee8be73d3589d58c5ddbf9dce3fdf4",
        "prover_destination_address": "tb1qt8rdur557nz338g3lekc6458pj0dl63c0s9904",
        
        # Prover 키 (우리 주소의 키)
        "prover_signature_private_key": "d8a1e1224e63135765bde9dc8a2c8e403eee8be73d3589d58c5ddbf9dce3fdf4",
        "prover_signature_public_key": "03bf751f0d2d22e6f0163c9acaa14ae04e6e1a004cb4a24d893c1f86314e79d5de",
        
        # Verifier 파라미터 (더미)
        "verifier_signature_private_key": "cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc",
        "verifier_signature_public_key": "03999269c93633303d8f5173bc017e5046f933053c59ebdde6bb3dd8d8de0528ba",
        "verifier_destination_address": "tb1qyvsy6ypssxmqmdzthzua3qwupkey90p3cdeuxx",
        
        # 수수료
        "step_fees_satoshis": 1000,
        "max_fee_allowed": 10000,
        
        # Verifier 서비스 설정
        "verifier_list": ["http://verifier-backend:80"]
    }
    
    print("=" * 60)
    print("BITVMX SETUP - 우리 주소 사용")
    print("=" * 60)
    print(f"\n💰 우리 주소: {setup_input['prover_destination_address']}")
    print(f"📊 Funding TX: {setup_input['funding_tx_id'][:16]}...")
    print(f"💵 금액: {setup_input['funding_amount_of_satoshis']:,} sats")
    print(f"🔑 Private key: {setup_input['secret_origin_of_funds'][:8]}...")
    
    try:
        # Health check
        health = requests.get(f"{API_BASE}/healthcheck", timeout=2)
        print(f"\n✅ Prover service: {health.json()}")
        
        # Setup 호출
        print("\n📡 Calling /api/v1/setup...")
        response = requests.post(
            f"{API_BASE}/api/v1/setup",
            json=setup_input,
            timeout=120
        )
        
        if response.status_code == 200:
            result = response.json()
            setup_uuid = result.get('setup_uuid')
            print(f"\n🎉 SUCCESS!")
            print(f"   Setup UUID: {setup_uuid}")
            
            # 생성된 파일 확인
            import os
            prover_dir = f"prover_files/{setup_uuid}"
            if os.path.exists(prover_dir):
                files = os.listdir(prover_dir)
                print(f"\n📂 Generated files:")
                for f in files:
                    print(f"   - {f}")
                
                # signed_transactions 확인
                signed_file = f"{prover_dir}/signed_transactions.json"
                if os.path.exists(signed_file):
                    with open(signed_file, 'r') as f:
                        signed = json.load(f)
                        print(f"\n🔏 Signed transactions:")
                        for key in signed.keys():
                            if isinstance(signed[key], list):
                                print(f"   - {key}: {len(signed[key])} txs")
                            elif isinstance(signed[key], str):
                                print(f"   - {key}: {len(signed[key])} bytes")
            
            return setup_uuid
        else:
            print(f"\n❌ Failed: {response.status_code}")
            print(f"Response: {response.text[:500]}")
            
    except Exception as e:
        print(f"\n❌ Error: {e}")
    
    return None

if __name__ == "__main__":
    setup_uuid = main()
    if setup_uuid:
        print(f"\n✨ Setup 생성 완료!")
        print(f"   UUID: {setup_uuid}")
        print(f"   다음 단계: prover transaction 브로드캐스트")