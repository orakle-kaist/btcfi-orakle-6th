#!/usr/bin/env python3
"""
BTCFi 옵션 상품 등록 트랜잭션 생성
"""
import json
import hashlib
from bitcoinutils.setup import setup
from bitcoinutils.transactions import Transaction, TxInput, TxOutput, TxWitnessInput
from bitcoinutils.keys import PrivateKey, P2wpkhAddress
from bitcoinutils.script import Script
from bitcoinutils.constants import SIGHASH_ALL

# Mutinynet 설정
setup('testnet')

# 우리 주소 정보
OUR_ADDRESS = "tb1qt8rdur557nz338g3lekc6458pj0dl63c0s9904"
PRIVATE_KEY = "d8a1e1224e63135765bde9dc8a2c8e403eee8be73d3589d58c5ddbf9dce3fdf4"

def create_option_registration_tx():
    """옵션 상품 등록 트랜잭션 생성"""
    
    # 최신 UTXO (이전 트랜잭션의 출력)
    # 이 값은 실제로 확인해야 함
    print("Creating option product registration transaction...")
    
    # 옵션 메타데이터 (간단한 버전)
    option_data = {
        "type": "CALL",
        "strike": 50000,
        "expiry": "2025-01-31"
    }
    
    # JSON을 바이트로 변환하고 해시
    option_json = json.dumps(option_data, separators=(',', ':'))
    option_hash = hashlib.sha256(option_json.encode()).digest()[:20]  # 20 bytes
    
    print(f"Option data: {option_json}")
    print(f"Option hash (20 bytes): {option_hash.hex()}")
    
    # OP_RETURN 스크립트 생성
    op_return_data = b"BTCFI_OPT" + option_hash
    op_return_script = Script(['OP_RETURN', op_return_data.hex()])
    
    print(f"OP_RETURN script: {op_return_script}")
    print(f"OP_RETURN data size: {len(op_return_data)} bytes")
    
    # 트랜잭션 구조 예시
    print("\n=== Transaction Structure ===")
    print("Input: Previous BitVMX transaction output")
    print("Output 1: OP_RETURN with option metadata")
    print("Output 2: Change back to our address")
    print("\nThis transaction would register the option product on-chain")
    print("The OP_RETURN contains a hash of the option parameters")
    
    return option_hash.hex()

if __name__ == "__main__":
    option_hash = create_option_registration_tx()
    print(f"\n✅ Option product hash: {option_hash}")
    print("This hash can be used to verify the option parameters later")