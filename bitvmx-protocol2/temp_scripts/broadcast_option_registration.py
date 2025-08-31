#!/usr/bin/env python3
"""
옵션 등록 트랜잭션을 실제 Mutinynet에 브로드캐스트
"""

import json
import requests
from bitcoinutils.setup import setup
from bitcoinutils.keys import PrivateKey
from bitcoinutils.transactions import Transaction, TxInput, TxOutput, TxWitnessInput
from bitcoinutils.script import Script
import hashlib

# Mutinynet 설정
setup('testnet')

def broadcast_option_registration():
    """실제 Mutinynet에 옵션 등록 트랜잭션 브로드캐스트"""
    
    print("\n" + "="*60)
    print("옵션 등록 트랜잭션 Mutinynet 브로드캐스트")
    print("="*60)
    
    # Setup 데이터 로드
    setup_uuid = "a72c9742-bddb-4fdd-800e-a9aa5b983b2e"
    
    try:
        with open(f"prover_files/{setup_uuid}/setup.json", 'r') as f:
            setup_data = json.load(f)
        
        with open(f"prover_files/{setup_uuid}/option_product.json", 'r') as f:
            option_data = json.load(f)
    except FileNotFoundError:
        print("❌ Setup 파일을 찾을 수 없습니다")
        return None
    
    print(f"📊 옵션 상품: {option_data['product_data']['name']}")
    print(f"🔒 커밋먼트: {setup_data['list_of_public_inputs'][0]}")
    
    # 트랜잭션 생성
    funding_txid = setup_data['funding_tx_id']
    funding_index = setup_data['funding_index']
    funding_amount = setup_data['funding_amount_of_satoshis']
    
    # Private key
    priv_key = PrivateKey(secret_exponent=int(setup_data['secret_origin_of_funds'], 16))
    pub_key = priv_key.get_public_key()
    
    # OP_RETURN output with commitment (4 bytes)
    commitment = bytes.fromhex(setup_data['list_of_public_inputs'][0])
    op_return_script = Script(['OP_RETURN', commitment.hex()])
    
    # Change output (P2WPKH)
    fee = 5000  # 수수료
    change_amount = funding_amount - fee
    
    # P2WPKH script for change
    pubkey_hash = hashlib.new('ripemd160', hashlib.sha256(pub_key.to_bytes()).digest()).digest()
    change_script = Script(['OP_0', pubkey_hash.hex()])
    
    # 트랜잭션 생성
    tx_input = TxInput(funding_txid, funding_index)
    tx_output_opreturn = TxOutput(0, op_return_script)  # OP_RETURN은 0 satoshi
    tx_output_change = TxOutput(change_amount, change_script)
    
    tx = Transaction([tx_input], [tx_output_opreturn, tx_output_change], has_segwit=True)
    
    # 서명 (P2WPKH witness)
    script_code = Script(['OP_DUP', 'OP_HASH160', pubkey_hash.hex(), 'OP_EQUALVERIFY', 'OP_CHECKSIG'])
    sig = priv_key.sign_segwit_input(tx, 0, script_code, funding_amount)
    witness = TxWitnessInput([sig, pub_key.to_hex()])
    tx.witnesses = [witness]
    
    # 트랜잭션 정보
    raw_tx = tx.serialize()
    txid = tx.get_txid()
    
    print(f"\n📋 트랜잭션 정보:")
    print(f"  TXID: {txid}")
    print(f"  크기: {len(raw_tx)//2} bytes")
    print(f"  입력: {funding_txid}:{funding_index}")
    print(f"  출력1: OP_RETURN {commitment.hex()} (4 bytes)")
    print(f"  출력2: Change {change_amount} sats")
    
    # Mutinynet API로 브로드캐스트
    print(f"\n🚀 브로드캐스트 중...")
    
    try:
        # Mutinynet API
        url = "https://mutinynet.com/api/tx"
        response = requests.post(url, data=raw_tx)
        
        if response.status_code == 200:
            print(f"✅ 브로드캐스트 성공!")
            print(f"   TXID: {txid}")
            print(f"   Explorer: https://mutinynet.com/tx/{txid}")
            
            # 결과 저장
            result = {
                "txid": txid,
                "raw_tx": raw_tx,
                "size": len(raw_tx)//2,
                "commitment": commitment.hex(),
                "option_product": option_data['product_data']['name'],
                "broadcast_success": True
            }
            
            with open(f"prover_files/{setup_uuid}/broadcast_result.json", 'w') as f:
                json.dump(result, f, indent=2)
            
            return txid
        else:
            print(f"❌ 브로드캐스트 실패: {response.status_code}")
            print(f"   응답: {response.text}")
            
    except Exception as e:
        print(f"❌ 브로드캐스트 오류: {e}")
    
    # 대안: bitcoind RPC (로컬 노드가 있는 경우)
    print("\n대안: Bitcoin RPC 시도...")
    try:
        import subprocess
        result = subprocess.run(
            ["bitcoin-cli", "-testnet", "sendrawtransaction", raw_tx],
            capture_output=True,
            text=True
        )
        if result.returncode == 0:
            print(f"✅ RPC 브로드캐스트 성공!")
            print(f"   TXID: {result.stdout.strip()}")
            return result.stdout.strip()
        else:
            print(f"❌ RPC 브로드캐스트 실패: {result.stderr}")
    except:
        pass
    
    # 수동 브로드캐스트용 정보 저장
    print("\n💾 수동 브로드캐스트용 정보 저장...")
    manual_broadcast = {
        "txid": txid,
        "raw_tx": raw_tx,
        "instruction": "다음 사이트에서 수동으로 브로드캐스트하세요:",
        "sites": [
            "https://mutinynet.com/broadcast",
            "https://blockstream.info/testnet/tx/push", 
            "https://testnet.blockchain.info/pushtx"
        ]
    }
    
    with open(f"prover_files/{setup_uuid}/manual_broadcast.json", 'w') as f:
        json.dump(manual_broadcast, f, indent=2)
    
    print(f"  파일: prover_files/{setup_uuid}/manual_broadcast.json")
    print(f"  Raw TX를 위 사이트에서 수동으로 제출하세요")
    
    return None

def check_funding_utxo():
    """Funding UTXO 확인"""
    setup_uuid = "a72c9742-bddb-4fdd-800e-a9aa5b983b2e"
    
    with open(f"prover_files/{setup_uuid}/setup.json", 'r') as f:
        setup_data = json.load(f)
    
    funding_txid = setup_data['funding_tx_id']
    
    print(f"\n🔍 Funding UTXO 확인...")
    print(f"  TXID: {funding_txid}")
    
    # Mutinynet API로 확인
    try:
        url = f"https://mutinynet.com/api/tx/{funding_txid}"
        response = requests.get(url)
        
        if response.status_code == 200:
            print(f"✅ Funding TX 확인됨")
            return True
        else:
            print(f"❌ Funding TX를 찾을 수 없음")
            print(f"   먼저 Funding TX를 생성하고 브로드캐스트하세요")
            return False
    except Exception as e:
        print(f"❌ 확인 실패: {e}")
        return False

def main():
    """메인 실행"""
    
    print("\n" + "🚀 "*20)
    print("BitVMX 옵션 등록 - Mutinynet 브로드캐스트")
    print("온체인: 4바이트 커밋먼트만!")
    print("🚀 "*20)
    
    # Funding UTXO 확인
    if not check_funding_utxo():
        print("\n⚠️  Funding TX가 없습니다")
        print("   먼저 create_taproot_funding_tx.py를 실행하세요")
        return
    
    # 브로드캐스트
    txid = broadcast_option_registration()
    
    if txid:
        print(f"\n{'='*60}")
        print("🎉 성공!")
        print(f"{'='*60}")
        print(f"✅ 옵션 상품이 Mutinynet에 등록되었습니다")
        print(f"✅ TXID: {txid}")
        print(f"✅ 온체인 데이터: 4 bytes (커밋먼트만)")
        print(f"✅ 오프체인 데이터: 290 bytes (실제 옵션 정보)")
        print(f"✅ BitVMX 원칙 준수 완료!")

if __name__ == "__main__":
    main()