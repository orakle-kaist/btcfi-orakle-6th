#!/usr/bin/env python3
"""
BitVMX API call with proper verifier configuration
"""
import json
import requests
import time

def main():
    API_BASE = "http://localhost:8081"
    
    # Setup input with verifier properly configured
    setup_input = {
        # Core parameters
        "max_amount_of_steps": 10,
        "amount_of_bits_wrong_step_search": 1,
        "funding_tx_id": "66115221c1c2ec635371a7ea46eeda175e766b51982fe5b2e710793be8523dff",
        "funding_index": 0,
        "funding_amount_of_satoshis": 199997187,
        "secret_origin_of_funds": "d8a1e1224e63135765bde9dc8a2c8e403eee8be73d3589d58c5ddbf9dce3fdf4",
        "prover_destination_address": "tb1qt8rdur557nz338g3lekc6458pj0dl63c0s9904",
        "amount_of_input_words": 1,
        
        # Prover keys
        "prover_signature_private_key": "d8a1e1224e63135765bde9dc8a2c8e403eee8be73d3589d58c5ddbf9dce3fdf4",
        "prover_signature_public_key": "03bf751f0d2d22e6f0163c9acaa14ae04e6e1a004cb4a24d893c1f86314e79d5de",
        
        # Verifier parameters
        "verifier_signature_private_key": "cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc",
        "verifier_signature_public_key": "03999269c93633303d8f5173bc017e5046f933053c59ebdde6bb3dd8d8de0528ba",
        "verifier_destination_address": "tb1qyvsy6ypssxmqmdzthzua3qwupkey90p3cdeuxx",
        
        # Fees
        "step_fees_satoshis": 1000,
        
        # Use Docker network name for verifier
        "verifier_list": ["http://verifier-backend:80"]
    }
    
    print("=" * 60)
    print("BITVMX SETUP WITH VERIFIER")
    print("=" * 60)
    print(f"\nFunding TX: {setup_input['funding_tx_id'][:16]}...")
    print(f"Amount: {setup_input['funding_amount_of_satoshis']:,} sats")
    print(f"Prover address: {setup_input['prover_destination_address']}")
    print(f"Verifier: {setup_input['verifier_list'][0]}")
    
    try:
        # Health check both services
        prover_health = requests.get(f"{API_BASE}/healthcheck", timeout=2)
        print(f"\n✅ Prover: {prover_health.json()}")
        
        verifier_health = requests.get("http://localhost:8080/healthcheck", timeout=2)
        print(f"✅ Verifier: {verifier_health.json()}")
        
        # Call setup
        print("\n📡 Calling /api/v1/setup...")
        response = requests.post(
            f"{API_BASE}/api/v1/setup",
            json=setup_input,
            timeout=120  # Longer timeout for complex setup
        )
        
        if response.status_code == 200:
            result = response.json()
            setup_uuid = result.get('setup_uuid')
            print(f"\n✅ SUCCESS!")
            print(f"   Setup UUID: {setup_uuid}")
            
            # Check if files were created
            import os
            prover_dir = f"prover_files/{setup_uuid}"
            if os.path.exists(prover_dir):
                files = os.listdir(prover_dir)
                print(f"\n📂 Generated files:")
                for f in files:
                    print(f"   - {f}")
            
            return setup_uuid
        else:
            print(f"\n❌ Failed: {response.status_code}")
            print(f"Response: {response.text[:500]}")
            
    except Exception as e:
        print(f"\n❌ Error: {e}")
    
    return None

if __name__ == "__main__":
    setup_uuid = main()
    if setup_uuid:
        print(f"\n🎉 Setup created successfully!")
        print(f"   UUID: {setup_uuid}")
        print(f"   Check: prover_files/{setup_uuid}/")