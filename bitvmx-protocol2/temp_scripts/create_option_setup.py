#!/usr/bin/env python3
"""
BTCFi 옵션 상품 등록을 위한 BitVMX 셋업 생성
"""
import json
import uuid
import sys
import os
import hashlib

# BitVMX 라이브러리 경로 추가
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from bitvmx_protocol_library.transaction_generation.services.transaction_generator_from_public_keys_service_optimized import (
    TransactionGeneratorFromPublicKeysServiceOptimized
)
from bitvmx_protocol_library.transaction_generation.services.generate_signatures_service import (
    GenerateSignaturesService
)
from bitvmx_protocol_library.transaction_generation.services.apply_signatures_to_transactions_service import (
    ApplySignaturesToTransactionsService
)
from bitcoinutils.setup import setup
from bitcoinutils.keys import PrivateKey

# Bitcoin testnet 설정
setup('testnet')

def create_option_setup():
    """옵션 등록용 BitVMX 셋업 생성"""
    
    # 새 UUID 생성
    setup_uuid = str(uuid.uuid4())
    print(f"Creating new setup with UUID: {setup_uuid}")
    
    # 새로운 UTXO 사용 (2 BTC 받은 것)
    funding_data = {
        "funding_tx_id": "66115221c1c2ec635371a7ea46eeda175e766b51982fe5b2e710793be8523dff",
        "funding_amount_satoshis": 199997187,
        "taproot_private_key": "d8a1e1224e63135765bde9dc8a2c8e403eee8be73d3589d58c5ddbf9dce3fdf4",
        "taproot_public_key": "03bf751f0d2d22e6f0163c9acaa14ae04e6e1a004cb4a24d893c1f86314e79d5de"
    }
    
    # 옵션 데이터 (오프체인 저장)
    option_data = {
        "type": "PUT",
        "strike": 50000,
        "spot": 54000,
        "quantity": 100,
        "setup_uuid": setup_uuid
    }
    
    # 옵션 데이터의 32바이트 커밋먼트 생성 (BitVMX 원칙)
    option_json = json.dumps(option_data, sort_keys=True, separators=(',', ':'))
    option_commitment = hashlib.sha256(option_json.encode()).hexdigest()[:8]  # 첫 4바이트만
    
    # 셋업 데이터
    setup_data = {
        "setup_uuid": setup_uuid,
        "network": "mutinynet",
        "name": "BTCFi Option Registration with Taproot",
        "max_amount_of_steps": 50000,
        "amount_of_bits_wrong_step_search": 1,
        "funding_tx_id": funding_data['funding_tx_id'],  # Our new Taproot funding TX
        "funding_index": 0,
        "funding_amount_of_satoshis": funding_data['funding_amount_satoshis'],
        "secret_origin_of_funds": funding_data['taproot_private_key'],  # Taproot private key
        "prover_destination_address": "tb1qt8rdur557nz338g3lekc6458pj0dl63c0s9904",
        "prover_signature_private_key": funding_data['taproot_private_key'],
        "prover_signature_public_key": funding_data['taproot_public_key'],
        "verifier_signature_private_key": "cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc",
        "verifier_signature_public_key": "0366666666666666666666666666666666666666666666666666666666666666",
        "amount_of_input_words": 4,
        "step_fees_satoshis": 3000,
        "max_fee_allowed": 100000,
        "amount_of_public_inputs": 1,
        "list_of_public_inputs": [
            option_commitment  # 32바이트 커밋먼트의 첫 4바이트만 온체인
        ],
        "verifier_list": [],
        "prover_publishing_transaction_id": None,
        "rom_commitment_file": "execution_files/instruction_commitment_option_registration.txt",
        "elf_file": "execution_files/btcfi_option_registration_v2.elf"
    }
    
    # 디렉토리 생성
    prover_dir = f"prover_files/{setup_uuid}"
    os.makedirs(prover_dir, exist_ok=True)
    
    # 옵션 데이터 오프체인 저장
    option_file = f"{prover_dir}/option_metadata.json"
    with open(option_file, 'w') as f:
        json.dump({
            "option_data": option_data,
            "commitment": option_commitment,
            "full_commitment": hashlib.sha256(option_json.encode()).hexdigest()
        }, f, indent=2)
    
    # 셋업 파일 저장
    setup_file = f"{prover_dir}/setup.json"
    with open(setup_file, 'w') as f:
        json.dump(setup_data, f, indent=2)
    
    print(f"✅ Setup created: {setup_file}")
    
    # 트랜잭션 생성
    print("\n=== Generating transactions ===")
    
    # Public keys 설정
    prover_pubkey = setup_data["prover_signature_public_key"]
    verifier_pubkey = "0366666666666666666666666666666666666666666666666666666666666666"  # 더미
    
    # BitVMXProtocolSetupPropertiesDTO 생성
    from bitvmx_protocol_library.bitvmx_protocol_definition.entities.bitvmx_protocol_setup_properties_dto import BitVMXProtocolSetupPropertiesDTO
    from bitvmx_protocol_library.bitvmx_protocol_definition.entities.bitvmx_protocol_properties_dto import BitVMXProtocolPropertiesDTO
    
    # 설정 속성 생성
    protocol_properties = BitVMXProtocolPropertiesDTO(
        n0=4,
        n1=4,
        amount_of_nibbles_hash=8,
        amount_of_bits_wrong_step_search=2,
        amount_of_bits_per_digit_checksum=4
    )
    
    setup_dto = BitVMXProtocolSetupPropertiesDTO(
        setup_uuid=setup_uuid,
        bitvmx_protocol_properties_dto=protocol_properties,
        signature_public_keys=[prover_pubkey, verifier_pubkey],
        prover_signature_public_key=prover_pubkey,
        verifier_signature_public_key=verifier_pubkey,
        funding_tx_id=setup_data["funding_tx_id"],
        funding_index=setup_data["funding_index"],
        funding_amount_of_satoshis=setup_data["funding_amount_of_satoshis"],
        step_fees_satoshis=setup_data["step_fees_satoshis"],
        input_hex="00" * 32  # Dummy input for now
    )
    
    # 트랜잭션 생성기 초기화
    tx_generator = TransactionGeneratorFromPublicKeysServiceOptimized()
    
    # 트랜잭션 생성
    print("Generating unsigned transactions...")
    transactions = tx_generator(setup_dto)
    
    print(f"Generated {len(transactions.__dict__)} transaction types")
    
    # 서명 생성
    print("\nGenerating signatures...")
    signature_service = GenerateSignaturesService()
    signatures = signature_service(
        transactions,
        setup_data["prover_signature_private_key"],
        setup_data.get("verifier_signature_private_key", "cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc")
    )
    
    # 서명 적용
    print("Applying signatures...")
    apply_service = ApplySignaturesToTransactionsService()
    signed_transactions = apply_service(
        transactions,
        signatures,
        setup_data["funding_amount_of_satoshis"]
    )
    
    # 서명된 트랜잭션 저장
    signed_tx_dict = {}
    for key, value in signed_transactions.__dict__.items():
        if hasattr(value, 'to_hex'):
            signed_tx_dict[key] = value.to_hex()
        elif isinstance(value, list):
            signed_tx_dict[key] = [tx.to_hex() if hasattr(tx, 'to_hex') else str(tx) for tx in value]
            
    signed_file = f"{prover_dir}/signed_transactions.json"
    with open(signed_file, 'w') as f:
        json.dump(signed_tx_dict, f, indent=2)
    
    print(f"✅ Signed transactions saved: {signed_file}")
    
    # hash_result_tx 정보 출력
    if 'hash_result_tx' in signed_tx_dict:
        from bitcoinutils.transactions import Transaction
        hash_tx = Transaction.from_raw(signed_tx_dict['hash_result_tx'])
        print(f"\n=== hash_result_tx (옵션 등록 트랜잭션) ===")
        print(f"TXID: {hash_tx.get_txid()}")
        print(f"Size: {len(signed_tx_dict['hash_result_tx'])//2} bytes")
        print(f"Ready to broadcast!")
    
    return setup_uuid

if __name__ == "__main__":
    setup_uuid = create_option_setup()
    print(f"\n✅ Complete! Setup UUID: {setup_uuid}")
    print("\nNext step: Broadcast hash_result_tx to register option on-chain")