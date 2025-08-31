#!/usr/bin/env python3
"""
Call BitVMX Docker API - Using Original BitVMX Flow
Following the exact same flow as BitVMX protocol
"""
import json
import requests
import hashlib
import uuid
import time
import os

def main():
    """Call BitVMX prover API using Docker service"""
    
    # BitVMX Docker service endpoint (port 8081 for prover)
    API_BASE = "http://localhost:8081"
    
    # Check if service is running
    try:
        health = requests.get(f"{API_BASE}/healthcheck", timeout=2)
        print(f"✅ BitVMX Prover service status: {health.json()}")
    except Exception as e:
        print(f"❌ BitVMX Prover service not running. Start with:")
        print("   docker compose up prover-backend")
        return
    
    # Our funding from Mutinynet (2 BTC)
    funding_data = {
        "tx_id": "66115221c1c2ec635371a7ea46eeda175e766b51982fe5b2e710793be8523dff",
        "index": 0,
        "amount": 199997187,
        "private_key": "d8a1e1224e63135765bde9dc8a2c8e403eee8be73d3589d58c5ddbf9dce3fdf4",
        "public_key": "03bf751f0d2d22e6f0163c9acaa14ae04e6e1a004cb4a24d893c1f86314e79d5de",
        "address": "tb1qt8rdur557nz338g3lekc6458pj0dl63c0s9904"
    }
    
    # Option data for commitment (following BitVMX principle)
    option_data = {
        "type": "PUT",
        "strike": 50000,
        "spot": 54000,
        "quantity": 100
    }
    
    # Create 32-byte commitment, use first 4 bytes on-chain
    option_json = json.dumps(option_data, sort_keys=True, separators=(',', ':'))
    commitment_full = hashlib.sha256(option_json.encode()).hexdigest()
    commitment_4bytes = commitment_full[:8]
    
    print(f"\n=== BitVMX Setup Parameters ===")
    print(f"Funding TX: {funding_data['tx_id']}")
    print(f"Amount: {funding_data['amount']} sats")
    print(f"Option commitment: {commitment_4bytes}")
    
    # Setup input following BitVMX API schema
    # BitVMX requires both prover and verifier parameters
    setup_input = {
        # Core parameters (required)
        "max_amount_of_steps": 100,  # Reduced for faster processing
        "amount_of_bits_wrong_step_search": 1,
        "funding_tx_id": funding_data["tx_id"],
        "funding_index": funding_data["index"],
        "funding_amount_of_satoshis": funding_data["amount"],  # Explicitly specify amount
        "secret_origin_of_funds": funding_data["private_key"],
        "prover_destination_address": funding_data["address"],
        "amount_of_input_words": 1,
        
        # Use actual keys for prover
        "prover_signature_private_key": funding_data["private_key"],
        "prover_signature_public_key": funding_data["public_key"],
        
        # Verifier parameters (required by BitVMX protocol)
        # Using dummy values for single-party setup
        "verifier_signature_private_key": "cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc",
        "verifier_signature_public_key": "0366666666666666666666666666666666666666666666666666666666666666",
        "verifier_destination_address": "tb1qvenenenen7nenen7nenen7nenen7nenen7nene07t93p",  # Dummy but valid address
        "verifier_destroyed_public_key": "0377777777777777777777777777777777777777777777777777777777777777",
        
        # Optional parameters
        "step_fees_satoshis": 3000,
        "max_fee_allowed": 50000,
        
        # Public inputs (our option commitment)
        "amount_of_public_inputs": 1,
        "list_of_public_inputs": [commitment_4bytes],
        
        # Use the running verifier backend via Docker network
        # This follows the BitVMX protocol's two-party design
        "verifier_list": ["http://verifier-backend:80"]
    }
    
    print("\n=== Calling BitVMX Prover API ===")
    print(f"Endpoint: {API_BASE}/api/v1/setup")
    
    try:
        # Call setup endpoint (matches OpenAPI spec)
        response = requests.post(
            f"{API_BASE}/api/v1/setup",
            json=setup_input,
            timeout=300  # 5 minutes timeout
        )
        
        if response.status_code == 200:
            result = response.json()
            setup_uuid = result.get("setup_uuid")
            print(f"✅ Setup created successfully!")
            print(f"   Setup UUID: {setup_uuid}")
            
            # Check what files were created
            if setup_uuid:
                prover_dir = f"prover_files/{setup_uuid}"
                if os.path.exists(prover_dir):
                    files = os.listdir(prover_dir)
                    print(f"\n=== Generated files in {prover_dir} ===")
                    for f in files:
                        print(f"   - {f}")
                
                # Try to get signed transactions
                signed_file = f"{prover_dir}/signed_transactions.json"
                if os.path.exists(signed_file):
                    with open(signed_file, 'r') as f:
                        signed = json.load(f)
                        print(f"\n=== Signed transactions generated ===")
                        for key in signed.keys():
                            if isinstance(signed[key], list):
                                print(f"   - {key}: {len(signed[key])} transactions")
                            else:
                                print(f"   - {key}")
            
            return setup_uuid
            
        else:
            print(f"❌ API returned error {response.status_code}")
            print(f"   Response: {response.text}")
            
    except requests.exceptions.Timeout:
        print("❌ Request timed out (5 minutes)")
        print("   Consider reducing max_amount_of_steps")
    except Exception as e:
        print(f"❌ Error calling API: {e}")
    
    return None

if __name__ == "__main__":
    setup_uuid = main()
    
    if setup_uuid:
        print(f"\n✅ Complete! Setup UUID: {setup_uuid}")
        print("\nNext steps:")
        print("1. Check generated transactions in prover_files/{setup_uuid}/")
        print("2. Broadcast transactions to Mutinynet")
        print("3. Monitor option registration on blockchain")