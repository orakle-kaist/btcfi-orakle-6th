#!/usr/bin/env python3
"""
Try the /api/v1/fund endpoint
"""
import json
import requests

def main():
    API_BASE = "http://localhost:8081"
    
    # Simple fund request
    fund_input = {
        "funding_txid": "00c57240bf32c053bcc6f2ca37a45609064051ed7c10023a99af670db9beb24f",
        "funding_index": 0,
        "amount": 149998922
    }
    
    print("=" * 60)
    print("BITVMX FUND ENDPOINT")
    print("=" * 60)
    
    # Health check
    health = requests.get(f"{API_BASE}/healthcheck", timeout=2)
    print(f"✅ Prover service: {health.json()}")
    
    # Call /api/v1/fund
    print("\n📡 Calling /api/v1/fund...")
    response = requests.post(
        f"{API_BASE}/api/v1/fund",
        json=fund_input,
        timeout=120
    )
    
    if response.status_code == 200:
        result = response.json()
        print(f"\n✅ SUCCESS!")
        print(f"   Response: {json.dumps(result, indent=2)[:500]}")
        return True
    else:
        print(f"\n❌ Failed: {response.status_code}")
        print(f"   Response: {response.text[:500]}")
        return False

if __name__ == "__main__":
    main()
