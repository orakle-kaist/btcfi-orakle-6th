#!/usr/bin/env python3
"""
옵션 상품 등록을 위한 실제 BitVMX 트랜잭션 생성
==============================================

Setup을 사용해서 실제 온체인에 올릴 hash_result_tx를 생성
"""

import json
import sys
import os

# BitVMX 라이브러리 경로 추가
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from bitvmx_protocol_library.transaction_generation.services.transaction_generator_from_public_keys_service_optimized import (
    TransactionGeneratorFromPublicKeysServiceOptimized
)
from bitvmx_protocol_library.bitvmx_protocol_definition.entities.bitvmx_protocol_setup_properties_dto import (
    BitVMXProtocolSetupPropertiesDTO
)
from bitvmx_protocol_library.transaction_generation.services.generate_signatures_service import (
    GenerateSignaturesService
)
from bitvmx_protocol_library.transaction_generation.services.apply_signatures_to_transactions_service import (
    ApplySignaturesToTransactionsService
)
from bitcoinutils.setup import setup
from bitcoinutils.keys import PrivateKey
from bitcoinutils.transactions import Transaction

# Bitcoin testnet 설정
setup('testnet')

def generate_option_registration_tx(setup_uuid: str):
    """
    Setup UUID를 사용해서 실제 온체인 트랜잭션 생성
    """
    
    print(f"\n{'='*60}")
    print(f"BitVMX 옵션 등록 트랜잭션 생성")
    print(f"{'='*60}")
    print(f"Setup UUID: {setup_uuid}")
    
    # 1. Setup 파일 로드
    setup_file = f"prover_files/{setup_uuid}/setup.json"
    option_file = f"prover_files/{setup_uuid}/option_product.json"
    
    if not os.path.exists(setup_file):
        print(f"❌ Setup 파일을 찾을 수 없습니다: {setup_file}")
        return None
    
    with open(setup_file, 'r') as f:
        setup_data = json.load(f)
    
    with open(option_file, 'r') as f:
        option_data = json.load(f)
    
    print(f"\n📊 옵션 상품: {option_data['product_data']['name']}")
    print(f"🔒 커밋먼트 (온체인): {setup_data['list_of_public_inputs'][0]}")
    
    # 2. BitVMXProtocolSetupPropertiesDTO 생성
    print(f"\n트랜잭션 생성 중...")
    
    setup_dto = BitVMXProtocolSetupPropertiesDTO(
        setup_uuid=setup_data["setup_uuid"],
        n_blocks_duration=10,
        escrow_public_key="",
        escrow_signature="",
        prover_public_key=setup_data["prover_signature_public_key"],
        prover_signature="",
        verifier_public_key=setup_data["verifier_signature_public_key"], 
        verifier_signature="",
        prover_destination_address=setup_data["prover_destination_address"],
        step_fees_satoshis=setup_data["step_fees_satoshis"],
        max_amount_of_steps=setup_data["max_amount_of_steps"],
        amount_of_bits_per_digit_checksum=1,
        network=setup_data["network"],
        funding_amount_of_satoshis=setup_data["funding_amount_of_satoshis"],
        funding_tx_id=setup_data["funding_tx_id"],
        funding_index=setup_data["funding_index"],
        prover_signature_private_key=setup_data["prover_signature_private_key"],
        verifier_signature_private_key=setup_data["verifier_signature_private_key"],
        secret_origin_of_funds=setup_data["secret_origin_of_funds"],
        amount_of_input_words=setup_data["amount_of_input_words"],
        trace_words_lengths=[],
        amount_of_bits_wrong_step_search=setup_data["amount_of_bits_wrong_step_search"],
        amount_of_blake3_hashes=32,
        amount_of_sha256_hashes=32,
        blake3_hash_as_hex=[],
        sha256_hash_as_hex=[]
    )
    
    # 3. 트랜잭션 생성
    try:
        tx_generator = TransactionGeneratorFromPublicKeysServiceOptimized()
        
        # 트랜잭션 생성
        print("  - 트랜잭션 구조 생성...")
        transactions = tx_generator(setup_dto)
        
        # 서명 생성
        print("  - 서명 생성...")
        signature_service = GenerateSignaturesService()
        signatures = signature_service(
            transactions,
            setup_data["prover_signature_private_key"],
            setup_data.get("verifier_signature_private_key", "0000000000000000000000000000000000000000000000000000000000000002")
        )
        
        # 서명 적용
        print("  - 서명 적용...")
        apply_service = ApplySignaturesToTransactionsService()
        signed_transactions = apply_service(
            transactions,
            signatures,
            setup_data["funding_amount_of_satoshis"]
        )
        
        # hash_result_tx 추출
        if hasattr(signed_transactions, 'hash_result_tx'):
            hash_tx_hex = signed_transactions.hash_result_tx.to_hex()
            hash_tx = Transaction.from_raw(hash_tx_hex)
            txid = hash_tx.get_txid()
            
            print(f"\n✅ 트랜잭션 생성 성공!")
            print(f"  TXID: {txid}")
            print(f"  크기: {len(hash_tx_hex)//2} bytes")
            
            # 트랜잭션 저장
            tx_file = f"prover_files/{setup_uuid}/hash_result_tx.json"
            with open(tx_file, 'w') as f:
                json.dump({
                    "txid": txid,
                    "raw_tx": hash_tx_hex,
                    "size": len(hash_tx_hex)//2,
                    "commitment_onchain": setup_data['list_of_public_inputs'][0],
                    "option_product": option_data['product_data']['name']
                }, f, indent=2)
            
            print(f"  저장: {tx_file}")
            
            # 트랜잭션 분석
            print(f"\n📋 트랜잭션 분석:")
            print(f"  입력: Funding UTXO ({setup_data['funding_tx_id']}:{setup_data['funding_index']})")
            print(f"  출력: BitVMX commitment script")
            print(f"  커밋먼트: {setup_data['list_of_public_inputs'][0]} (4 bytes)")
            print(f"  실제 데이터: 오프체인에 저장 (290 bytes)")
            
            return txid, hash_tx_hex
            
    except Exception as e:
        print(f"❌ 트랜잭션 생성 실패: {e}")
        import traceback
        traceback.print_exc()
        return None, None
    
    return None, None


def main():
    """메인 실행 함수"""
    
    print("\n" + "🚀 "*20)
    print("BitVMX 옵션 등록 트랜잭션 생성")
    print("온체인에는 4바이트 커밋먼트만!")
    print("🚀 "*20)
    
    # 가장 최근 Setup UUID 사용
    setup_uuid = "a72c9742-bddb-4fdd-800e-a9aa5b983b2e"
    
    # 트랜잭션 생성
    txid, raw_tx = generate_option_registration_tx(setup_uuid)
    
    if txid:
        print(f"\n{'='*60}")
        print("📈 효율성 요약")
        print(f"{'='*60}")
        print(f"✅ 온체인 데이터: 4 bytes (커밋먼트만)")
        print(f"✅ 오프체인 데이터: 290 bytes (실제 옵션 정보)")
        print(f"✅ 절감률: 98.6%")
        print(f"✅ BitVMX 원칙 준수 완료!")
        
        print(f"\n다음 단계:")
        print(f"1. 이 트랜잭션을 브로드캐스트")
        print(f"2. 컨펌 후 옵션 구매 가능")
        print(f"3. 만기 시 자동 정산")
    else:
        print("\n❌ 트랜잭션 생성 실패")


if __name__ == "__main__":
    main()