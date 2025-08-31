#!/usr/bin/env python3
"""
Fix Trigger Protocol TX signature with correct amount
"""
import sys
sys.path.insert(0, '/bitvmx-backend')

from bitcoinutils.setup import setup
from bitcoinutils.keys import PrivateKey
from bitcoinutils.script import Script
from bitcoinutils.constants import TAPROOT_SIGHASH_ALL
from bitcoinutils.transactions import Transaction, TxInput, TxOutput, TxWitnessInput
import json
import binascii

setup('testnet')

def fix_trigger_signature():
    setup_uuid = '60f1041f-1a8f-4e17-8181-44208f11b71c'
    
    # 실제 Hash Result TX output amount
    ACTUAL_AMOUNT = 149995912  # 이것이 정확한 값!
    
    # Private key
    privkey_hex = "d8a1e1224e63135765bde9dc8a2c8e403eee8be73d3589d58c5ddbf9dce3fdf4"
    privkey = PrivateKey(b=binascii.unhexlify(privkey_hex))
    
    print("🔧 Trigger Protocol TX 서명 수정")
    print("=" * 50)
    
    # 기존 트랜잭션 읽기
    with open(f'/bitvmx-backend/prover_files/{setup_uuid}/signed_transactions.json', 'r') as f:
        txs = json.load(f)
    
    # Trigger TX 파싱
    trigger_hex = txs['trigger_protocol_tx']
    trigger_tx = Transaction.from_raw(trigger_hex)
    
    print(f"✅ 기존 Trigger TX 로드됨")
    print(f"   Input: Hash Result TX output")
    print(f"   사용할 Amount: {ACTUAL_AMOUNT:,} sats")
    
    # 서명 재생성
    try:
        # Taproot address와 script 가져오기
        # 여기서는 단순히 key-path spend로 시도
        from bitcoinutils.keys import P2trAddress
        
        # Taproot 주소 (Hash Result TX의 output 주소)
        taproot_addr = "tb1pr03uq5xl0n6k30mlj5t8h3hh6n5ag7fkm8gfaa0v6w54ne9nr7lswnghy5"
        
        # Script pubkey
        script_pubkey_hex = "51201be1c0509e7cf5531fbf92947bc6f7d4e9d47936d9c84f75d66b8954e653f3f3"
        script_pubkey = Script.from_raw(script_pubkey_hex)
        
        # 새 서명 생성 (key-path spend)
        sig = privkey.sign_taproot_input(
            trigger_tx,
            0,  # input index
            [script_pubkey],  # prevout script
            [ACTUAL_AMOUNT],  # 정확한 amount!
            script_path=False,  # key-path로 시도
            tweak=True,
            sighash=TAPROOT_SIGHASH_ALL
        )
        
        # Witness 업데이트
        trigger_tx.witnesses = [TxWitnessInput([sig])]
        
        # 새 hex 생성
        new_trigger_hex = trigger_tx.serialize()
        
        print(f"\n✅ 새 서명 생성 완료")
        print(f"   Witness 포함: {'0001' in new_trigger_hex[8:12]}")
        print(f"   크기: {len(new_trigger_hex)//2} bytes")
        
        # 저장
        txs['trigger_protocol_tx'] = new_trigger_hex
        with open(f'/bitvmx-backend/prover_files/{setup_uuid}/signed_transactions_fixed.json', 'w') as f:
            json.dump(txs, f, indent=2)
        
        print(f"\n💾 signed_transactions_fixed.json 저장됨")
        
        return new_trigger_hex
        
    except Exception as e:
        print(f"\n❌ 에러: {e}")
        import traceback
        traceback.print_exc()
        return None

if __name__ == "__main__":
    new_hex = fix_trigger_signature()
    
    if new_hex:
        # 브로드캐스트 시도
        import requests
        print("\n📡 브로드캐스트 시도...")
        response = requests.post(
            "https://mutinynet.com/api/tx",
            data=new_hex,
            headers={'Content-Type': 'text/plain'},
            timeout=10
        )
        
        if response.status_code == 200:
            print(f"✅ 성공! TXID: {response.text.strip()}")
        else:
            print(f"❌ 실패: {response.text[:200]}")