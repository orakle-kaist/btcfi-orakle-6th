#!/usr/bin/env python3
"""Create a real setup and broadcast funding transaction."""

import requests
import json
import time
from datetime import datetime

# Configuration
PROVER_URL = "http://localhost:8080"
VERIFIER_URL = "http://localhost:8081"

# Real setup data with 100 steps
setup_data = {
    "n0": "57896044618658097711785492504343953926634992332820282019728792003956564819947",
    "n1": "57896044618658097711785492504343953926634992332820282019728792003956564819948",
    "prover_public_key": "b882af3fb540e1c2530d3d9e11993f206bb7626e9cfe19a03e7e42c75e19ad59",
    "input_hex": "a2010203",
    "max_amount_of_steps": 100,  # 100 steps
    "funding_tx_id": "f8cc674288d0b039e41a6829c8bbd1b6a7096e084b431610f23c9a0bc37dcffd",
    "funding_index": 0,
    "funding_amount": 10000000,  # 0.1 BTC
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

def create_setup():
    """Create the setup."""
    print(f"\n🚀 Creating real setup with {setup_data['max_amount_of_steps']} steps...")
    print(f"⏰ Started at: {datetime.now().strftime('%H:%M:%S')}")
    
    # Step 1: Call prover setup
    print("\n📤 Step 1: Calling prover setup...")
    start_time = time.time()
    
    try:
        response = requests.post(
            f"{PROVER_URL}/api/v1/setup",
            json=setup_data,
            timeout=600
        )
        
        elapsed = time.time() - start_time
        print(f"✅ Prover responded in {elapsed:.1f} seconds")
        
        if response.status_code == 200:
            prover_result = response.json()
            setup_uuid = prover_result['setup_uuid']
            print(f"✅ Setup ID: {setup_uuid}")
            
            # Save setup UUID for later use
            with open("current_setup.json", "w") as f:
                json.dump({
                    "setup_uuid": setup_uuid,
                    "created_at": datetime.now().isoformat(),
                    "funding_tx_id": setup_data["funding_tx_id"],
                    "funding_index": setup_data["funding_index"],
                    "funding_amount": setup_data["funding_amount"],
                    "steps": setup_data["max_amount_of_steps"]
                }, f, indent=2)
            
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
                timeout=600
            )
            
            elapsed = time.time() - start_time
            print(f"✅ Verifier responded in {elapsed:.1f} seconds")
            
            if verifier_response.status_code == 200:
                print("✅ Verifier public keys generated successfully!")
                return setup_uuid
            else:
                print(f"❌ Verifier error: {verifier_response.status_code}")
                print(f"   Response: {verifier_response.text[:500]}")
                return None
                
        else:
            print(f"❌ Prover error: {response.status_code}")
            print(f"   Response: {response.text[:500]}")
            return None
            
    except requests.exceptions.Timeout:
        elapsed = time.time() - start_time
        print(f"❌ Timeout after {elapsed:.1f} seconds")
        return None
    except Exception as e:
        print(f"❌ Error: {e}")
        return None

def broadcast_funding():
    """Broadcast the funding transaction."""
    print("\n📡 Broadcasting funding transaction...")
    
    # Read the setup UUID
    try:
        with open("current_setup.json", "r") as f:
            setup_info = json.load(f)
            setup_uuid = setup_info["setup_uuid"]
    except FileNotFoundError:
        print("❌ No setup found. Create a setup first.")
        return False
    
    # Call the broadcast endpoint
    try:
        response = requests.post(
            f"{PROVER_URL}/api/v1/broadcast",
            json={"setup_uuid": setup_uuid},
            timeout=60
        )
        
        if response.status_code == 200:
            result = response.json()
            print("✅ Funding transaction broadcast successful!")
            
            if "funding_txid" in result:
                print(f"   Funding TXID: {result['funding_txid']}")
                print(f"   View on Mutinynet: https://mutinynet.com/tx/{result['funding_txid']}")
            
            if "hash_result_txid" in result:
                print(f"   Hash Result TXID: {result['hash_result_txid']}")
                print(f"   View on Mutinynet: https://mutinynet.com/tx/{result['hash_result_txid']}")
                
            return True
        else:
            print(f"❌ Broadcast error: {response.status_code}")
            print(f"   Response: {response.text[:500]}")
            return False
            
    except Exception as e:
        print(f"❌ Error broadcasting: {e}")
        return False

if __name__ == "__main__":
    print("=" * 60)
    print("BitVMX Real Setup and Funding Transaction Test")
    print(f"Steps: {setup_data['max_amount_of_steps']}")
    print("=" * 60)
    
    # Create the setup
    setup_uuid = create_setup()
    
    if setup_uuid:
        print(f"\n✅ Setup created successfully: {setup_uuid}")
        
        # Ask user if they want to broadcast
        print("\n" + "=" * 60)
        print("Ready to broadcast funding transaction!")
        print("This will spend the UTXO:")
        print(f"  - TXID: {setup_data['funding_tx_id']}")
        print(f"  - Index: {setup_data['funding_index']}")
        print(f"  - Amount: {setup_data['funding_amount']} sats (0.1 BTC)")
        print(f"  - Steps: {setup_data['max_amount_of_steps']}")
        print("=" * 60)
        
        answer = input("\nDo you want to broadcast? (yes/no): ").strip().lower()
        
        if answer == "yes":
            if broadcast_funding():
                print("\n🎉 Success! Check the transaction on Mutinynet explorer.")
            else:
                print("\n❌ Broadcast failed.")
        else:
            print("\n⏸️  Broadcast cancelled. Setup saved in current_setup.json")
    else:
        print("\n❌ Setup creation failed")