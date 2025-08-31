#!/usr/bin/env python3
"""
Simple broadcast of prover transaction using requests
"""
import json
import os
import hashlib
import requests

def main():
    # Setup UUID
    setup_uuid = "78fd8d6e-b3f4-468d-8411-2bf609662add"
    prover_dir = f"prover_files/{setup_uuid}"
    
    print("=" * 60)
    print(f"SIMPLE PROVER TX BROADCAST")
    print("=" * 60)
    print(f"\nSetup UUID: {setup_uuid}")
    
    # Load signed transactions
    signed_tx_file = f"{prover_dir}/signed_transactions.json"
    if not os.path.exists(signed_tx_file):
        print(f"\n❌ Error: {signed_tx_file} not found")
        return False
    
    print(f"\n📄 Loading signed transactions...")
    with open(signed_tx_file, 'r') as f:
        signed_data = json.load(f)
    
    # Get the first transaction (hash_result_tx is the kickoff)
    kickoff_tx_hex = signed_data.get('hash_result_tx', '')
    if not kickoff_tx_hex:
        # Try trigger_protocol_tx as alternative
        kickoff_tx_hex = signed_data.get('trigger_protocol_tx', '')
        if not kickoff_tx_hex:
            print("\n❌ Error: No kickoff transaction found")
            print("   Available keys:", list(signed_data.keys()))
            return False
        print("   Using trigger_protocol_tx as kickoff")
    
    print(f"   - Kickoff TX size: {len(kickoff_tx_hex) // 2} bytes")
    
    # Calculate TXID
    tx_bytes = bytes.fromhex(kickoff_tx_hex)
    txid = hashlib.sha256(hashlib.sha256(tx_bytes).digest()).digest()[::-1].hex()
    print(f"   - Calculated TXID: {txid}")
    
    # Check if already broadcast
    print(f"\n🔍 Checking if already broadcast...")
    check_url = f"https://mutinynet.com/api/tx/{txid}"
    try:
        response = requests.get(check_url, timeout=5)
        if response.status_code == 200:
            print(f"   ℹ️ Transaction already broadcast!")
            print(f"   Explorer: https://mutinynet.com/tx/{txid}")
            return True
    except:
        pass
    
    # Broadcast transaction
    print(f"\n📡 Broadcasting transaction...")
    
    # Try mempool.space API
    broadcast_url = "https://mutinynet.com/api/tx"
    try:
        response = requests.post(
            broadcast_url,
            data=kickoff_tx_hex,
            headers={'Content-Type': 'text/plain'},
            timeout=10
        )
        
        if response.status_code == 200:
            result_txid = response.text.strip()
            print(f"\n✅ SUCCESS! Transaction broadcast!")
            print(f"   TXID: {result_txid}")
            print(f"   Explorer: https://mutinynet.com/tx/{result_txid}")
            return True
        else:
            print(f"\n❌ Broadcast failed: {response.status_code}")
            print(f"   Response: {response.text[:200]}")
            
    except Exception as e:
        print(f"\n❌ Error: {e}")
    
    # Try alternative broadcast endpoint
    print(f"\n🔄 Trying alternative broadcast method...")
    alt_url = "https://mutinynet.com/api/broadcast"
    try:
        response = requests.post(
            alt_url,
            json={"tx": kickoff_tx_hex},
            timeout=10
        )
        
        if response.status_code == 200:
            result = response.json()
            print(f"\n✅ SUCCESS! Transaction broadcast!")
            print(f"   Result: {result}")
            return True
        else:
            print(f"   Failed: {response.status_code}")
            
    except Exception as e:
        print(f"   Error: {e}")
    
    return False

if __name__ == "__main__":
    success = main()
    if success:
        print("\n🎉 Prover transaction successfully broadcast!")
    else:
        print("\n⚠️ Failed to broadcast transaction")
        print("   You may need to use Bitcoin Core or Electrum to broadcast")