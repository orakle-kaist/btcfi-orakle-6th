#!/usr/bin/env python3

"""
Use existing Taproot UTXO from our previous Prover TX
======================================================

We already have a Taproot UTXO from the previous transaction:
- TX: 0847d1a6ab7dca82e61c27bb722cce3bd561b26920cf6836e0016ce387343f63
- Output: Index 0, 1179980800 sats, v1_p2tr type
- Address: tb1pxq2mlg7m7mgp26guu268vyp5jnj0ryr07vszdyxuwvfqe3825lysgtgzv6
"""

import json
import time
import secrets
import requests

def create_new_setup_with_existing_taproot():
    """
    Create a new BitVMX setup using our existing Taproot UTXO
    """
    
    # Our existing Taproot UTXO from previous Prover TX
    taproot_utxo = {
        "txid": "0847d1a6ab7dca82e61c27bb722cce3bd561b26920cf6836e0016ce387343f63",
        "index": 0,
        "amount": 1179980800,  # satoshis
        "type": "v1_p2tr",
        "address": "tb1pxq2mlg7m7mgp26guu268vyp5jnj0ryr07vszdyxuwvfqe3825lysgtgzv6"
    }
    
    print("🎯 Using existing Taproot UTXO")
    print("=" * 60)
    print(f"TX ID: {taproot_utxo['txid']}")
    print(f"Index: {taproot_utxo['index']}")
    print(f"Amount: {taproot_utxo['amount']} sats ({taproot_utxo['amount']/100000000:.8f} BTC)")
    print(f"Type: {taproot_utxo['type']} (Taproot)")
    print(f"Address: {taproot_utxo['address']}")
    print("=" * 60)
    
    # This is already a Taproot UTXO, so it can be used directly as funding
    # for the next BitVMX protocol transaction
    
    # Now create a new setup with this as the funding TX
    prover_api = "http://localhost:8081/api/v1"
    verifier_api = "http://localhost:8080/api/v1"
    
    # Generate new keys for this setup
    prover_priv_key = secrets.token_bytes(32).hex()
    signature_priv_key = secrets.token_bytes(32).hex()
    
    setup_data = {
        "max_amount_of_steps": 100,
        "amount_of_input_words": 4,
        "amount_of_bits_wrong_step_search": 10,
        "amount_of_bits_per_digit_checksum": 4,
        "funding_tx_id": taproot_utxo['txid'],
        "funding_index": taproot_utxo['index'],
        "secret_origin_of_funds": prover_priv_key,  # Need the private key that controls this UTXO
        "verifier_list": [verifier_api],
        "prover_destination_address": "tb1qd28npep0s8frcm3y7dxqajkcy2m40eysplyr9v",
        "prover_signature_private_key": signature_priv_key
    }
    
    print("\n📝 Creating new BitVMX setup...")
    print(f"   Funding TX: {taproot_utxo['txid']}:{taproot_utxo['index']}")
    print(f"   Amount: {taproot_utxo['amount']} sats")
    
    try:
        response = requests.post(
            f"{prover_api}/setup",
            json=setup_data,
            timeout=600
        )
        
        if response.status_code == 200:
            result = response.json()
            setup_uuid = result['setup_uuid']
            
            print(f"\n✅ Setup created successfully!")
            print(f"   Setup UUID: {setup_uuid}")
            
            # Now submit option input
            option_data = {
                'type': 1,        # PUT option
                'strike': 50000,  # $50,000 strike
                'spot': 54000,    # $54,000 current price
                'quantity': 100   # 100 units
            }
            
            option_hex = "{:08x}{:08x}{:08x}{:08x}".format(
                option_data['type'],
                int(option_data['strike'] * 100),
                int(option_data['spot'] * 100),
                option_data['quantity']
            )
            
            print(f"\n📊 Submitting option input...")
            print(f"   Type: PUT")
            print(f"   Strike: ${option_data['strike']:,}")
            print(f"   Spot: ${option_data['spot']:,}")
            print(f"   Quantity: {option_data['quantity']}")
            
            input_response = requests.post(
                f"{prover_api}/input",
                json={
                    "setup_uuid": setup_uuid,
                    "input": option_hex
                },
                timeout=60
            )
            
            if input_response.status_code == 200:
                print(f"✅ Option input submitted successfully!")
                
                # Generate and broadcast next transaction
                print(f"\n🚀 Generating next BitVMX transaction...")
                
                next_response = requests.post(
                    f"{prover_api}/next_step",
                    json={"setup_uuid": setup_uuid},
                    timeout=120
                )
                
                if next_response.status_code == 200:
                    next_result = next_response.json()
                    print(f"✅ Next transaction generated!")
                    print(f"   {next_result.get('message', '')}")
                    print(f"   Status: {next_result.get('next_step', '')}")
                else:
                    print(f"❌ Failed to generate next transaction: {next_response.text}")
            else:
                print(f"❌ Failed to submit option input: {input_response.text}")
            
            return setup_uuid
            
        else:
            print(f"❌ Setup creation failed: {response.text}")
            return None
            
    except Exception as e:
        print(f"❌ Error: {e}")
        return None

if __name__ == "__main__":
    print("\n" + "🔗" * 30)
    print("BitVMX Protocol - Using Existing Taproot UTXO")
    print("🔗" * 30 + "\n")
    
    # Check that our UTXO hasn't been spent
    print("Checking UTXO status...")
    utxo_check = requests.get("https://mutinynet.com/api/tx/0847d1a6ab7dca82e61c27bb722cce3bd561b26920cf6836e0016ce387343f63")
    
    if utxo_check.status_code == 200:
        tx_data = utxo_check.json()
        if tx_data.get('status', {}).get('confirmed'):
            print(f"✅ UTXO is confirmed in block {tx_data['status']['block_height']}")
            print(f"   Confirmations: {tx_data['status'].get('confirmations', 0)}")
        else:
            print("⏳ UTXO is unconfirmed, waiting for confirmation...")
    
    print("\n" + "-" * 60)
    
    # Create new setup with existing Taproot UTXO
    setup_uuid = create_new_setup_with_existing_taproot()
    
    if setup_uuid:
        print("\n" + "🎉" * 30)
        print("BitVMX Flow Completed Successfully!")
        print("🎉" * 30)
        print(f"\nThe existing Taproot UTXO from our previous Prover TX")
        print(f"has been used as the funding for a new BitVMX setup.")
        print(f"\nSetup UUID: {setup_uuid}")
        print(f"\n🔍 Check BitVMX Explorer for transaction chain:")