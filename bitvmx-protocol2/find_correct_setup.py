#!/usr/bin/env python3
"""
Find which setup created the Hash Result TX with tweaked key 1be3c050...
"""
import os
import json
import hashlib
from bitcoinutils.keys import PublicKey
from bitcoinutils.setup import setup

def compute_tweaked_key(internal_pubkey_hex, taptree_root):
    """Compute the tweaked output key using BIP-341 taproot tweak"""
    # Convert to PublicKey object
    internal_key = PublicKey(internal_pubkey_hex)
    
    # Compute taptweak = TaggedHash("TapTweak", internal_pubkey || merkle_root)
    tap_tweak_tag = hashlib.sha256(b"TapTweak").digest()
    internal_key_bytes = bytes.fromhex(internal_key.to_x_only_hex())
    
    if taptree_root:
        tweak_input = internal_key_bytes + bytes.fromhex(taptree_root)
    else:
        tweak_input = internal_key_bytes
    
    tap_tweak = hashlib.sha256(tap_tweak_tag + tap_tweak_tag + tweak_input).digest()
    
    # Apply tweak to internal key
    from coincurve import PublicKey as ECPublicKey
    internal_point = ECPublicKey(bytes.fromhex("02" + internal_key.to_x_only_hex()))
    
    # Compute Q = P + t*G
    import coincurve
    t = int.from_bytes(tap_tweak, 'big')
    G = coincurve.PublicKey.from_secret(bytes([1] * 31 + bytes([1])))  # Generator point
    
    # This is simplified - in practice we'd use proper point addition
    # For now, just return the internal key for debugging
    return internal_key.to_x_only_hex()

def scan_setups():
    """Scan all setup directories to find the one with matching tweaked key"""
    target_tweaked_key = "1be3c050df7cf568bf7f95167bc6f7d4e9d47936d9d09ef5ecd3a959e4b31fbf"
    
    # Scan prover_files directory
    prover_dir = "prover_files"
    if not os.path.exists(prover_dir):
        print(f"Directory {prover_dir} not found")
        return None
    
    for setup_dir in os.listdir(prover_dir):
        setup_path = os.path.join(prover_dir, setup_dir)
        if not os.path.isdir(setup_path):
            continue
        
        print(f"\nChecking setup: {setup_dir}")
        
        # Check for private key file
        private_key_file = os.path.join(setup_path, "bitvmx_protocol_verifier_private_dto.json")
        if os.path.exists(private_key_file):
            with open(private_key_file, 'r') as f:
                data = json.load(f)
                destroyed_key = data.get('destroyed_public_key')
                if destroyed_key:
                    print(f"  Found destroyed_public_key: {destroyed_key[:16]}...")
                    
                    # Check if this could produce our target
                    # For now, just check if we have transaction data
                    
        # Check for signed transactions
        signed_tx_file = os.path.join(setup_path, "signed_transactions.json")
        if os.path.exists(signed_tx_file):
            with open(signed_tx_file, 'r') as f:
                tx_data = json.load(f)
                if 'hash_result_tx' in tx_data:
                    # Parse the hash_result_tx to check its output
                    tx_hex = tx_data['hash_result_tx']
                    print(f"  Has hash_result_tx")
                    
                    # Extract witness output from tx
                    # This is a simplified check - look for the output script
                    if "1be3c050" in tx_hex:
                        print(f"  ✅ FOUND! Setup {setup_dir} contains matching output key!")
                        return setup_dir
    
    return None

def check_specific_setup(setup_uuid):
    """Check a specific setup in detail"""
    print(f"\n=== Checking setup {setup_uuid} ===")
    
    base_dir = f"prover_files/{setup_uuid}"
    
    # Check private key file
    private_key_file = f"{base_dir}/bitvmx_protocol_verifier_private_dto.json"
    if os.path.exists(private_key_file):
        with open(private_key_file, 'r') as f:
            data = json.load(f)
            print(f"Destroyed public key: {data.get('destroyed_public_key', 'Not found')}")
            print(f"Unspendable public key: {data.get('unspendable_public_key', 'Not found')}")
    
    # Check signed transactions
    signed_tx_file = f"{base_dir}/signed_transactions.json"
    if os.path.exists(signed_tx_file):
        with open(signed_tx_file, 'r') as f:
            tx_data = json.load(f)
            if 'hash_result_tx' in tx_data:
                tx_hex = tx_data['hash_result_tx']
                # Check if output contains our target key
                if "51201be3c050df7cf568bf7f95167bc6f7d4e9d47936d9d09ef5ecd3a959e4b31fbf" in tx_hex:
                    print("✅ This setup's hash_result_tx contains the target output!")
                    return True
    
    return False
if __name__ == "__main__":
    setup('testnet')

    print("🔍 Searching for setup that created Hash Result TX with tweaked key 1be3c050...")
    print("=" * 60)
    
    # First check the current setup
    current_setup = "60f1041f-1a8f-4e17-8181-44208f11b71c"
    if check_specific_setup(current_setup):
        print(f"\n✅ Current setup {current_setup} is the correct one!")
    else:
        print(f"\n❌ Current setup {current_setup} is NOT the match")
        
        # Scan all setups
        matching_setup = scan_setups()
        if matching_setup:
            print(f"\n✅ Found matching setup: {matching_setup}")
        else:
            print("\n❌ No matching setup found in prover_files")