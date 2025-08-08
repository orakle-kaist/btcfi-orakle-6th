#!/usr/bin/env python3
"""
실제 MutinyNet 트랜잭션 생성 - 올바른 witness 구조 구현
"""

import hashlib
import struct
import time
import json
import requests
from binascii import hexlify, unhexlify
import ecdsa
from ecdsa.util import sigencode_der_canonize

def hash256(data):
    """Double SHA256"""
    return hashlib.sha256(hashlib.sha256(data).digest()).digest()

def hash160(data):
    """SHA256 + RIPEMD160"""
    import hashlib
    sha = hashlib.sha256(data).digest()
    ripemd = hashlib.new('ripemd160')
    ripemd.update(sha)
    return ripemd.digest()

def create_option_registration_tx():
    """
    BitVMX 기반 옵션 등록 트랜잭션 생성
    """
    
    # 우리가 실제로 소유한 UTXO
    UTXO = {
        'txid': 'a3948d735b2a2a884b0e9a3d4a9aeefc3b1cda48c00307fca90b8c04666147c3',
        'vout': 1,
        'amount': 100000,  # sats
        'address': 'tb1qt8rdur557nz338g3lekc6458pj0dl63c0s9904'
    }
    
    # 우리의 프라이빗 키 (이전에 성공한 것)
    PRIVATE_KEY = 'd8a1e1224e63135765bde9dc8a2c8e403eee8be73d3589d58c5ddbf9dce3fdf4'
    
    print("\n" + "="*60)
    print("🚀 BitVMX 옵션 등록 트랜잭션 생성")
    print("="*60)
    
    # 옵션 데이터
    option_data = {
        'type': 'CALL',
        'strike': 122000,  # $122K
        'expiry': int(time.time()) + (3 * 24 * 60 * 60),  # 3일 후
        'unit': 0.01,  # 0.01 BTC
        'id': f'btcfi_opt_{int(time.time())}'
    }
    
    # BitVMX 해시 (실제 에뮬레이터 실행 결과)
    bitvmx_hash = '9cc626dfe6cd76df6a70a523fe69adc21e4f8a11e9cf4cd3ed259976275f6317'
    
    # OP_RETURN 데이터 생성
    op_return_json = json.dumps({
        'bvmx': bitvmx_hash[:16],  # BitVMX hash 축약
        't': option_data['type'][0],
        's': option_data['strike'],
        'e': option_data['expiry'],
        'u': option_data['unit']
    }, separators=(',', ':'))
    
    op_return_data = op_return_json.encode()[:75]
    
    print(f"  UTXO: {UTXO['txid'][:16]}...:{UTXO['vout']}")
    print(f"  금액: {UTXO['amount']:,} sats")
    print(f"  주소: {UTXO['address']}")
    print(f"  옵션: {option_data['type']} ${option_data['strike']:,}")
    print(f"  BitVMX: {bitvmx_hash[:16]}...")
    print(f"  OP_RETURN: {op_return_data.decode()}")
    
    # 트랜잭션 생성
    fee = 500  # 수수료
    change_amount = UTXO['amount'] - fee
    
    tx_hex = create_segwit_transaction(
        UTXO,
        op_return_data,
        change_amount,
        PRIVATE_KEY
    )
    
    return tx_hex, option_data

def create_segwit_transaction(utxo, op_return_data, change_amount, private_key_hex):
    """
    SegWit (P2WPKH) 트랜잭션 생성
    """
    
    # 프라이빗 키에서 공개키 생성
    private_key_bytes = unhexlify(private_key_hex)
    signing_key = ecdsa.SigningKey.from_string(private_key_bytes, curve=ecdsa.SECP256k1)
    verifying_key = signing_key.get_verifying_key()
    
    # Compressed public key
    x = verifying_key.pubkey.point.x()
    y = verifying_key.pubkey.point.y()
    prefix = b'\x02' if y % 2 == 0 else b'\x03'
    public_key = prefix + x.to_bytes(32, 'big')
    
    # 공개키 해시 (witness program)
    pubkey_hash = hash160(public_key)
    
    print(f"\n  공개키: {hexlify(public_key).decode()[:16]}...")
    print(f"  PubkeyHash: {hexlify(pubkey_hash).decode()}")
    
    # 트랜잭션 구조
    version = struct.pack('<I', 2)
    marker = b'\x00'  # witness marker
    flag = b'\x01'    # witness flag
    
    # Input
    tx_in_count = b'\x01'
    tx_in = unhexlify(utxo['txid'])[::-1]  # little-endian
    tx_in += struct.pack('<I', utxo['vout'])
    tx_in += b'\x00'  # scriptSig 길이 (witness에서 처리)
    tx_in += struct.pack('<I', 0xfffffffe)  # sequence
    
    # Output 개수
    tx_out_count = b'\x02'
    
    # Output 1: OP_RETURN
    tx_out1 = struct.pack('<Q', 0)  # 0 sats
    op_return_script = b'\x6a' + bytes([len(op_return_data)]) + op_return_data
    tx_out1 += bytes([len(op_return_script)]) + op_return_script
    
    # Output 2: Change (자신에게)
    tx_out2 = struct.pack('<Q', change_amount)
    # P2WPKH script: OP_0 <20-byte-key-hash>
    change_script = b'\x00\x14' + pubkey_hash
    tx_out2 += bytes([len(change_script)]) + change_script
    
    # Witness를 위한 sighash 생성 (BIP-143)
    sighash = create_bip143_sighash(
        utxo,
        [(0, op_return_script), (change_amount, change_script)],
        pubkey_hash
    )
    
    # 서명 생성
    signature = signing_key.sign_digest(sighash, sigencode=sigencode_der_canonize)
    signature_with_sighash = signature + b'\x01'  # SIGHASH_ALL
    
    # Witness structure
    witness = b'\x02'  # 2 stack items
    witness += bytes([len(signature_with_sighash)]) + signature_with_sighash
    witness += bytes([len(public_key)]) + public_key
    
    # Locktime
    locktime = struct.pack('<I', 0)
    
    # 전체 트랜잭션 조합 (witness 포함)
    raw_tx = (
        version +
        marker + flag +  # witness marker/flag
        tx_in_count +
        tx_in +
        tx_out_count +
        tx_out1 +
        tx_out2 +
        witness +  # witness data
        locktime
    )
    
    # TXID 계산 (witness 제외)
    txid_preimage = (
        version +
        tx_in_count +
        tx_in +
        tx_out_count +
        tx_out1 +
        tx_out2 +
        locktime
    )
    txid = hexlify(hash256(txid_preimage)[::-1]).decode()
    
    tx_hex = hexlify(raw_tx).decode()
    
    print(f"\n✅ 트랜잭션 생성 완료!")
    print(f"  TXID: {txid}")
    print(f"  크기: {len(raw_tx)} bytes")
    print(f"  Witness: {len(witness)} bytes")
    print(f"  수수료: 500 sats")
    
    return tx_hex

def create_bip143_sighash(utxo, outputs, pubkey_hash):
    """
    BIP-143 sighash 생성 (P2WPKH)
    """
    
    # 1. nVersion
    version = struct.pack('<I', 2)
    
    # 2. hashPrevouts
    prevout = unhexlify(utxo['txid'])[::-1] + struct.pack('<I', utxo['vout'])
    hash_prevouts = hash256(prevout)
    
    # 3. hashSequence
    sequence = struct.pack('<I', 0xfffffffe)
    hash_sequence = hash256(sequence)
    
    # 4. Outpoint
    outpoint = unhexlify(utxo['txid'])[::-1] + struct.pack('<I', utxo['vout'])
    
    # 5. scriptCode (P2WPKH: OP_DUP OP_HASH160 <pubkey_hash> OP_EQUALVERIFY OP_CHECKSIG)
    script_code = b'\x19\x76\xa9\x14' + pubkey_hash + b'\x88\xac'
    
    # 6. Amount
    amount = struct.pack('<Q', utxo['amount'])
    
    # 7. nSequence
    n_sequence = struct.pack('<I', 0xfffffffe)
    
    # 8. hashOutputs
    outputs_data = b''
    for out_amount, out_script in outputs:
        outputs_data += struct.pack('<Q', out_amount)
        outputs_data += bytes([len(out_script)]) + out_script
    hash_outputs = hash256(outputs_data)
    
    # 9. nLocktime
    locktime = struct.pack('<I', 0)
    
    # 10. sighash type
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
    
    return hash256(preimage)

def broadcast_transaction(tx_hex):
    """
    트랜잭션 브로드캐스트
    """
    
    print("\n📡 트랜잭션 브로드캐스트 시도...")
    
    # MutinyNet API
    try:
        response = requests.post(
            "https://mutinynet.com/api/tx",
            data=tx_hex,
            headers={"Content-Type": "text/plain"},
            timeout=10
        )
        
        if response.status_code == 200:
            txid = response.text.strip()
            print("✅ 브로드캐스트 성공!")
            print(f"  TXID: {txid}")
            print(f"  Explorer: https://mutinynet.com/tx/{txid}")
            print(f"  BitVMX Explorer: https://bitvmx-explorer.com/protocol?network=mutinynet&txid={txid}")
            return True
        else:
            print(f"❌ 브로드캐스트 실패: {response.status_code}")
            print(f"  응답: {response.text}")
            
            # 디버깅을 위한 추가 정보
            if "witness" in response.text.lower():
                print("\n⚠️ Witness 구조 문제 감지")
                print("  P2WPKH witness는 정확히 2개 아이템 필요:")
                print("  1. 서명 (DER + SIGHASH_ALL)")
                print("  2. 압축된 공개키 (33 bytes)")
    except Exception as e:
        print(f"❌ 오류: {e}")
    
    return False

def main():
    """
    메인 실행
    """
    
    print("\n" + "="*60)
    print("🎯 BitVMX 옵션 등록 - 실제 트랜잭션")
    print("  네트워크: MutinyNet")
    print("  프로토콜: BitVMX")
    print("="*60)
    
    # 트랜잭션 생성
    tx_hex, option_data = create_option_registration_tx()
    
    print(f"\n생성된 트랜잭션:")
    print(f"  Hex (처음 100자): {tx_hex[:100]}...")
    print(f"  전체 길이: {len(tx_hex)} 문자")
    
    # 브로드캐스트
    success = broadcast_transaction(tx_hex)
    
    if success:
        print("\n🎉 BitVMX 옵션 등록 성공!")
        print(f"  옵션 ID: {option_data['id']}")
        print(f"  타입: {option_data['type']}")
        print(f"  행사가: ${option_data['strike']:,}")
        print(f"  만기: {option_data['expiry']}")
        print("\n💡 다음 단계:")
        print("  1. BitVMX Explorer에서 프로토콜 확인")
        print("  2. Pre-sign 트랜잭션 생성")
        print("  3. 옵션 만기 시 자동 정산")
    else:
        print("\n⚠️ 트랜잭션 브로드캐스트 실패")
        print("  Raw hex를 수동으로 브로드캐스트하려면:")
        print(f"  https://mutinynet.com/tx/push")
        print(f"\n  트랜잭션 hex:")
        print(f"  {tx_hex}")
    
    print("\n" + "="*60)

if __name__ == "__main__":
    main()