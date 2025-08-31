#!/usr/bin/env python3
"""
Get failed transaction data from a setup
"""
import json
import requests

def main():
    API_BASE = "http://localhost:8081"
    
    # Use one of the setups with check_failed_transactions
    setup_uuid = "208f19ab-a92f-4013-a02d-7f285980fb1e"
    
    print("=" * 60)
    print("CHECKING FAILED TRANSACTIONS")
    print("=" * 60)
    print(f"Setup UUID: {setup_uuid}")
    
    # Try to get more detailed info
    response = requests.post(
        f"{API_BASE}/api/v1/next_step",
        json={"setup_uuid": setup_uuid},
        timeout=10
    )
    
    if response.status_code == 200:
        result = response.json()
        print(f"\nFull response:")
        print(json.dumps(result, indent=2))
        
        # Save for analysis
        with open("failed_tx_response.json", "w") as f:
            json.dump(result, f, indent=2)
        print("\n💾 Saved to failed_tx_response.json")
        
    else:
        print(f"\n❌ Failed: {response.status_code}")
        print(f"   Response: {response.text[:500]}")

if __name__ == "__main__":
    main()
