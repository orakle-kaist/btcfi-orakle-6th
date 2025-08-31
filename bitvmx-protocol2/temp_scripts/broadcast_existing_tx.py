#!/usr/bin/env python3
"""
Broadcast existing signed transaction
"""
import json
import requests

def main():
    # Read the signed transactions
    import subprocess
    result = subprocess.run([
        'docker', 'exec', 'bitvmx-protocol2-prover-backend-1',
        'cat', '/bitvmx-backend/prover_files/208f19ab-a92f-4013-a02d-7f285980fb1e/signed_transactions.json'
    ], capture_output=True, text=True)
    
    data = json.loads(result.stdout)
    
    # Get the hash_result_tx
    tx_hex = data['hash_result_tx']
    
    print("=" * 60)
    print("BROADCASTING EXISTING PROVER TRANSACTION")
    print("=" * 60)
    print(f"Transaction type: hash_result_tx")
    print(f"Hex length: {len(tx_hex)} chars ({len(tx_hex)//2} bytes)")
    print(f"First 100 chars: {tx_hex[:100]}...")
    
    # Broadcast to Mutinynet
    print("\n📡 Broadcasting to Mutinynet...")
    response = requests.post(
        "https://mutinynet.com/api/tx",
        data=tx_hex,
        headers={'Content-Type': 'text/plain'},
        timeout=10
    )
    
    if response.status_code == 200:
        txid = response.text.strip()
        print(f"✅ SUCCESS!")
        print(f"   TXID: {txid}")
        print(f"   Explorer: https://mutinynet.com/tx/{txid}")
        return True
    else:
        print(f"❌ Failed: {response.status_code}")
        print(f"   Response: {response.text[:500]}")
        
        # Try to decode the error
        if "already" in response.text.lower():
            print("\n💡 Transaction might already be in the blockchain")
        elif "witness" in response.text.lower():
            print("\n⚠️ Witness issue detected - checking transaction structure...")
            print(f"   TX starts with: {tx_hex[:10]}")
            print(f"   Version bytes: {tx_hex[:8]}")
            print(f"   Flag (if SegWit): {tx_hex[8:12]}")
        
        return False

if __name__ == "__main__":
    main()
