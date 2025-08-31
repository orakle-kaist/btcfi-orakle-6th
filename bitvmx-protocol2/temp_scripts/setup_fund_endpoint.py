#!/usr/bin/env python3
"""
Use /api/v1/setup/fund endpoint
"""
import json
import requests

def main():
    API_BASE = "http://localhost:8081"
    
    setup_input = {
        "max_amount_of_steps": 10,
        "amount_of_bits_wrong_step_search": 1,
        "amount_of_input_words": 1,
        
        # Our keys and address
        "secret_origin_of_funds": "d8a1e1224e63135765bde9dc8a2c8e403eee8be73d3589d58c5ddbf9dce3fdf4",
        "prover_signature_private_key": "d8a1e1224e63135765bde9dc8a2c8e403eee8be73d3589d58c5ddbf9dce3fdf4",
        "prover_signature_public_key": "03bf751f0d2d22e6f0163c9acaa14ae04e6e1a004cb4a24d893c1f86314e79d5de",
        "prover_destination_address": "tb1qt8rdur557nz338g3lekc6458pj0dl63c0s9904",
        
        # Verifier (dummy for now)
        "verifier_signature_private_key": "cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc",
        "verifier_signature_public_key": "03999269c93633303d8f5173bc017e5046f933053c59ebdde6bb3dd8d8de0528ba",
        "verifier_destination_address": "tb1qyvsy6ypssxmqmdzthzua3qwupkey90p3cdeuxx",
        
        # Fees
        "step_fees_satoshis": 1000,
    }
    
    print("=" * 60)
    print("BITVMX SETUP/FUND ENDPOINT")
    print("=" * 60)
    
    # Health check
    health = requests.get(f"{API_BASE}/healthcheck", timeout=2)
    print(f"✅ Prover service: {health.json()}")
    
    # Call /api/v1/setup/fund
    print("\n📡 Calling /api/v1/setup/fund...")
    response = requests.post(
        f"{API_BASE}/api/v1/setup/fund",
        json=setup_input,
        timeout=120
    )
    
    if response.status_code == 200:
        result = response.json()
        print(f"\n✅ SUCCESS!")
        print(f"   Response: {json.dumps(result, indent=2)[:500]}")
        
        # Check for setup_uuid
        if "setup_uuid" in result:
            print(f"\n   Setup UUID: {result['setup_uuid']}")
        
        # Check for funding address
        if "funding_address" in result:
            print(f"   Funding address: {result['funding_address']}")
            print(f"\n💡 Send funds to this address to complete setup")
            
        return True
    else:
        print(f"\n❌ Failed: {response.status_code}")
        print(f"   Response: {response.text[:500]}")
        return False

if __name__ == "__main__":
    main()