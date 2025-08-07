#!/usr/bin/env python3
"""BIP-143 서명 구현 - 실제 작동한 버전"""

import hashlib
import struct
from binascii import hexlify, unhexlify

def hash256(data):
    """Double SHA256"""
    return hashlib.sha256(hashlib.sha256(data).digest()).digest()

def create_bip143_sighash(tx_data):
    """
    BIP-143 sighash 생성 (실제 MutinyNet에서 작동)
    
    우리가 성공한 트랜잭션:
    TXID: 8c5b24941f67125780d753328fe4a2b57c6f26b938186f4ac0190574a308eaf8
    """
    
    # 1. nVersion (4 bytes, little-endian)
    version = struct.pack('<I', 2)
    
    # 2. hashPrevouts (32 bytes)
    prevout = unhexlify(tx_data['prevout_hash']) + struct.pack('<I', tx_data['prevout_index'])
    hash_prevouts = hash256(prevout)
    
    # 3. hashSequence (32 bytes)
    sequence = struct.pack('<I', 0xfffffffe)
    hash_sequence = hash256(sequence)
    
    # 4. Outpoint (32 bytes + 4 bytes)
    outpoint = unhexlify(tx_data['prevout_hash']) + struct.pack('<I', tx_data['prevout_index'])
    
    # 5. scriptCode
    script_pubkey = unhexlify(tx_data['script_pubkey'])
    script_code = bytes([len(script_pubkey)]) + script_pubkey
    
    # 6. Amount (8 bytes, little-endian)
    amount = struct.pack('<Q', tx_data['amount'])
    
    # 7. nSequence (4 bytes)
    n_sequence = struct.pack('<I', 0xfffffffe)
    
    # 8. hashOutputs (32 bytes)
    outputs = b''
    for output in tx_data['outputs']:
        outputs += struct.pack('<Q', output['amount'])
        script = unhexlify(output['script'])
        outputs += bytes([len(script)]) + script
    hash_outputs = hash256(outputs)
    
    # 9. nLocktime (4 bytes)
    locktime = struct.pack('<I', tx_data.get('locktime', 0))
    
    # 10. sighash type (4 bytes)
    sighash_type = struct.pack('<I', 1)  # SIGHASH_ALL
    
    # Preimage 조합
    preimage = (
        version +
        hash_prevouts +
        hash_sequence +
        outpoint +
        script_code +
        amount +
        n_sequence +
        hash_outputs +
        locktime +
        sighash_type
    )
    
    # Double SHA256
    sighash = hash256(preimage)
    
    return sighash

def sign_transaction(private_key_hex, tx_data):
    """
    트랜잭션 서명
    
    Args:
        private_key_hex: 비밀키 (hex)
        tx_data: 트랜잭션 데이터
    
    Returns:
        서명된 트랜잭션 (hex)
    """
    import ecdsa
    from ecdsa.util import sigencode_der_canonize
    
    # Sighash 생성
    sighash = create_bip143_sighash(tx_data)
    
    # 비밀키로 서명
    private_key_bytes = unhexlify(private_key_hex)
    signing_key = ecdsa.SigningKey.from_string(private_key_bytes, curve=ecdsa.SECP256k1)
    signature = signing_key.sign_digest(sighash, sigencode=sigencode_der_canonize)
    
    # SIGHASH_ALL 추가
    signature_with_sighash = signature + b'\x01'
    
    return hexlify(signature_with_sighash).decode()

# 실제 사용된 트랜잭션 데이터
SUCCESSFUL_TX_DATA = {
    'prevout_hash': 'fb5ecd9da1e6aac3ca27afef6491e3e296c1da60f79e3069aabad8d2a66e00d4',
    'prevout_index': 0,
    'amount': 100000,
    'script_pubkey': '1976a914c8c0ab383fb3dd9f03e3ea2d6e86ab895a6fbab788ac',
    'outputs': [
        {
            'amount': 95000,
            'script': '001407001a1c181b52ef255bbfd5810b0d2f64ca5a49'
        },
        {
            'amount': 4000,
            'script': '001464c016ac4135d8f8dc07e51165a8b689cd59769a'
        }
    ]
}

if __name__ == "__main__":
    print("BIP-143 서명 도구")
    print("=" * 50)
    print(f"성공한 트랜잭션: 8c5b24941f67125780d753328fe4a2b57c6f26b938186f4ac0190574a308eaf8")
    print(f"MutinyNet 확인: https://mutinynet.com/tx/8c5b24941f67125780d753328fe4a2b57c6f26b938186f4ac0190574a308eaf8")