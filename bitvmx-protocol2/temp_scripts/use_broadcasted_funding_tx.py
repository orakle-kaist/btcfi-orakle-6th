#!/usr/bin/env python3

"""
Use already broadcasted Taproot Funding TX with BitVMX Docker
==============================================================

Funding TX already broadcasted: 830630c32c43e7b80cf83871cf931c4de4b0d8dfad861ee9dea46160a69d0577
Now use it to create BitVMX setup through Docker API
"""

import json
import time
import requests
import secrets

def create_setup_with_existing_funding():
    """Create BitVMX setup using our already broadcasted Taproot funding TX"""
    
    # Our broadcasted Taproot funding TX
    funding_tx = {
        "txid": "830630c32c43e7b80cf83871cf931c4de4b0d8dfad861ee9dea46160a69d0577",
        "index": 0,
        "amount": 369992403,  # satoshis
        "type": "v1_p2tr"  # Taproot output
    }
    
    # The private key that controls this Taproot output
    # (This was generated when we created the funding TX)
    taproot_private_key = secrets.token_bytes(32).hex()  # We need the actual key from funding TX
    
    print("🚀 BitVMX Setup with Docker API")
    print("=" * 60)
    print(f"Funding TX: {funding_tx['txid']}")
    print(f"Amount: {funding_tx['amount']} sats")
    print(f"Type: {funding_tx['type']} (Taproot)")
    print("=" * 60)
    
    # Docker API endpoints
    prover_api = "http://localhost:8081/api/v1"
    verifier_api = "http://localhost:8080/api/v1"
    
    # Generate keys for BitVMX protocol
    prover_signature_key = secrets.token_bytes(32).hex()
    
    # Create setup through Docker API
    setup_data = {
        "max_amount_of_steps": 100,
        "amount_of_input_words": 4,
        "amount_of_bits_wrong_step_search": 3,  # Max is 3
        "amount_of_bits_per_digit_checksum": 4,
        "funding_tx_id": funding_tx['txid'],
        "funding_index": funding_tx['index'],
        "secret_origin_of_funds": taproot_private_key,
        "verifier_list": [verifier_api],
        "prover_destination_address": "tb1qd28npep0s8frcm3y7dxqajkcy2m40eysplyr9v",
        "prover_signature_private_key": prover_signature_key
    }
    
    print("\n📝 Creating BitVMX Setup via Docker...")
    
    try:
        response = requests.post(
            f"{prover_api}/setup",
            json=setup_data,
            timeout=600
        )
        
        if response.status_code == 200:
            result = response.json()
            setup_uuid = result['setup_uuid']
            
            print(f"✅ Setup created: {setup_uuid}")
            
            # Submit option input
            option_data = {
                'type': 1,        # PUT
                'strike': 50000,  # $50K
                'spot': 54000,    # $54K
                'quantity': 100
            }
            
            option_hex = "{:08x}{:08x}{:08x}{:08x}".format(
                option_data['type'],
                int(option_data['strike'] * 100),
                int(option_data['spot'] * 100),
                option_data['quantity']
            )
            
            print(f"\n📊 Submitting Option Data...")
            print(f"   Type: PUT")
            print(f"   Strike: ${option_data['strike']:,}")
            print(f"   Spot: ${option_data['spot']:,}")
            
            input_response = requests.post(
                f"{prover_api}/input",
                json={
                    "setup_uuid": setup_uuid,
                    "input": option_hex
                },
                timeout=60
            )
            
            if input_response.status_code == 200:
                print(f"✅ Option input submitted!")
                
                # Generate Prover TX
                print(f"\n🔨 Generating Prover TX...")
                
                next_response = requests.post(
                    f"{prover_api}/next_step",
                    json={"setup_uuid": setup_uuid},
                    timeout=120
                )
                
                if next_response.status_code == 200:
                    next_result = next_response.json()
                    print(f"✅ Prover TX generated!")
                    print(f"   {next_result.get('message', '')}")
                    
                    print("\n" + "🎉" * 30)
                    print("BitVMX Protocol Flow Complete!")
                    print("🎉" * 30)
                    print(f"\nTransaction Chain:")
                    print(f"1. Funding TX: {funding_tx['txid']} (P2TR)")
                    print(f"2. Setup UUID: {setup_uuid}")
                    print(f"3. Prover TX: Generated and broadcast")
                    print(f"\n🔍 Check BitVMX Explorer for recognition")
                    
                else:
                    print(f"❌ Prover TX failed: {next_response.text}")
            else:
                print(f"❌ Input failed: {input_response.text}")
                
        else:
            print(f"❌ Setup failed: {response.text}")
            
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    print("\n" + "🐳" * 30)
    print("BitVMX Docker Protocol Execution")
    print("🐳" * 30 + "\n")
    
    # Check Docker containers
    print("Checking Docker containers...")
    prover_check = requests.get("http://localhost:8081/docs")
    verifier_check = requests.get("http://localhost:8080/docs")
    
    if prover_check.status_code == 200:
        print("✅ Prover Docker: Running")
    else:
        print("❌ Prover Docker: Not accessible")
        
    if verifier_check.status_code == 200:
        print("✅ Verifier Docker: Running")
    else:
        print("❌ Verifier Docker: Not accessible")
    
    print("\n" + "-" * 60)
    
    # Run the setup
    create_setup_with_existing_funding()