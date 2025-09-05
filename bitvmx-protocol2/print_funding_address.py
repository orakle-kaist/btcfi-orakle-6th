#!/usr/bin/env python3
"""Generate BitVMX Taproot funding address"""

import uuid
import requests
import sys
import os

# Add path for bitvmx_protocol_library
sys.path.insert(0, '.')

from bitcoinutils.keys import PrivateKey
from bitcoinutils.setup import setup as btc_setup

# Setup bitcoin network
btc_setup('testnet')

from bitvmx_protocol_library.bitvmx_protocol_definition.entities.bitvmx_protocol_properties_dto import BitVMXProtocolPropertiesDTO
from bitvmx_protocol_library.bitvmx_protocol_definition.entities.bitvmx_protocol_setup_properties_dto import BitVMXProtocolSetupPropertiesDTO
from bitvmx_protocol_library.script_generation.services.bitvmx_bitcoin_scripts_generator_service import BitVMXBitcoinScriptsGeneratorService
from bitvmx_protocol_library.script_generation.entities.business_objects.bitcoin_script_list import BitcoinScriptList

PROVER_URL = "http://localhost:8080"
VERIFIER_URL = "http://localhost:8081"

def generate_funding_address():
    setup_uuid = str(uuid.uuid4())
    print(f"🔑 Setup UUID: {setup_uuid}")
    
    # 1) Verifier /setup (키 생성)
    print("📡 Contacting verifier...")
    r = requests.post(f"{VERIFIER_URL}/api/v1/setup", json={
        "setup_uuid": setup_uuid, 
        "network": "mutinynet"
    })
    r.raise_for_status()
    v_pub = r.json()["public_key"]  # verifier destroyed pubkey (hex)
    print(f"✅ Verifier public key: {v_pub[:20]}...")
    
    # 2) Prover destroyed key 생성
    p_priv = PrivateKey()  # random
    p_pub = p_priv.get_public_key().to_hex()
    print(f"✅ Prover public key: {p_pub[:20]}...")
    
    # 3) Unspendable PK 계산
    seed = v_pub + p_pub
    unspendable_pk = BitVMXProtocolSetupPropertiesDTO.unspendable_public_key_from_seed(seed)
    print(f"🔒 Unspendable PK: {unspendable_pk.to_hex()[:20]}...")
    
    # 4) DTO 구성(스크립트 생성을 위한 최소 값)
    props = BitVMXProtocolPropertiesDTO(
        max_amount_of_steps=16, 
        amount_of_input_words=2,  # Reduced for smaller witness
        amount_of_bits_wrong_step_search=2, 
        amount_of_bits_per_digit_checksum=4
    )
    
    dto = BitVMXProtocolSetupPropertiesDTO(
        setup_uuid=setup_uuid,
        uuid=str(uuid.uuid4()),
        funding_amount_of_satoshis=10000000,
        step_fees_satoshis=7000,
        funding_tx_id="0"*64,
        funding_index=0,
        verifier_address_dict={},
        prover_destination_address="tb1qt8rdur557nz338g3lekc6458pj0dl63c0s9904",
        prover_signature_public_key=p_pub,
        verifier_signature_public_key="03"+"6"*64,
        verifier_destination_address="tb1q8fg5jrspc7fn8jvpe5tfr7e5dlwvsh6xw8cq4j",
        seed_unspendable_public_key=seed,
        prover_destroyed_public_key=p_pub,
        verifier_destroyed_public_key=v_pub,
        bitvmx_protocol_properties_dto=props,
        elf_file_name="option_registration_final.elf",
        bitvmx_bitcoin_scripts_dto=None,
        bitvmx_transactions_dto=None,
        bitvmx_prover_winternitz_public_keys_dto=None,
        bitvmx_verifier_winternitz_public_keys_dto=None,
        signature_public_keys=None,
        unspendable_public_key=unspendable_pk
    )
    
    # 5) 스크립트 생성 후 트리 주소 계산
    print("🔨 Generating scripts...")
    scripts = BitVMXBitcoinScriptsGeneratorService(
        elf_file_name=dto.elf_file_name
    )(bitvmx_protocol_setup_properties_dto=dto)
    
    tree = BitcoinScriptList([
        scripts.hash_result_script,
        scripts.prover_timeout_script
    ])
    
    addr = tree.get_taproot_address(unspendable_pk)
    
    print("=" * 60)
    print("✨ BitVMX Taproot Funding Address Generated!")
    print("=" * 60)
    print(f"📍 Address: {addr.to_string()}")
    print(f"🆔 Setup UUID: {setup_uuid}")
    print()
    print("📋 Next steps:")
    print("1. Send testnet BTC to the address above")
    print("2. Wait for confirmation")
    print("3. Run setup with the funding TXID and output index")
    print("=" * 60)
    
    # Save for later use
    with open('funding_address.txt', 'w') as f:
        f.write(f"Address: {addr.to_string()}\n")
        f.write(f"Setup UUID: {setup_uuid}\n")
        f.write(f"Prover key: {p_priv.to_hex()}\n")
        f.write(f"Verifier pubkey: {v_pub}\n")
    
    return addr.to_string(), setup_uuid

if __name__ == "__main__":
    try:
        addr, uuid = generate_funding_address()
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()