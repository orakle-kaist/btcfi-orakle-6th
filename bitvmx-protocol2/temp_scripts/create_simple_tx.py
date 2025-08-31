#!/usr/bin/env python3
"""
Create and broadcast a simple transaction using our UTXO
"""
import hashlib
import requests

def main():
    # Our UTXO
    utxo_txid = "00c57240bf32c053bcc6f2ca37a45609064051ed7c10023a99af670db9beb24f"
    utxo_vout = 0
    utxo_amount = 149998922  # sats
    
    # Our address
    our_address = "tb1qt8rdur557nz338g3lekc6458pj0dl63c0s9904"
    
    # Simple transaction: spend to ourselves with fee
    fee = 1000
    output_amount = utxo_amount - fee
    
    print("=" * 60)
    print("CREATING SIMPLE TRANSACTION")
    print("=" * 60)
    print(f"\n📊 Input UTXO: {utxo_txid[:16]}...")
    print(f"   Amount: {utxo_amount:,} sats")
    print(f"   Fee: {fee:,} sats")
    print(f"   Output: {output_amount:,} sats")
    
    # Check if UTXO exists
    print("\n🔍 Checking UTXO...")
    response = requests.get(f"https://mutinynet.com/api/tx/{utxo_txid}/outspend/{utxo_vout}")
    if response.status_code == 200:
        data = response.json()
        if data.get("spent"):
            print("❌ UTXO already spent!")
            print(f"   Spent in TX: {data.get('txid', 'unknown')}")
            return False
        else:
            print("✅ UTXO is available!")
    else:
        print("⚠️ Could not check UTXO status")
    
    # For now, just check the UTXO status
    # Creating raw transaction requires more complex signing logic
    
    print("\n💡 Next step: Use Docker API or Bitcoin Core to create signed transaction")
    print("   Or use our existing setup scripts with this UTXO")
    
    return True

if __name__ == "__main__":
    main()