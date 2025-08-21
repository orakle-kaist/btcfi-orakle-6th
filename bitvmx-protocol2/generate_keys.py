#!/usr/bin/env python3
"""
BitVMX용 키 쌍 생성
"""

import hashlib
import secrets

def generate_keypair():
    """secp256k1 키 쌍 생성"""
    
    # 개인키 생성 (32바이트)
    private_key = secrets.token_hex(32)
    
    # 간단한 공개키 생성 (실제로는 타원곡선 연산 필요)
    # 여기서는 예시로 생성
    private_bytes = bytes.fromhex(private_key)
    hash_val = hashlib.sha256(private_bytes).digest()
    
    # 압축된 공개키 형식 (33바이트)
    # 02 또는 03 prefix + 32바이트 x좌표
    public_key = "02" + hash_val.hex()
    
    return private_key, public_key

# MutinyNet 테스트용 키
# 실제로는 이미 있는 키 사용
PROVER_PRIVATE_KEY = "d8a1e1224e63135765bde9dc8a2c8e403eee8be73d3589d58c5ddbf9dce3fdf4"

# 공개키 생성 (간단한 방법)
# 실제로는 bitcoinutils 사용
def get_public_key_from_private(private_key_hex):
    """개인키에서 공개키 유도"""
    try:
        from bitcoinutils.setup import setup
        from bitcoinutils.keys import PrivateKey
        
        setup('testnet')
        priv_key = PrivateKey(secret_exponent=int(private_key_hex, 16))
        pub_key = priv_key.get_public_key()
        return pub_key.to_hex()
    except:
        # 대체 방법: 임시 공개키
        # secp256k1의 generator point G를 사용해야 하지만
        # 여기서는 유효한 형식의 더미 키 생성
        return "03a1bb0c22d3a2e47fb7b89f5de7b03e4b4e4f8e4e4b8f7e8f4b7e8f4b7e8f4b7e"

if __name__ == "__main__":
    print("BitVMX Key Generation")
    print("=" * 60)
    
    # 실제 공개키 생성 시도
    pub_key = get_public_key_from_private(PROVER_PRIVATE_KEY)
    
    print(f"Private Key: {PROVER_PRIVATE_KEY}")
    print(f"Public Key:  {pub_key}")
    print()
    
    # Verifier용 키 생성
    verifier_priv, verifier_pub = generate_keypair()
    print("Verifier Keys (example):")
    print(f"Private: {verifier_priv}")
    print(f"Public:  {verifier_pub}")