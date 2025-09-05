#!/usr/bin/env python3

import json
import secrets
import subprocess
import tempfile
import time
import os

# Fresh UTXO to use
UTXO_TXID = "3398087bd04b8f47e20700fa451d8c455986d0e93a2787ed6280e383f0f6bf87"
UTXO_VOUT = 1
UTXO_VALUE = 10000000

# Generate fresh keys
secret = secrets.token_hex(32)
n0 = int(secrets.token_hex(32), 16)
n1 = int(secrets.token_hex(32), 16)
prover_key = secrets.token_hex(32)

# Setup parameters - reduced for smaller witness
setup_data = {
    "max_amount_of_steps": 16,
    "amount_of_input_words": 2,  # Reduced from 4
    "amount_of_bits_wrong_step_search": 2,
    "amount_of_bits_per_digit_checksum": 4,
    "funding_tx_id": UTXO_TXID,
    "funding_index": UTXO_VOUT,
    "funding_amount": UTXO_VALUE,
    "secret_origin_of_funds": secret,
    "prover_destination_address": "tb1qt8rdur557nz338g3lekc6458pj0dl63c0s9904",
    "prover_signature_private_key_hex": prover_key,
    "n0": str(n0),
    "n1": str(n1),
    "elf_file_name": "option_registration_final.elf",
    "input_hex": "0000C350" + "000F4240",  # 2 words only
    "timeout_seconds": 600
}

print("🚀 Creating fresh BitVMX setup")
print(f"📦 Using UTXO: {UTXO_TXID}:{UTXO_VOUT}")
print(f"💰 Amount: {UTXO_VALUE} sats")
print(f"📝 Input words: {setup_data['amount_of_input_words']}")
print(f"🔢 Max steps: {setup_data['max_amount_of_steps']}")
print()

# Save to temp file
with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
    json.dump(setup_data, f, indent=2)
    temp_file = f.name

print(f"📄 Setup data saved to: {temp_file}")

# Call API using curl
print("📡 Calling prover API...")
cmd = [
    'curl', '-X', 'POST',
    'http://localhost:8080/api/v1/setup',
    '-H', 'Content-Type: application/json',
    '-d', f'@{temp_file}',
    '--max-time', '60'
]

try:
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    
    if result.returncode == 0:
        response = json.loads(result.stdout)
        print("✅ Setup created successfully!")
        print(f"🆔 Setup UUID: {response.get('setup_uuid')}")
        print(f"📍 Funding address: {response.get('funding_address')}")
        
        # Save the response
        with open('fresh_setup.json', 'w') as f:
            json.dump(response, f, indent=2)
        print("💾 Saved to fresh_setup.json")
        
    else:
        print(f"❌ Failed: {result.stdout}")
        if result.stderr:
            print(f"Error: {result.stderr}")
            
except Exception as e:
    print(f"❌ Error: {e}")
    
finally:
    # Cleanup
    if os.path.exists(temp_file):
        os.unlink(temp_file)