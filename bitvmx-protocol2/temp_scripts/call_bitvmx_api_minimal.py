#!/usr/bin/env python3
"""
Minimal BitVMX API call - Testing with simplest possible setup
"""
import json
import requests
import time

def main():
    API_BASE = "http://localhost:8081"
    
    # Minimal required data
    setup_input = {
        # Absolute minimum required fields
        "max_amount_of_steps": 10,
        "amount_of_bits_wrong_step_search": 1,
        "funding_tx_id": "66115221c1c2ec635371a7ea46eeda175e766b51982fe5b2e710793be8523dff",
        "funding_index": 0,
        "funding_amount_of_satoshis": 199997187,
        "secret_origin_of_funds": "d8a1e1224e63135765bde9dc8a2c8e403eee8be73d3589d58c5ddbf9dce3fdf4",
        "prover_destination_address": "tb1qt8rdur557nz338g3lekc6458pj0dl63c0s9904",
        "amount_of_input_words": 1,
        
        # Required prover keys
        "prover_signature_private_key": "d8a1e1224e63135765bde9dc8a2c8e403eee8be73d3589d58c5ddbf9dce3fdf4",
        "prover_signature_public_key": "03bf751f0d2d22e6f0163c9acaa14ae04e6e1a004cb4a24d893c1f86314e79d5de",
        
        # Required verifier parameters (dummy for single-party)
        "verifier_signature_private_key": "cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc",
        "verifier_signature_public_key": "0366666666666666666666666666666666666666666666666666666666666666",
        "verifier_destination_address": "tb1qvenenenen7nenen7nenen7nenen7nenen7nene07t93p",
        
        # Fees
        "step_fees_satoshis": 1000,
        "max_fee_allowed": 10000,
    }
    
    print("=" * 60)
    print("MINIMAL BITVMX SETUP TEST")
    print("=" * 60)
    print(f"\nFunding: {setup_input['funding_tx_id'][:10]}...")
    print(f"Amount: {setup_input['funding_amount_of_satoshis']} sats")
    print(f"Address: {setup_input['prover_destination_address']}")
    
    try:
        # Health check
        health = requests.get(f"{API_BASE}/healthcheck", timeout=2)
        print(f"\n✅ Prover service: {health.json()}")
        
        # Call setup
        print("\nCalling /api/v1/setup...")
        response = requests.post(
            f"{API_BASE}/api/v1/setup",
            json=setup_input,
            timeout=60
        )
        
        if response.status_code == 200:
            result = response.json()
            print(f"\n✅ SUCCESS! Setup UUID: {result.get('setup_uuid')}")
            return result.get('setup_uuid')
        else:
            print(f"\n❌ Failed: {response.status_code}")
            print(f"Response: {response.text}")
            
    except Exception as e:
        print(f"\n❌ Error: {e}")
    
    return None

if __name__ == "__main__":
    setup_uuid = main()
    if setup_uuid:
        print(f"\n🎉 Setup created: {setup_uuid}")