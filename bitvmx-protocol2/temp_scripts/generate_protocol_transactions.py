#!/usr/bin/env python3

import json
import os
import sys
from pathlib import Path

# Add the bitvmx_protocol_library to path
sys.path.insert(0, str(Path(__file__).parent))

from bitvmx_protocol_library.transaction_generation.services import generate_bitvmx_protocol_transactions_service
from bitvmx_protocol_library.transaction_generation.entities import BitVMXTransactionGenerator

def main():
    setup_uuid = "ce08932e-0f17-4e33-b91e-21689a5198ce"
    
    # Load setup data
    setup_path = f"prover_files/{setup_uuid}/setup.json"
    with open(setup_path, 'r') as f:
        setup_data = json.load(f)
    
    # Load option data  
    option_data = {
        "option_type": 1,  # PUT
        "strike_price": 50000,
        "spot_price": 54000,
        "quantity": 100
    }
    
    print(f"Generating BitVMX protocol transactions for setup: {setup_uuid}")
    print(f"Option data: {option_data}")
    
    # Initialize the transaction generator
    generator = BitVMXTransactionGenerator(setup_uuid)
    
    # Generate all protocol transactions
    transactions = generator.generate_all_transactions(option_data)
    
    # Save transactions
    output_dir = f"prover_files/{setup_uuid}"
    os.makedirs(output_dir, exist_ok=True)
    
    transactions_file = f"{output_dir}/protocol_transactions.json"
    with open(transactions_file, 'w') as f:
        json.dump(transactions, f, indent=2)
    
    print(f"Protocol transactions generated and saved to: {transactions_file}")
    
    # Extract and save the prover transaction (hash_result_tx)
    if 'hash_result_tx' in transactions:
        prover_tx = {
            "hash_result_tx": transactions['hash_result_tx'],
            "txid": transactions.get('hash_result_txid'),
            "option_data": option_data,
            "option_hex": f"{option_data['option_type']:08x}{option_data['strike_price']:08x}{option_data['spot_price']:08x}{option_data['quantity']:08x}",
            "funding_spent": f"{setup_data['funding_tx_id']}:{setup_data['funding_index']}"
        }
        
        prover_tx_file = f"{output_dir}/prover_tx.json"
        with open(prover_tx_file, 'w') as f:
            json.dump(prover_tx, f, indent=2)
        
        print(f"Prover transaction saved to: {prover_tx_file}")
        print(f"Transaction ID: {prover_tx.get('txid')}")

if __name__ == "__main__":
    main()