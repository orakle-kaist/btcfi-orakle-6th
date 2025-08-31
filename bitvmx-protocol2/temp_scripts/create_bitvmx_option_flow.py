#!/usr/bin/env python3

"""
Complete BitVMX Option Flow Implementation
==========================================

This script implements the proper BitVMX protocol flow:
1. Create Taproot Funding TX (P2TR output)
2. Create Setup with the Taproot funding info  
3. Submit Option Input data
4. Generate and broadcast Prover TX (consuming Taproot UTXO)

This follows the "정석" (standard/proper) way as required by BitVMX Explorer.
"""

import json
import time
import secrets
import requests
import hashlib
from typing import Dict, Tuple, Optional
from bitcoinutils.setup import setup
from bitcoinutils.keys import PrivateKey, PublicKey
from bitcoinutils.transactions import Transaction, TxInput, TxOutput, TxWitnessInput
from bitcoinutils.script import Script

# Setup for Mutinynet
setup('testnet')

class BitVMXOptionFlow:
    def __init__(self):
        self.prover_api = "http://localhost:8081/api/v1"
        self.verifier_api = "http://localhost:8080/api/v1"
        self.mutinynet_api = "https://mutinynet.com/api"
        
    def step1_create_taproot_funding_tx(self, source_utxo: Dict) -> Dict:
        """
        Step 1: Create a Taproot Funding Transaction
        
        This creates a P2TR (Taproot) output that will be recognized
        by BitVMX Explorer as a proper funding transaction.
        """
        print("\n" + "="*60)
        print("STEP 1: Creating BitVMX Taproot Funding Transaction")
        print("="*60)
        
        # Generate Taproot keypair for the funding output
        taproot_priv_key = PrivateKey(b=secrets.token_bytes(32))
        taproot_pub_key = taproot_priv_key.get_public_key()
        
        # Source UTXO info (P2WPKH from wallet)
        source_txid = source_utxo['txid']
        source_index = source_utxo['index']
        source_amount = source_utxo['amount']
        source_priv_key = PrivateKey(secret_exponent=int(source_utxo['private_key'], 16))
        source_pub_key = source_priv_key.get_public_key()
        
        # Create Taproot output script (P2TR)
        taproot_internal_pubkey = taproot_pub_key.to_hex()[2:]  # x-only format
        taproot_script = Script(['OP_1', taproot_internal_pubkey])
        
        # Calculate output amount (minus fee)
        fee = 5000
        output_amount = source_amount - fee
        
        # Build transaction
        tx_input = TxInput(source_txid, source_index)
        tx_output = TxOutput(output_amount, taproot_script)
        tx = Transaction([tx_input], [tx_output], has_segwit=True)
        
        # Sign the P2WPKH input
        source_pkh = hashlib.new('ripemd160', 
                                hashlib.sha256(bytes.fromhex(source_pub_key.to_hex())).digest()).digest()
        script_code = Script(['OP_DUP', 'OP_HASH160', source_pkh.hex(), 'OP_EQUALVERIFY', 'OP_CHECKSIG'])
        
        sig = source_priv_key.sign_segwit_input(tx, 0, script_code, source_amount)
        witness = TxWitnessInput([sig, source_pub_key.to_hex()])
        tx.witnesses = [witness]
        
        funding_data = {
            "funding_tx_id": tx.get_txid(),
            "funding_index": 0,
            "funding_amount_satoshis": output_amount,
            "taproot_private_key": taproot_priv_key.to_bytes().hex(),
            "taproot_public_key": taproot_pub_key.to_hex(),
            "raw_transaction": tx.serialize(),
            "output_type": "v1_p2tr"  # This is what BitVMX Explorer looks for
        }
        
        # Save funding data to file for later use
        with open('taproot_funding_data.json', 'w') as f:
            json.dump(funding_data, f, indent=2)
        
        print(f"✅ Taproot Funding TX created: {funding_data['funding_tx_id']}")
        print(f"   Output: {output_amount} sats to P2TR address")
        print(f"   Type: {funding_data['output_type']} (Taproot)")
        print(f"   Private key saved to taproot_funding_data.json")
        
        return funding_data
    
    def step2_broadcast_funding_tx(self, funding_data: Dict) -> bool:
        """
        Step 2: Broadcast the Funding Transaction to Mutinynet
        """
        print("\n" + "="*60)
        print("STEP 2: Broadcasting Funding Transaction")
        print("="*60)
        
        url = f"{self.mutinynet_api}/tx"
        try:
            response = requests.post(url, data=funding_data['raw_transaction'])
            if response.status_code == 200:
                print(f"✅ Funding TX broadcast successfully!")
                print(f"   TX ID: {funding_data['funding_tx_id']}")
                print(f"   Explorer: https://mutinynet.com/tx/{funding_data['funding_tx_id']}")
                return True
            else:
                print(f"❌ Broadcast failed: {response.text}")
                return False
        except Exception as e:
            print(f"❌ Error broadcasting: {e}")
            return False
    
    def step3_create_bitvmx_setup(self, funding_data: Dict) -> Optional[str]:
        """
        Step 3: Create BitVMX Setup using the Taproot funding UTXO
        """
        print("\n" + "="*60)
        print("STEP 3: Creating BitVMX Setup")
        print("="*60)
        
        # Generate setup keys
        prover_priv_key = PrivateKey(b=secrets.token_bytes(32))
        prover_pub_key = prover_priv_key.get_public_key()
        
        setup_data = {
            "max_amount_of_steps": 100,
            "amount_of_input_words": 4,
            "amount_of_bits_wrong_step_search": 3,  # Maximum allowed is 3
            "amount_of_bits_per_digit_checksum": 4,
            "funding_tx_id": funding_data['funding_tx_id'],
            "funding_index": funding_data['funding_index'],
            "secret_origin_of_funds": funding_data['taproot_private_key'],
            "verifier_list": [self.verifier_api],
            "prover_destination_address": "tb1qd28npep0s8frcm3y7dxqajkcy2m40eysplyr9v",
            "prover_signature_private_key": prover_priv_key.to_bytes().hex(),
            "prover_signature_public_key": prover_pub_key.to_hex()
        }
        
        # Call setup endpoint
        try:
            response = requests.post(
                f"{self.prover_api}/setup",
                json=setup_data,
                timeout=600  # 10 minute timeout
            )
            
            if response.status_code == 200:
                result = response.json()
                setup_uuid = result['setup_uuid']
                print(f"✅ Setup created successfully!")
                print(f"   Setup UUID: {setup_uuid}")
                print(f"   Funding: {funding_data['funding_tx_id']}:{funding_data['funding_index']}")
                return setup_uuid
            else:
                print(f"❌ Setup creation failed: {response.text}")
                return None
                
        except Exception as e:
            print(f"❌ Error creating setup: {e}")
            return None
    
    def step4_submit_option_input(self, setup_uuid: str, option_data: Dict) -> bool:
        """
        Step 4: Submit Option Input Data
        """
        print("\n" + "="*60)
        print("STEP 4: Submitting Option Input")
        print("="*60)
        
        # Encode option data
        option_hex = "{:08x}{:08x}{:08x}{:08x}".format(
            option_data['type'],      # 0=CALL, 1=PUT
            int(option_data['strike'] * 100),   # Strike price in cents
            int(option_data['spot'] * 100),     # Spot price in cents  
            option_data['quantity']    # Quantity
        )
        
        input_data = {
            "setup_uuid": setup_uuid,
            "input": option_hex
        }
        
        try:
            response = requests.post(
                f"{self.prover_api}/input",
                json=input_data,
                timeout=60
            )
            
            if response.status_code == 200:
                print(f"✅ Option input submitted!")
                print(f"   Type: {'PUT' if option_data['type'] == 1 else 'CALL'}")
                print(f"   Strike: ${option_data['strike']:,}")
                print(f"   Spot: ${option_data['spot']:,}")
                print(f"   Quantity: {option_data['quantity']}")
                print(f"   Encoded: 0x{option_hex}")
                return True
            else:
                print(f"❌ Input submission failed: {response.text}")
                return False
                
        except Exception as e:
            print(f"❌ Error submitting input: {e}")
            return False
    
    def step5_generate_prover_tx(self, setup_uuid: str) -> Optional[Dict]:
        """
        Step 5: Generate and Broadcast Prover Transaction
        
        This consumes the Taproot UTXO and will be recognized by
        BitVMX Explorer as a proper Prover transaction.
        """
        print("\n" + "="*60)
        print("STEP 5: Generating Prover Transaction")
        print("="*60)
        
        try:
            # Trigger next step (generates prover tx)
            response = requests.post(
                f"{self.prover_api}/next_step",
                json={"setup_uuid": setup_uuid},
                timeout=120
            )
            
            if response.status_code == 200:
                result = response.json()
                print(f"✅ Prover TX generated and broadcast!")
                print(f"   Message: {result.get('message', 'Success')}")
                print(f"   Next Step: {result.get('next_step', 'await_confirmations')}")
                return result
            else:
                print(f"❌ Prover TX generation failed: {response.text}")
                return None
                
        except Exception as e:
            print(f"❌ Error generating Prover TX: {e}")
            return None
    
    def run_complete_flow(self):
        """
        Run the complete BitVMX option flow
        """
        print("\n" + "🚀" * 30)
        print("BitVMX Option Protocol - Complete Flow")
        print("🚀" * 30)
        
        # Use existing wallet UTXO (confirmed unspent)
        source_utxo = {
            'txid': '84b056f743ee50d6668c207c3edf022768b632d6a72f2e974104c6498fd6c7cd',
            'index': 0,
            'amount': 369994867,  # 3.69994867 BTC
            'private_key': 'd8a1e1224e63135765bde9dc8a2c8e403eee8be73d3589d58c5ddbf9dce3fdf4'  # From our setup.json
        }
        
        # Option parameters
        option_data = {
            'type': 1,        # PUT option
            'strike': 50000,  # $50,000 strike
            'spot': 54000,    # $54,000 current price
            'quantity': 100   # 100 units
        }
        
        # Step 1: Create Taproot funding TX
        funding_data = self.step1_create_taproot_funding_tx(source_utxo)
        
        # Step 2: Broadcast funding TX
        if not self.step2_broadcast_funding_tx(funding_data):
            print("❌ Flow aborted: Could not broadcast funding TX")
            return
        
        # Wait for confirmation
        print("\n⏳ Waiting for funding TX confirmation...")
        time.sleep(10)
        
        # Step 3: Create BitVMX setup
        setup_uuid = self.step3_create_bitvmx_setup(funding_data)
        if not setup_uuid:
            print("❌ Flow aborted: Could not create setup")
            return
        
        # Step 4: Submit option input
        if not self.step4_submit_option_input(setup_uuid, option_data):
            print("❌ Flow aborted: Could not submit option input")
            return
        
        # Step 5: Generate and broadcast Prover TX
        prover_result = self.step5_generate_prover_tx(setup_uuid)
        if not prover_result:
            print("❌ Flow aborted: Could not generate Prover TX")
            return
        
        # Success!
        print("\n" + "🎉" * 30)
        print("BitVMX Option Flow Completed Successfully!")
        print("🎉" * 30)
        print(f"\n📋 Summary:")
        print(f"   1. Funding TX: {funding_data['funding_tx_id']} (P2TR)")
        print(f"   2. Setup UUID: {setup_uuid}")
        print(f"   3. Option: PUT ${option_data['strike']:,} (Spot: ${option_data['spot']:,})")
        print(f"   4. Status: Prover TX broadcast, awaiting confirmations")
        print(f"\n🔍 Check BitVMX Explorer:")
        print(f"   https://bitvmx.org/tx/{funding_data['funding_tx_id']}")

if __name__ == "__main__":
    flow = BitVMXOptionFlow()
    flow.run_complete_flow()