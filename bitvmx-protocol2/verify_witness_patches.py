#!/usr/bin/env python3
"""
Verify that witness patches are correctly applied
"""

def check_patches():
    """Check if witness patches are applied to the necessary files"""
    
    print("=" * 60)
    print("CHECKING WITNESS PATCHES")
    print("=" * 60)
    
    patches_status = {}
    
    # Check apply_signatures_to_transactions_service.py
    print("\n1. Checking apply_signatures_to_transactions_service.py...")
    try:
        with open("bitvmx_protocol_library/transaction_generation/services/apply_signatures_to_transactions_service.py", "r") as f:
            content = f.read()
            
        # Check for search_hash patch
        if "WITNESS_FIX" in content or "tx.to_bytes(has_segwit=True).hex()" in content:
            print("   ✅ Patch found for search_hash_tx_list")
            patches_status['apply_search_hash'] = True
            
            # Check specific lines
            if "if tx.witnesses and len(tx.witnesses) > 0:" in content:
                print("      - Witness check present")
            if "serialized = tx.to_bytes(has_segwit=True).hex()" in content:
                print("      - Using to_bytes(has_segwit=True)")
        else:
            print("   ❌ Patch NOT found for search_hash_tx_list")
            patches_status['apply_search_hash'] = False
            
    except Exception as e:
        print(f"   ❌ Error reading file: {e}")
        patches_status['apply_search_hash'] = False
    
    # Check publish_hash_search_transaction_service.py
    print("\n2. Checking publish_hash_search_transaction_service.py...")
    try:
        with open("bitvmx_protocol_library/transaction_generation/services/publication_services/prover/publish_hash_search_transaction_service.py", "r") as f:
            content = f.read()
            
        if "WITNESS_FIX" in content or "tx.to_bytes(has_segwit=True).hex()" in content:
            print("   ✅ Patch found")
            patches_status['publish_hash'] = True
            
            # Check specific implementation
            if "if tx.witnesses and len(tx.witnesses) > 0:" in content:
                print("      - Witness check present")
            if "serialized = tx.to_bytes(has_segwit=True).hex()" in content:
                print("      - Using to_bytes(has_segwit=True)")
        else:
            print("   ❌ Patch NOT found")
            patches_status['publish_hash'] = False
            
    except Exception as e:
        print(f"   ❌ Error reading file: {e}")
        patches_status['publish_hash'] = False
    
    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    
    all_patched = all(patches_status.values())
    
    if all_patched:
        print("✅ All necessary patches are applied!")
        print("\nThe witness serialization should work correctly.")
        print("Transactions generated after these patches will include witness data.")
    else:
        print("❌ Some patches are missing:")
        for name, status in patches_status.items():
            if not status:
                print(f"   - {name}")
        
        print("\nTo fix, you need to apply the patches to serialize transactions with witness.")
    
    return all_patched

def verify_transaction_has_witness(tx_hex):
    """Check if a transaction hex has witness data"""
    
    # Check for witness marker (0x00 0x01 after version)
    # In hex: "02000000" (version 2) followed by "0001" for witness
    
    if len(tx_hex) < 20:
        return False, "Transaction too short"
    
    # Version is first 4 bytes (8 hex chars)
    version = tx_hex[:8]
    
    # Check for witness flag right after version
    has_witness_flag = tx_hex[8:12] == "0001"
    
    # Additional check: witness transactions are typically longer
    is_long_enough = len(tx_hex) > 400  # Rough estimate
    
    return has_witness_flag, f"Version={version}, Witness flag={'Yes' if has_witness_flag else 'No'}, Length={len(tx_hex)}"

def check_existing_transactions():
    """Check existing signed transactions for witness"""
    
    print("\n" + "=" * 60)
    print("CHECKING EXISTING TRANSACTIONS")
    print("=" * 60)
    
    import os
    import json
    
    # Check all existing setups
    prover_files = "prover_files"
    
    for setup_dir in os.listdir(prover_files):
        signed_file = os.path.join(prover_files, setup_dir, "signed_transactions.json")
        
        if os.path.exists(signed_file):
            print(f"\nSetup: {setup_dir}")
            
            try:
                with open(signed_file, "r") as f:
                    signed_txs = json.load(f)
                
                # Check search_hash_tx_list
                if "search_hash_tx_list" in signed_txs and signed_txs["search_hash_tx_list"]:
                    first_tx = signed_txs["search_hash_tx_list"][0]
                    if isinstance(first_tx, str):
                        has_witness, info = verify_transaction_has_witness(first_tx)
                        print(f"  search_hash_tx[0]: {info}")
                        if has_witness:
                            print("    ✅ Has witness!")
                        else:
                            print("    ❌ No witness")
                
                # Check search_choice_tx_list  
                if "search_choice_tx_list" in signed_txs and signed_txs["search_choice_tx_list"]:
                    first_tx = signed_txs["search_choice_tx_list"][0]
                    if isinstance(first_tx, str):
                        has_witness, info = verify_transaction_has_witness(first_tx)
                        print(f"  search_choice_tx[0]: {info}")
                        if has_witness:
                            print("    ✅ Has witness!")
                        else:
                            print("    ❌ No witness")
                            
            except Exception as e:
                print(f"  Error reading: {e}")

def main():
    # Check patches
    patches_ok = check_patches()
    
    # Check existing transactions
    check_existing_transactions()
    
    print("\n" + "=" * 60)
    print("NEXT STEPS")
    print("=" * 60)
    
    if patches_ok:
        print("✅ Patches are applied correctly.")
        print("\nTo generate new transactions with witness:")
        print("1. Create a new setup")
        print("2. Generate and sign transactions")
        print("3. The witness will be automatically included")
    else:
        print("❌ Apply the missing patches first")
        print("\nThe patches should modify tx.serialize() to:")
        print("  if tx.witnesses and len(tx.witnesses) > 0:")
        print("      serialized = tx.to_bytes(has_segwit=True).hex()")
        print("  else:")
        print("      serialized = tx.serialize()")
    
    return 0 if patches_ok else 1

if __name__ == "__main__":
    import sys
    sys.exit(main())