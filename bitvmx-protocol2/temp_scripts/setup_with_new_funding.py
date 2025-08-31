#!/usr/bin/env python3

"""
Create BitVMX Setup with our new Taproot funding TX
====================================================
"""

import json
import requests
import secrets
from bitcoinutils.keys import PrivateKey

# Load our funding TX data
with open('taproot_funding_data.json', 'r') as f:
    funding_data = json.load(f)

print("=" * 60)
print("BitVMX Setup with New Taproot Funding TX")
print("=" * 60)
print(f"Funding TX: {funding_data['funding_tx_id']}")
print(f"Amount: {funding_data['funding_amount_satoshis']} sats")
print(f"Private key: {funding_data['taproot_private_key'][:16]}...")
print("=" * 60)

# Generate signature keys
sig_private_key = PrivateKey(b=secrets.token_bytes(32))
sig_public_key = sig_private_key.get_public_key()

# Setup data
setup_data = {
    "max_amount_of_steps": 100,
    "amount_of_input_words": 4,
    "amount_of_bits_wrong_step_search": 3,
    "amount_of_bits_per_digit_checksum": 4,
    "funding_tx_id": funding_data['funding_tx_id'],
    "funding_index": funding_data['funding_index'],
    "secret_origin_of_funds": funding_data['taproot_private_key'],
    "verifier_list": ["http://verifier-backend:80"],  # Correct verifier URL without /api/v1
    "prover_destination_address": "tb1qd28npep0s8frcm3y7dxqajkcy2m40eysplyr9v",
    "prover_signature_private_key": sig_private_key.to_bytes().hex(),
    "prover_signature_public_key": sig_public_key.to_hex(),
    # Add verifier fields even with empty list
    "verifier_destination_address": "tb1qd28npep0s8frcm3y7dxqajkcy2m40eysplyr9v",
    "verifier_signature_public_key": "0366666666666666666666666666666666666666666666666666666666666666",
    "verifier_destroyed_public_key": "0377777777777777777777777777777777777777777777777777777777777777"
}

# Create setup
print("\n📝 Creating BitVMX Setup...")
response = requests.post(
    "http://localhost:8081/api/v1/setup",
    json=setup_data,
    timeout=600
)

if response.status_code == 200:
    result = response.json()
    setup_uuid = result['setup_uuid']
    print(f"✅ Setup created: {setup_uuid}")
    
    # Save setup info
    setup_info = {
        "setup_uuid": setup_uuid,
        "funding_tx_id": funding_data['funding_tx_id'],
        "funding_amount": funding_data['funding_amount_satoshis'],
        "taproot_private_key": funding_data['taproot_private_key']
    }
    
    with open(f'setup_{setup_uuid}.json', 'w') as f:
        json.dump(setup_info, f, indent=2)
    
    # Submit option input
    option_hex = "00000001004c4b40005265c000000064"  # PUT, $50K, $54K, 100
    
    print(f"\n📊 Submitting option input...")
    input_response = requests.post(
        f"http://localhost:8081/api/v1/input",
        json={"setup_uuid": setup_uuid, "input_hex": option_hex},
        timeout=60
    )
    
    if input_response.status_code == 200:
        print("✅ Option input submitted!")
        
        # Generate Prover TX
        print(f"\n🔨 Generating Prover TX...")
        next_response = requests.post(
            f"http://localhost:8081/api/v1/next_step",
            json={"setup_uuid": setup_uuid},
            timeout=120
        )
        
        if next_response.status_code == 200:
            next_result = next_response.json()
            print("✅ Prover TX generated!")
            print(f"   {next_result.get('message', '')}")
            
            print("\n" + "🎉" * 30)
            print("SUCCESS! Complete BitVMX Flow:")
            print("1. Taproot Funding TX: ✅")
            print("2. BitVMX Setup: ✅")
            print("3. Option Input: ✅")
            print("4. Prover TX: ✅")
            print("🎉" * 30)
        else:
            print(f"❌ Prover TX failed: {next_response.text}")
    else:
        print(f"❌ Input failed: {input_response.text}")
else:
    print(f"❌ Setup failed: {response.text}")