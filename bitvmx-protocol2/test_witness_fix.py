#!/usr/bin/env python3
import sys
sys.path.insert(0, '/Users/parkgeonwoo/oracle_vm/btcfi-orakle-6th/bitvmx-protocol2')

import json

# Check if witness was applied to search_hash_tx_list
with open('prover_files/a985e49a-2964-49f8-adbe-5087446ead70/signed_transactions.json', 'r') as f:
    data = json.load(f)

print("Checking witness data in search_hash_tx_list:")
for i, tx in enumerate(data.get('search_hash_tx_list', [])):
    # Check if transaction has witness (should be longer than base transaction)
    tx_len = len(tx)
    has_witness = tx_len > 400  # Witness adds significant length
    print(f"  Tx {i}: Length={tx_len}, Has witness={has_witness}")
    if has_witness:
        # Extract witness flag and count
        witness_flag_pos = tx.find('0001')  # Segwit marker
        if witness_flag_pos > 0:
            print(f"    - Witness flag found at position {witness_flag_pos}")
    else:
        print(f"    - NO WITNESS DATA (ends with {tx[-20:]})")

print("\nComparing with search_choice_tx_list:")
for i, tx in enumerate(data.get('search_choice_tx_list', [])):
    tx_len = len(tx)
    has_witness = tx_len > 400
    print(f"  Tx {i}: Length={tx_len}, Has witness={has_witness}")