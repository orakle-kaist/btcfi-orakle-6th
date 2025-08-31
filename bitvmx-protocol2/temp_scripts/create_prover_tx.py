#!/usr/bin/env python3

import json
import hashlib
import time
from bitcoinutils.setup import setup
from bitcoinutils.keys import PrivateKey, PublicKey
from bitcoinutils.transactions import Transaction, TxInput, TxOutput, TxWitnessInput
from bitcoinutils.script import Script

def create_prover_tx():
    # 테스트넷 설정
    setup('testnet')
    
    # Setup 파일 읽기
    setup_uuid = "ce08932e-0f17-4e33-b91e-21689a5198ce"
    with open(f"prover_files/{setup_uuid}/setup.json", 'r') as f:
        setup_data = json.load(f)
    
    # 개인키 설정
    priv_key_hex = setup_data['prover_signature_private_key']
    priv_key = PrivateKey(secret_exponent=int(priv_key_hex, 16))
    pub_key = priv_key.get_public_key()
    
    # Funding UTXO 정보
    funding_txid = setup_data['funding_tx_id']
    funding_index = setup_data['funding_index']
    funding_amount = setup_data['funding_amount_of_satoshis']
    
    # 옵션 데이터 (PUT 옵션) - 오프체인 저장
    option_data = {
        "type": 1,  # PUT
        "strike": 50000,
        "spot": 54000,
        "quantity": 100,
        "timestamp": int(time.time()),
        "setup_uuid": setup_uuid
    }
    
    # 옵션 데이터를 32바이트 커밋먼트로 변환 (온체인에는 이것만 저장)
    option_json = json.dumps(option_data, sort_keys=True, separators=(',', ':'))
    option_commitment = hashlib.sha256(option_json.encode()).hexdigest()
    
    # 오프체인에 실제 데이터 저장
    with open(f"prover_files/{setup_uuid}/option_metadata.json", 'w') as f:
        json.dump(option_data, f, indent=2)
    
    # Output 금액 계산 (수수료 제외)
    fee = 10000
    output_amount = funding_amount - fee
    
    # Taproot 주소 생성 (P2TR - 옵션 데이터 포함)
    # BitVMX는 P2TR을 사용하므로 taproot 주소로 변경
    taproot_pubkey = pub_key.to_hex()[2:]  # 압축된 공개키에서 prefix 제거
    output_script = Script(['OP_1', taproot_pubkey])  # P2TR script
    
    # Input 생성
    tx_input = TxInput(funding_txid, funding_index)
    
    # Output 생성 (P2TR)
    tx_output = TxOutput(output_amount, output_script)
    
    # 트랜잭션 생성
    tx = Transaction([tx_input], [tx_output], has_segwit=True)
    
    # P2WPKH witness 서명
    # scriptCode for P2WPKH
    pkh = hashlib.new('ripemd160', hashlib.sha256(bytes.fromhex(pub_key.to_hex())).digest()).digest()
    script_code = Script(['OP_DUP', 'OP_HASH160', pkh.hex(), 'OP_EQUALVERIFY', 'OP_CHECKSIG'])
    
    sig = priv_key.sign_segwit_input(tx, 0, script_code, funding_amount)
    witness = TxWitnessInput([sig, pub_key.to_hex()])
    tx.witnesses = [witness]
    
    # 결과 저장 (커밋먼트만 온체인, 실제 데이터는 오프체인)
    prover_tx_data = {
        "hash_result_tx": tx.serialize(),
        "txid": tx.get_txid(),
        "option_commitment": option_commitment,  # 32바이트 커밋먼트
        "funding_spent": f"{funding_txid}:{funding_index}"
    }
    
    # 파일로 저장
    with open(f"prover_files/{setup_uuid}/prover_tx.json", 'w') as f:
        json.dump(prover_tx_data, f, indent=2)
    
    print(f"Prover TX created successfully!")
    print(f"TXID: {tx.get_txid()}")
    print(f"Option data: {option_data}")
    print(f"Funding spent: {funding_txid}:{funding_index}")
    print(f"Output amount: {output_amount/100000000:.8f} BTC")
    
    return tx.get_txid(), tx.serialize()

if __name__ == "__main__":
    txid, raw_tx = create_prover_tx()