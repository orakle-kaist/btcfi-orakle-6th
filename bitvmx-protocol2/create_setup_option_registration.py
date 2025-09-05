#!/usr/bin/env python3
"""Create setup for option registration with option_registration_final.elf"""

import requests
import json
import time
import subprocess
import tempfile
import os
from datetime import datetime

# Configuration
PROVER_URL = "http://localhost:8080"
VERIFIER_URL = "http://localhost:8081"
ADDRESS = "tb1qt8rdur557nz338g3lekc6458pj0dl63c0s9904"

def find_best_utxo():
    """Find the best available UTXO for our address"""
    print("🔍 Finding available UTXOs...")
    
    try:
        # Get all UTXOs for our address
        response = requests.get(f"https://mutinynet.com/api/address/{ADDRESS}/utxo")
        utxos = response.json()
        
        # Filter for confirmed UTXOs with at least 1M sats
        available_utxos = []
        for utxo in utxos:
            if utxo.get("status", {}).get("confirmed", False) and utxo.get("value", 0) >= 1000000:
                # Check if this UTXO is unspent
                outspends_response = requests.get(f"https://mutinynet.com/api/tx/{utxo['txid']}/outspends")
                outspends = outspends_response.json()
                
                if len(outspends) > utxo["vout"] and not outspends[utxo["vout"]].get("spent", True):
                    available_utxos.append(utxo)
                    print(f"  ✅ Found UTXO: {utxo['txid']}:{utxo['vout']} with {utxo['value']} sats")
        
        if not available_utxos:
            print("  ❌ No available UTXOs found!")
            return None, None, None
        
        # Select the largest UTXO
        best_utxo = max(available_utxos, key=lambda x: x["value"])
        print(f"  🎯 Selected UTXO: {best_utxo['txid']}:{best_utxo['vout']} with {best_utxo['value']} sats")
        
        return best_utxo["txid"], best_utxo["vout"], best_utxo["value"]
        
    except Exception as e:
        print(f"  ❌ Error finding UTXOs: {e}")
        return None, None, None

# Find best UTXO automatically
funding_tx_id, funding_index, funding_amount = find_best_utxo()

if not funding_tx_id:
    print("❌ No available UTXO found. Please fund the address:", ADDRESS)
    exit(1)

print(f"📊 Using UTXO: {funding_tx_id}:{funding_index}")
print(f"💰 Amount: {funding_amount} sats")

# Generate unique n0, n1 based on current timestamp to avoid conflicts
import hashlib
timestamp_hash = hashlib.sha256(str(time.time()).encode()).hexdigest()
n0_base = int(timestamp_hash[:32], 16)
n1_base = int(timestamp_hash[32:], 16)

# Ensure n0 and n1 are large prime-like numbers
n0 = str(n0_base | (1 << 255) | 1)  # Set high bit and make odd
n1 = str((n0_base + 2) | (1 << 255) | 1)  # Slightly different, also odd

print(f"🔑 Generated n0: {n0[:20]}...")
print(f"🔑 Generated n1: {n1[:20]}...")

# Calculate wrapper TX fee based on estimated vsize
# P2WPKH input (68 vbytes) + P2TR output (43 vbytes) + overhead (11 vbytes) ≈ 122 vbytes
# But we'll use a conservative 200 vbytes to ensure it gets mined
wrapper_vsize = 200
sat_per_vbyte = 50  # Current network fee rate
wrapper_fee = wrapper_vsize * sat_per_vbyte
print(f"💸 Calculated wrapper fee: {wrapper_fee} sats ({wrapper_vsize} vbytes @ {sat_per_vbyte} sat/vB)")

# Adjust funding amount for wrapper fee if we'll need to create wrapper TX
# Check if the UTXO is P2WPKH (needs wrapper) or already P2TR (no wrapper needed)
adjusted_funding_amount = funding_amount
try:
    utxo_response = requests.get(f"https://mutinynet.com/api/tx/{funding_tx_id}")
    if utxo_response.status_code == 200:
        tx_data = utxo_response.json()
        if funding_index < len(tx_data.get("vout", [])):
            scriptpubkey = tx_data["vout"][funding_index].get("scriptpubkey", "")
            if scriptpubkey.startswith("0014"):  # P2WPKH
                print(f"📦 UTXO is P2WPKH, wrapper TX will be needed")
                adjusted_funding_amount = funding_amount - wrapper_fee
                print(f"💰 Adjusted funding amount: {adjusted_funding_amount} sats (after {wrapper_fee} sats wrapper fee)")
            elif scriptpubkey.startswith("5120"):  # P2TR
                print(f"✅ UTXO is already P2TR, no wrapper needed")
except Exception as e:
    print(f"⚠️ Could not determine UTXO type: {e}")
    # Conservative: assume wrapper is needed
    adjusted_funding_amount = funding_amount - wrapper_fee

# Setup data with only actually used parameters
setup_data = {
    "n0": n0,
    "n1": n1,
    "prover_public_key": "b882af3fb540e1c2530d3d9e11993f206bb7626e9cfe19a03e7e42c75e19ad59",
    "input_hex": "00000000404b4c0067d84e00005ed0b2",  # Option registration data (4 words: option_type, strike, expiry, pool_size) 
    "max_amount_of_steps": 16,  # Reduced for faster testing (2^4)
    "funding_tx_id": funding_tx_id,    # 자동으로 찾은 UTXO 사용
    "funding_index": funding_index,     # 자동으로 찾은 index 사용
    "funding_amount": adjusted_funding_amount,   # Adjusted for wrapper fee if needed
    "step_fees": 7000,  # Standard fee for regular transactions (hash_result uses HASH_FEES_SATOSHIS)
    "amount_of_bits_wrong_step_search": 2,  # 줄여서 빠른 테스트 (최대값은 3)
    "amount_of_bits_per_digit_checksum": 4,  # 체크섬 자릿수 비트 (필수)
    "secret_origin_of_funds": "d8a1e1224e63135765bde9dc8a2c8e403eee8be73d3589d58c5ddbf9dce3fdf4",
    "prover_destination_address": "tb1qt8rdur557nz338g3lekc6458pj0dl63c0s9904",
    "verifier_destination_address": "tb1q8fg5jrspc7fn8jvpe5tfr7e5dlwvsh6xw8cq4j",
    "prover_signature_private_key": "d8a1e1224e63135765bde9dc8a2c8e403eee8be73d3589d58c5ddbf9dce3fdf4",
    "prover_signature_public_key": "03bf751f0d2d22e6f0163c9acaa14ae04e6e1a004cb4a24d893c1f86314e79d5de",
    "amount_of_input_words": 4,  # 🔥 FIX: option_type, strike, expiry, pool_size (4 words = 32 hex chars)
    "elf_file_name": "option_registration_final.elf"  # 🔥 FIX: 원래 옵션 ELF 파일 사용
}


def create_setup():
    """Create the setup."""
    print(f"\n🚀 Creating setup with {setup_data['elf_file_name']} and {setup_data['max_amount_of_steps']} steps...")
    print(f"⏰ Started at: {datetime.now().strftime('%H:%M:%S')}")
    
    # Step 1: Call prover setup using curl
    print("\n📤 Step 1: Calling prover setup with curl...")
    start_time = time.time()
    
    # Write setup data to temp file for curl
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json.dump(setup_data, f, indent=2)
        temp_file = f.name
    
    try:
        # Use curl command exactly as BitvMX expects
        curl_cmd = [
            'curl', '-X', 'POST',
            f'{PROVER_URL}/api/v1/setup',
            '-H', 'Content-Type: application/json',
            '-d', f'@{temp_file}',
            '-s',  # Silent mode
            '--max-time', '1800'  # 30 minute timeout for first-time merkle computation
        ]
        
        print(f"📡 Executing: {' '.join(curl_cmd[:3])}...")
        print(f"📄 Sending data from: {temp_file}")
        # Debug: Show what we're sending
        with open(temp_file, 'r') as f:
            sent_data = json.load(f)
            print(f"   - funding_tx_id: {sent_data.get('funding_tx_id')}")
            print(f"   - funding_amount: {sent_data.get('funding_amount')} sats")
            print(f"   - elf_file_name: {sent_data.get('elf_file_name')}")
            print(f"   - max_steps: {sent_data.get('max_amount_of_steps')}")
        result = subprocess.run(curl_cmd, capture_output=True, text=True)
        
        elapsed = time.time() - start_time
        print(f"✅ Prover responded in {elapsed:.1f} seconds")
        
        if result.returncode == 0:
            print(f"📥 Raw response: {result.stdout[:500]}")  # Debug
            if not result.stdout:
                print("❌ Empty response from prover")
                return None
            prover_result = json.loads(result.stdout)
            setup_uuid = prover_result['setup_uuid']
            print(f"✅ Setup ID: {setup_uuid}")
            
            # Save setup UUID
            with open("current_setup.json", "w") as f:
                json.dump({
                    "setup_uuid": setup_uuid,
                    "created_at": datetime.now().isoformat(),
                    "elf_file": setup_data["elf_file_name"]
                }, f, indent=2)
            
            # Read DTO from file since API response doesn't include it
            dto_file = f"prover_files/{setup_uuid}/bitvmx_protocol_setup_properties_dto.json"
            print(f"📂 Reading DTO from: {dto_file}")
            
            # Wait for file to be created
            import time as time2
            for i in range(10):
                if os.path.exists(dto_file):
                    break
                time2.sleep(1)
            
            if not os.path.exists(dto_file):
                print(f"❌ DTO file not found: {dto_file}")
                return None
            
            with open(dto_file, "r") as f:
                dto_data = json.load(f)
            
            # Extract verifier data
            verifier_data = {
                "bitvmx_protocol_setup_properties_dto": dto_data
            }
            
            # Step 2: Call verifier using curl
            print("\n📤 Step 2: Calling verifier public keys generation with curl...")
            start_time = time.time()
            
            # Write verifier data to temp file
            with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
                json.dump(verifier_data, f, indent=2)
                verifier_temp_file = f.name
            
            curl_cmd_verifier = [
                'curl', '-X', 'POST',
                f'{VERIFIER_URL}/api/v1/public_keys',
                '-H', 'Content-Type: application/json',
                '-d', f'@{verifier_temp_file}',
                '-s',
                '--max-time', '120'
            ]
            
            print(f"📡 Executing verifier call...")
            verifier_result = subprocess.run(curl_cmd_verifier, capture_output=True, text=True)
            
            elapsed = time.time() - start_time
            print(f"✅ Verifier responded in {elapsed:.1f} seconds")
            
            # Clean up verifier temp file
            os.unlink(verifier_temp_file)
            
            if verifier_result.returncode == 0:
                print("✅ Verifier public keys generated successfully!")
                return setup_uuid
            else:
                print(f"❌ Verifier error: return code {verifier_result.returncode}")
                if verifier_result.stdout:
                    print(f"   Response: {verifier_result.stdout[:500]}")
                if verifier_result.stderr:
                    print(f"   Error: {verifier_result.stderr[:500]}")
                return None
                
        else:
            print(f"❌ Prover error: return code {result.returncode}")
            if result.stdout:
                print(f"   Response: {result.stdout[:500]}")
            if result.stderr:
                print(f"   Error: {result.stderr[:500]}")
            return None
            
    except subprocess.TimeoutExpired:
        elapsed = time.time() - start_time
        print(f"❌ Timeout after {elapsed:.1f} seconds")
        return None
    except Exception as e:
        print(f"❌ Error: {e}")
        return None
    finally:
        # Clean up temp files
        if 'temp_file' in locals() and os.path.exists(temp_file):
            os.unlink(temp_file)
        if 'verifier_temp_file' in locals() and os.path.exists(verifier_temp_file):
            os.unlink(verifier_temp_file)

if __name__ == "__main__":
    print("=" * 60)
    print("BitVMX Option Registration Setup")
    print(f"ELF: {setup_data['elf_file_name']}")
    print(f"Max Steps: {setup_data['max_amount_of_steps']}")
    print(f"Input Words: {setup_data['amount_of_input_words']} (option_type, strike, expiry, pool_size)")
    print(f"Input Hex: {setup_data['input_hex']}")
    print(f"Wrong Step Search Bits: {setup_data['amount_of_bits_wrong_step_search']}")
    print(f"Checksum Bits: {setup_data['amount_of_bits_per_digit_checksum']}")
    print(f"Funding: {adjusted_funding_amount} sats (original: {funding_amount})")
    print("=" * 60)
    
    setup_uuid = create_setup()
    
    if setup_uuid:
        print(f"\n✅ Setup created successfully: {setup_uuid}")
        
        # For No-Faucet mode: Broadcast wrapper TX if it exists
        wrapper_tx_path = "/tmp/funding_tx.hex"
        if os.path.exists(wrapper_tx_path):
            print("\n" + "=" * 60)
            print("📡 WRAPPER TX BROADCAST (No-Faucet Mode)")
            print("=" * 60)
            
            with open(wrapper_tx_path, "r") as f:
                wrapper_tx_hex = f.read().strip()
            
            print(f"📦 Wrapper TX found (length: {len(wrapper_tx_hex)} chars)")
            print(f"🔄 Converting P2WPKH → P2TR")
            
            # Broadcast wrapper TX
            try:
                response = requests.post(
                    "https://mutinynet.com/api/tx",
                    headers={"Content-Type": "text/plain"},
                    data=wrapper_tx_hex
                )
                
                if response.status_code == 200:
                    wrapper_txid = response.text.strip()
                    print(f"✅ Wrapper TX broadcast successful!")
                    print(f"📝 TXID: {wrapper_txid}")
                    print(f"🔗 https://mutinynet.com/tx/{wrapper_txid}")
                    
                    # Wait for confirmation
                    print("\n⏳ Waiting for wrapper TX to be confirmed...")
                    print("   (This creates the P2TR UTXO needed for hash_result_tx)")
                    
                    # Save wrapper TXID for reference
                    with open(f"prover_files/{setup_uuid}/wrapper_txid.txt", "w") as f:
                        f.write(wrapper_txid)
                    
                    print("\n📌 IMPORTANT: Wait for 1 confirmation before proceeding!")
                    print("   Then run: python test_final.py")
                    
                else:
                    print(f"❌ Wrapper TX broadcast failed: {response.text}")
                    
            except Exception as e:
                print(f"❌ Error broadcasting wrapper TX: {e}")
        else:
            print("\n📌 No wrapper TX needed (using native P2TR UTXO)")
            
    else:
        print("\n❌ Setup creation failed")