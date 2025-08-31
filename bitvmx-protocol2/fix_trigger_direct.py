#!/usr/bin/env python3
"""
Directly fix the Trigger Protocol TX by replacing the signature with correct amount
"""
import sys
import os
import json

sys.path.insert(0, '/bitvmx-backend')

from bitcoinutils.setup import setup
from bitcoinutils.keys import PrivateKey
from bitcoinutils.constants import TAPROOT_SIGHASH_ALL
from bitcoinutils.transactions import Transaction, TxWitnessInput
from bitcoinutils.script import Script

setup('testnet')

def fix_trigger_signature():
    """Fix the Trigger Protocol TX signature"""
    
    setup_uuid = '60f1041f-1a8f-4e17-8181-44208f11b71c'
    CORRECT_AMOUNT = 149995912  # From Hash Result TX output
    
    print("🔧 Fixing Trigger Protocol TX Signature")
    print("=" * 50)
    
    # Load existing transactions
    prover_dir = f'/bitvmx-backend/prover_files/{setup_uuid}'
    
    # Try different paths for signed transactions
    signed_tx_path = None
    for filename in ['signed_transactions_old.json', 'signed_transactions_backup.json', 'signed_transactions_fixed.json']:
        path = os.path.join(prover_dir, filename)
        if os.path.exists(path):
            signed_tx_path = path
            break
    
    if not signed_tx_path:
        print("❌ No signed transactions found")
        return None
    
    with open(signed_tx_path, 'r') as f:
        signed_txs = json.load(f)
    
    print(f"✅ Loaded transactions from {os.path.basename(signed_tx_path)}")
    
    # Parse Trigger TX
    trigger_hex = signed_txs['trigger_protocol_tx']
    trigger_tx = Transaction.from_raw(trigger_hex)
    
    print(f"   Input: {trigger_tx.inputs[0].txid[:16]}...:{trigger_tx.inputs[0].txout_index}")
    
    # Load private key
    private_dto_path = os.path.join(prover_dir, 'bitvmx_protocol_verifier_private_dto.json')
    with open(private_dto_path, 'r') as f:
        private_dto = json.load(f)
    
    privkey = PrivateKey(b=bytes.fromhex(private_dto['prover_signature_private_key']))
    
    # Extract witness components from existing TX
    if trigger_tx.witnesses and len(trigger_tx.witnesses) > 0:
        existing_witness = trigger_tx.witnesses[0].stack
        
        # The witness structure should be:
        # [...halt_step_witnesses..., signature, script, control_block]
        # We need to preserve everything except the signature
        
        if len(existing_witness) >= 3:
            # Extract script and control block from the end
            control_block_hex = existing_witness[-1]
            script_hex = existing_witness[-2]
            old_signature = existing_witness[-3] if len(existing_witness) > 2 else None
            witnesses_before_sig = existing_witness[:-3] if len(existing_witness) > 3 else []
            
            print(f"✅ Extracted witness components:")
            print(f"   Witnesses before sig: {len(witnesses_before_sig)} items")
            print(f"   Script length: {len(script_hex)//2} bytes")
            print(f"   Control block length: {len(control_block_hex)//2} bytes")
            
            # Create the script object from hex
            script = Script.from_hex(script_hex)
            
            # Get the prevout script pubkey (Taproot output)
            # This should be the Hash Result TX output script
            # Format: OP_1 <32-byte-x-only-pubkey>
            prevout_script_hex = "51201be1c0509e7cf5531fbf92947bc6f7d4e9d47936d9c84f75d66b8954e653f3f3"
            prevout_script = Script.from_hex(prevout_script_hex)
            
            # Sign with correct amount
            print(f"\n🔐 Creating new signature with amount: {CORRECT_AMOUNT} sats")
            
            try:
                # Sign the transaction with script path
                new_signature = privkey.sign_taproot_input(
                    trigger_tx,
                    0,  # input index
                    [prevout_script],  # prevout script
                    [CORRECT_AMOUNT],  # CORRECT AMOUNT!
                    script_path=True,
                    tapleaf_script=script,
                    sighash=TAPROOT_SIGHASH_ALL,
                    tweak=False
                )
                
                print(f"✅ Generated new signature: {len(new_signature)} bytes")
                
                # Reconstruct witness
                new_witness_stack = witnesses_before_sig + [
                    new_signature,
                    script_hex,
                    control_block_hex
                ]
                
                trigger_tx.witnesses = [TxWitnessInput(new_witness_stack)]
                
                # Serialize
                new_trigger_hex = trigger_tx.serialize()
                
                print(f"\n✅ Transaction fixed:")
                print(f"   Size: {len(new_trigger_hex)//2} bytes")
                print(f"   TXID: {trigger_tx.get_txid()}")
                
                # Save
                signed_txs['trigger_protocol_tx'] = new_trigger_hex
                
                output_path = os.path.join(prover_dir, 'signed_transactions.json')
                with open(output_path, 'w') as f:
                    json.dump(signed_txs, f, indent=2)
                
                print(f"\n💾 Saved to signed_transactions.json")
                
                return new_trigger_hex
                
            except Exception as e:
                print(f"\n❌ Signing failed: {e}")
                import traceback
                traceback.print_exc()
                return None
        else:
            print("❌ Witness structure unexpected")
            return None
    else:
        print("❌ No witness in transaction")
        return None

if __name__ == "__main__":
    new_hex = fix_trigger_signature()
    
    if new_hex:
        print("\n✅ Success! Transaction is ready to broadcast")
        print("   Call /api/v1/next_step to broadcast")
    else:
        print("\n❌ Failed to fix signature")