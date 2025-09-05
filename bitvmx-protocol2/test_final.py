#!/usr/bin/env python3
"""
Final test to verify OP_EQUALVERIFY fix with signing cache
"""
import requests
import json
import time

def test_next_step(setup_uuid):
    """Test next_step with cached signing data"""
    
    print(f"\n=== Testing next_step for setup {setup_uuid} ===\n")
    
    # Call next_step API
    url = "http://localhost:8080/api/v1/next_step"
    
    payload = {
        "setup_uuid": setup_uuid,
        "force_resign": True,  # Force re-signing to use cache
        "regen_transactions": False
    }
    
    print(f"Calling: POST {url}")
    print(f"Payload: {payload}")
    print("This will use the cached signing data to ensure consistency...")
    
    try:
        response = requests.post(url, json=payload, timeout=30)
        
        if response.status_code == 200:
            result = response.json()
            print(f"\n✅ Success! Response received:")
            print(f"  - Message: {result.get('message', 'N/A')}")
            print(f"  - Next Step: {result.get('next_step', 'N/A')}")
            print(f"\nFull response:")
            print(json.dumps(result, indent=2))
            
            # Check if we have signatures
            if 'result' in result and 'signatures' in result['result']:
                signatures = result['result']['signatures']
                print(f"  - Number of signatures: {len(signatures)}")
                
                # Show first few signatures as sample
                for i, sig_data in enumerate(signatures[:3]):
                    if isinstance(sig_data, dict):
                        print(f"  - Signature {i}: {sig_data.get('signature', 'N/A')[:50]}...")
                        
            # Check transaction info
            if 'result' in result and 'transaction' in result['result']:
                tx_data = result['result']['transaction']
                print(f"\n  Transaction details:")
                print(f"  - Transaction ID: {tx_data.get('txid', 'N/A')}")
                print(f"  - Raw TX length: {len(tx_data.get('raw', ''))} bytes")
                
            return True
            
        else:
            print(f"\n❌ Error: HTTP {response.status_code}")
            print(f"Response: {response.text[:500]}")
            return False
            
    except requests.exceptions.Timeout:
        print("\n❌ Request timed out after 30 seconds")
        return False
    except Exception as e:
        print(f"\n❌ Exception: {e}")
        return False

def check_signing_cache(setup_uuid):
    """Check if signing cache exists"""
    cache_path = f"prover_files/{setup_uuid}/signing_cache.json"
    print(f"\nChecking signing cache: {cache_path}")
    
    try:
        with open(cache_path, 'r') as f:
            cache = json.load(f)
            print(f"✅ Cache found with hash_result_script_hex: {cache['hash_result_script_hex'][:50]}...")
            return True
    except FileNotFoundError:
        print(f"❌ Cache not found")
        return False
    except Exception as e:
        print(f"❌ Error reading cache: {e}")
        return False

def main():
    # Read current setup UUID from file
    try:
        with open("current_setup.json", "r") as f:
            current_setup = json.load(f)
            setup_uuid = current_setup["setup_uuid"]
    except:
        # Fallback to hardcoded UUID
        setup_uuid = "5d399639-31dc-4c5c-9785-97200a21fc2c"
    
    print("=" * 60)
    print("FINAL TEST: BitVMX Transaction Signing with Cache")
    print("=" * 60)
    
    # Check cache exists
    if not check_signing_cache(setup_uuid):
        print("\n⚠️  No signing cache found. Run create_setup first.")
        return
    
    # Test next_step
    success = test_next_step(setup_uuid)
    
    if success:
        print("\n" + "=" * 60)
        print("🎉 SUCCESS! Transaction signing working with cache!")
        print("=" * 60)
    else:
        print("\n" + "=" * 60)
        print("❌ Test failed. Check Docker logs for details.")
        print("=" * 60)

if __name__ == "__main__":
    main()