#!/usr/bin/env python3
"""
Get next step for existing setup
"""
import json
import requests

def main():
    API_BASE = "http://localhost:8081"
    
    # Use existing setup UUID
    setup_uuid = "ecc6ab56-d9cf-4205-8b36-cd1347cc86e7"
    
    print("=" * 60)
    print("NEXT STEP FOR EXISTING SETUP")
    print("=" * 60)
    print(f"Setup UUID: {setup_uuid}")
    
    # Call /api/v1/next_step
    print("\n📡 Getting next step...")
    response = requests.post(
        f"{API_BASE}/api/v1/next_step",
        json={"setup_uuid": setup_uuid},
        timeout=10
    )
    
    if response.status_code == 200:
        result = response.json()
        print(f"\n✅ SUCCESS!")
        print(f"\nNext step: {result.get('next_step', 'unknown')}")
        
        if "transaction" in result:
            print(f"\nTransaction available:")
            print(f"  Type: {result.get('transaction_type', 'unknown')}")
            if "hex" in result.get("transaction", {}):
                print(f"  Hex: {result['transaction']['hex'][:100]}...")
            if "txid" in result.get("transaction", {}):
                print(f"  TXID: {result['transaction']['txid']}")
        
        return result
    else:
        print(f"\n❌ Failed: {response.status_code}")
        print(f"   Response: {response.text[:500]}")
        return None

if __name__ == "__main__":
    result = main()
    if result and "transaction" in result:
        # Save transaction for broadcasting
        with open("temp_tx.json", "w") as f:
            json.dump(result, f, indent=2)
        print("\n💾 Saved to temp_tx.json")
