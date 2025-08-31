#!/usr/bin/env python3
"""
Check all existing setups
"""
import json
import requests
import os

def main():
    API_BASE = "http://localhost:8081"
    
    # List of setup UUIDs we found
    setups = [
        "bbb85126-d8f4-45fb-bc9e-87f9ac4d0d36",
        "208f19ab-a92f-4013-a02d-7f285980fb1e",
        "ecc6ab56-d9cf-4205-8b36-cd1347cc86e7",
        "a3eb64c0-d31d-4551-96e5-fc9be13302c2",
        "4392834a-7e5d-40e3-a9bf-927e5f9ef328"
    ]
    
    print("=" * 60)
    print("CHECKING ALL EXISTING SETUPS")
    print("=" * 60)
    
    for setup_uuid in setups:
        print(f"\n🔍 Setup: {setup_uuid}")
        
        # Get next step
        response = requests.post(
            f"{API_BASE}/api/v1/next_step",
            json={"setup_uuid": setup_uuid},
            timeout=10
        )
        
        if response.status_code == 200:
            result = response.json()
            next_step = result.get('next_step', 'unknown')
            print(f"   Status: {next_step}")
            
            if next_step == "fund" and "funding_address" in result:
                print(f"   Funding address: {result['funding_address']}")
                print(f"   ✅ This setup needs funding!")
                
            elif "transaction" in result:
                print(f"   Transaction type: {result.get('transaction_type', 'unknown')}")
                print(f"   ✅ This setup has a transaction ready!")
                
                # Save the first good one
                with open(f"setup_{setup_uuid}_tx.json", "w") as f:
                    json.dump(result, f, indent=2)
                print(f"   💾 Saved to setup_{setup_uuid}_tx.json")
                
        else:
            print(f"   ❌ Failed: {response.status_code}")

if __name__ == "__main__":
    main()
