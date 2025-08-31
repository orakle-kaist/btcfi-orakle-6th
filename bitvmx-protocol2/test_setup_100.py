#!/usr/bin/env python3
"""Test setup API with 100 steps and optimized transaction generation."""

import requests
import json
import time
from datetime import datetime

# Configuration
PROVER_URL = "http://localhost:8080"
VERIFIER_URL = "http://localhost:8081"

# Test data with 100 steps
setup_data = {
    "n0": "57896044618658097711785492504343953926634992332820282019728792003956564819947",
    "n1": "57896044618658097711785492504343953926634992332820282019728792003956564819948",
    "prover_public_key": "b882af3fb540e1c2530d3d9e11993f206bb7626e9cfe19a03e7e42c75e19ad59",
    "input_hex": "a2010203",
    "max_amount_of_steps": 100,  # 100 steps for testing
    "funding_tx_id": "f8cc674288d0b039e41a6829c8bbd1b6a7096e084b431610f23c9a0bc37dcffd",
    "funding_index": 0,
    "funding_amount": 10000000,
    "step_fees": 3000,
    "amount_of_steps_in_search_choice_phase": 100,
    "amount_of_bits_wrong_step_search": 2,
    "secret_origin_of_funds": "d8a1e1224e63135765bde9dc8a2c8e403eee8be73d3589d58c5ddbf9dce3fdf4",
    "prover_destination_address": "tb1qt8rdur557nz338g3lekc6458pj0dl63c0s9904",
    "verifier_destination_address": "tb1q8fg5jrspc7fn8jvpe5tfr7e5dlwvsh6xw8cq4j",
    "prover_signature_private_key": "d8a1e1224e63135765bde9dc8a2c8e403eee8be73d3589d58c5ddbf9dce3fdf4",
    "prover_signature_public_key": "03bf751f0d2d22e6f0163c9acaa14ae04e6e1a004cb4a24d893c1f86314e79d5de",
    "amount_of_input_words": 1,
    "amount_of_output_words": 2,
    "elf_file_name": "btcfi_ebreak.elf"
}

def test_setup():
    """Test setup with 100 steps."""
    print(f"\n🚀 Testing setup with {setup_data['max_amount_of_steps']} steps")
    print(f"⏰ Started at: {datetime.now().strftime('%H:%M:%S')}")
    
    # Step 1: Call prover setup
    print("\n📤 Step 1: Calling prover setup...")
    start_time = time.time()
    
    try:
        response = requests.post(
            f"{PROVER_URL}/api/v1/setup",
            json=setup_data,
            timeout=600  # 10 minute timeout
        )
        
        elapsed = time.time() - start_time
        print(f"✅ Prover responded in {elapsed:.1f} seconds")
        
        if response.status_code == 200:
            prover_result = response.json()
            print(f"✅ Setup ID: {prover_result['setup_uuid']}")
            
            # Extract verifier data
            verifier_data = {
                "bitvmx_protocol_setup_properties_dto": prover_result["bitvmx_protocol_setup_properties_dto"]
            }
            
            # Step 2: Call verifier
            print("\n📤 Step 2: Calling verifier public keys generation...")
            start_time = time.time()
            
            verifier_response = requests.post(
                f"{VERIFIER_URL}/api/v1/public_keys",
                json=verifier_data,
                timeout=600  # 10 minute timeout
            )
            
            elapsed = time.time() - start_time
            print(f"✅ Verifier responded in {elapsed:.1f} seconds")
            
            if verifier_response.status_code == 200:
                print("✅ Verifier public keys generated successfully!")
                verifier_result = verifier_response.json()
                
                # Show minimal result info
                if "verifier_public_key" in verifier_result:
                    print(f"   Verifier public key: {verifier_result['verifier_public_key'][:16]}...")
                
                print(f"\n✅ COMPLETE SETUP SUCCESS WITH {setup_data['max_steps']} STEPS!")
                print(f"⏰ Finished at: {datetime.now().strftime('%H:%M:%S')}")
                return True
            else:
                print(f"❌ Verifier error: {verifier_response.status_code}")
                print(f"   Response: {verifier_response.text[:500]}")
                return False
                
        else:
            print(f"❌ Prover error: {response.status_code}")
            print(f"   Response: {response.text[:500]}")
            return False
            
    except requests.exceptions.Timeout:
        elapsed = time.time() - start_time
        print(f"❌ Timeout after {elapsed:.1f} seconds")
        return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

if __name__ == "__main__":
    print("=" * 60)
    print("BitVMX Setup Test with 100 Steps (Optimized)")
    print("=" * 60)
    
    success = test_setup()
    
    if success:
        print("\n🎉 All tests passed!")
    else:
        print("\n❌ Test failed")