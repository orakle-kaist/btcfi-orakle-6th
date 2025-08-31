#!/usr/bin/env python3
"""
Use existing setup to broadcast prover transaction
Using setup: 78fd8d6e-b3f4-468d-8411-2bf609662add
"""
import json
import os
import sys
import hashlib

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from blockchain_query_services.services.mutinynet_query_service import (
    MutinynetQueryService,
)

def main():
    # Setup UUID
    setup_uuid = "78fd8d6e-b3f4-468d-8411-2bf609662add"
    prover_dir = f"prover_files/{setup_uuid}"
    
    print("=" * 60)
    print(f"BROADCASTING PROVER TX FROM EXISTING SETUP")
    print("=" * 60)
    print(f"\nSetup UUID: {setup_uuid}")
    print(f"Directory: {prover_dir}/")
    
    # Check if files exist
    signed_tx_file = f"{prover_dir}/signed_transactions.json"
    verifier_dto_file = f"{prover_dir}/bitvmx_protocol_verifier_dto.json"
    
    if not os.path.exists(signed_tx_file):
        print(f"\n❌ Error: {signed_tx_file} not found")
        return False
        
    if not os.path.exists(verifier_dto_file):
        print(f"\n❌ Error: {verifier_dto_file} not found")
        return False
    
    # Load signed transactions
    print(f"\n📄 Loading signed transactions...")
    with open(signed_tx_file, 'r') as f:
        signed_data = json.load(f)
    
    print(f"   - Kickoff TX: {len(signed_data.get('kickoff_tx', ''))} bytes")
    print(f"   - Hash TXs: {len(signed_data.get('hash_transaction', []))} transactions")
    
    # Load verifier DTO (for reference)
    print(f"\n📄 Loading verifier DTO...")
    with open(verifier_dto_file, 'r') as f:
        verifier_data = json.load(f)
    
    print(f"   - Protocol version: {verifier_data.get('version', 'unknown')}")
    
    # Extract kickoff transaction
    kickoff_tx_hex = signed_data.get('kickoff_tx', '')
    if not kickoff_tx_hex:
        print("\n❌ Error: No kickoff_tx found in signed_transactions.json")
        return False
    
    print(f"\n📡 Broadcasting prover kickoff transaction...")
    print(f"   TX size: {len(kickoff_tx_hex) // 2} bytes")
    
    try:
        # Initialize blockchain query service
        blockchain_service = MutinynetQueryService()
        
        # Direct broadcast using the hex string
        result = blockchain_service.post_raw_transaction(kickoff_tx_hex)
        
        if result:
            print(f"\n✅ SUCCESS! Transaction broadcast!")
            print(f"   TXID: {result}")
            print(f"   Explorer: https://mutinynet.com/tx/{result}")
            return True
        else:
            print(f"\n❌ Broadcast failed - no TXID returned")
            
            try:
                # Calculate TXID from raw hex
                tx_bytes = bytes.fromhex(kickoff_tx_hex)
                txid = hashlib.sha256(hashlib.sha256(tx_bytes).digest()).digest()[::-1].hex()
                print(f"\n   Calculated TXID: {txid}")
                
                # Check if transaction already exists
                existing_tx = blockchain_service.get_transaction(txid)
                if existing_tx:
                    print(f"   ℹ️ Transaction already broadcast!")
                    print(f"   Explorer: https://mutinynet.com/tx/{txid}")
                    return True
            except Exception as e:
                print(f"   Debug error: {e}")
                
            return False
            
    except Exception as e:
        print(f"\n❌ Error broadcasting: {e}")
        
        # Debug: Print first 200 chars of tx
        print(f"\n   Debug - TX hex (first 200 chars):")
        print(f"   {kickoff_tx_hex[:200]}...")
        
        return False

if __name__ == "__main__":
    success = main()
    if success:
        print("\n🎉 Prover transaction successfully broadcast!")
        print("   Next step: Wait for verifier challenge")
    else:
        print("\n⚠️ Failed to broadcast prover transaction")
        print("   Check the error messages above")