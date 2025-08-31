#!/usr/bin/env python3
"""
Broadcast prover transaction via Docker API
"""
import json
import requests
import time

def main():
    API_BASE = "http://localhost:8081"
    setup_uuid = "78fd8d6e-b3f4-468d-8411-2bf609662add"
    
    print("=" * 60)
    print("BROADCAST VIA DOCKER API")
    print("=" * 60)
    print(f"\nSetup UUID: {setup_uuid}")
    
    try:
        # Health check
        health = requests.get(f"{API_BASE}/healthcheck", timeout=2)
        print(f"✅ Prover service: {health.json()}")
        
        # Try to broadcast the kickoff transaction
        print("\n📡 Broadcasting kickoff transaction...")
        
        # Call the broadcast endpoint
        broadcast_data = {
            "setup_uuid": setup_uuid,
            "transaction_type": "kickoff"
        }
        
        response = requests.post(
            f"{API_BASE}/api/v1/broadcast/kickoff",
            json=broadcast_data,
            timeout=30
        )
        
        if response.status_code == 200:
            result = response.json()
            print(f"\n✅ SUCCESS!")
            print(f"   Result: {json.dumps(result, indent=2)}")
            return True
        else:
            print(f"\n❌ Failed: {response.status_code}")
            print(f"   Response: {response.text[:500]}")
            
    except Exception as e:
        print(f"\n❌ Error: {e}")
    
    # Try alternative: Call prover transaction endpoint
    print("\n🔄 Trying prover transaction endpoint...")
    try:
        response = requests.post(
            f"{API_BASE}/api/v1/prover/transaction",
            json={"setup_uuid": setup_uuid},
            timeout=30
        )
        
        if response.status_code == 200:
            result = response.json()
            print(f"\n✅ SUCCESS!")
            print(f"   TXID: {result.get('txid', 'unknown')}")
            return True
        else:
            print(f"   Failed: {response.status_code}")
            if response.text:
                print(f"   Response: {response.text[:200]}")
                
    except Exception as e:
        print(f"   Error: {e}")
    
    return False

if __name__ == "__main__":
    success = main()
    if success:
        print("\n🎉 Transaction broadcast via API!")
    else:
        print("\n⚠️ Failed to broadcast via API")
        print("   The funding UTXO may already be spent")