#!/usr/bin/env python3
"""
Recover funds from Hash Result TX output (Taproot) to simple P2WPKH
Since Trigger TX is failing due to complex BitVMX script-path signing
"""
import sys
sys.path.insert(0, '/bitvmx-backend')

from bitcoinutils.setup import setup
from bitcoinutils.keys import PrivateKey, P2wpkhAddress
from bitcoinutils.transactions import Transaction, TxInput, TxOutput, TxWitnessInput
from bitcoinutils.script import Script
import binascii
import requests

setup('testnet')

def recover_funds():
    print("💰 Hash Result TX Output 자금 회수")
    print("=" * 50)
    
    # Hash Result TX output 정보
    prev_txid = "5b2c13fdb0695b6ab2170fbaeee82b6a09b490b1a23d4dc982543c4be025ca68"
    prev_vout = 0
    prev_amount = 149995912  # 정확한 amount
    
    # Private key
    privkey_hex = "d8a1e1224e63135765bde9dc8a2c8e403eee8be73d3589d58c5ddbf9dce3fdf4"
    privkey = PrivateKey(b=binascii.unhexlify(privkey_hex))
    pubkey = privkey.get_public_key()
    
    # 대상 주소 (간단한 P2WPKH)
    dest_address = P2wpkhAddress.from_witness_program(pubkey.to_hash160())
    
    print(f"Input: {prev_txid[:16]}...")
    print(f"Amount: {prev_amount:,} sats")
    print(f"Output: {dest_address.to_string()}")
    
    # 트랜잭션 생성
    tx_in = TxInput(prev_txid, prev_vout)
    
    # Fee
    fee = 1000
    tx_out = TxOutput(prev_amount - fee, dest_address.to_script_pub_key())
    
    # Transaction with witness
    tx = Transaction([tx_in], [tx_out], has_segwit=True)
    
    # Taproot key-path spend 서명
    # Hash Result TX output은 Taproot이므로 key-path로 시도
    try:
        # Taproot 주소의 internal key로 서명
        sig = privkey.sign_taproot_input(
            tx, 
            0,
            [Script.from_raw("51201be1c0509e7cf5531fbf92947bc6f7d4e9d47936d9c84f75d66b8954e653f3f3")],  # prev script pubkey
            [prev_amount],
            script_path=False,  # key-path spend
            tweak=True,  # key tweak 적용
            sighash=0  # SIGHASH_DEFAULT
        )
        
        # Witness 설정
        tx.witnesses = [TxWitnessInput([sig])]
        
        # Serialize
        tx_hex = tx.serialize()
        
        print(f"\n✅ 트랜잭션 생성 완료")
        print(f"   Size: {len(tx_hex)//2} bytes")
        print(f"   Witness: {'0001' in tx_hex[8:12]}")
        
        return tx_hex
        
    except Exception as e:
        print(f"\n❌ 서명 실패: {e}")
        import traceback
        traceback.print_exc()
        return None

if __name__ == "__main__":
    tx_hex = recover_funds()
    
    if tx_hex:
        print("\n📡 브로드캐스트 시도...")
        response = requests.post(
            "https://mutinynet.com/api/tx",
            data=tx_hex,
            headers={'Content-Type': 'text/plain'},
            timeout=10
        )
        
        if response.status_code == 200:
            txid = response.text.strip()
            print(f"✅ 성공! TXID: {txid}")
            print(f"   Explorer: https://mutinynet.com/tx/{txid}")
        else:
            print(f"❌ 실패: {response.text[:200]}")
            