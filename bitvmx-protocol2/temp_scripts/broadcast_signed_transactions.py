#!/usr/bin/env python3
"""
BitVMX Signed Transactions Broadcaster
Broadcasts pre-signed BitVMX transactions to Mutinynet
"""
import json
import sys
import requests
import hashlib
import time

def calculate_txid(tx_hex: str) -> str:
    """Calculate TXID from hex transaction"""
    try:
        raw_bytes = bytes.fromhex(tx_hex)
        hash1 = hashlib.sha256(raw_bytes).digest()
        hash2 = hashlib.sha256(hash1).digest()
        return hash2[::-1].hex()
    except:
        return None

def broadcast_to_mutinynet(tx_hex: str) -> dict:
    """Broadcast transaction to Mutinynet"""
    url = "https://mutinynet.com/api/tx"
    
    try:
        response = requests.post(url, data=tx_hex, headers={"Content-Type": "text/plain"})
        if response.status_code == 200:
            return {"success": True, "txid": response.text.strip()}
        else:
            return {"success": False, "error": response.text}
    except Exception as e:
        return {"success": False, "error": str(e)}

def main():
    # Use existing setup with signed transactions
    setup_uuid = "a985e49a-2964-49f8-adbe-5087446ead70"
    signed_file = f"../prover_files/{setup_uuid}/signed_transactions.json"
    
    print(f"Loading signed transactions from {signed_file}")
    
    try:
        with open(signed_file, 'r') as f:
            signed_txs = json.load(f)
    except FileNotFoundError:
        print(f"Error: File not found: {signed_file}")
        return 1
    
    # BitVMX transaction broadcast order (topological)
    # 1. hash_result_tx first (spends from funding)
    # 2. trigger_protocol_tx (if exists)
    # 3. search transactions
    # 4. read_search transactions
    
    broadcast_order = [
        "hash_result_tx",
        "trigger_protocol_tx",
    ]
    
    # Add list transactions
    for key in ["search_hash_tx_list", "search_choice_tx_list", 
                "read_search_hash_tx_list", "read_search_choice_tx_list"]:
        if key in signed_txs and isinstance(signed_txs[key], list):
            for i, tx in enumerate(signed_txs[key]):
                broadcast_order.append(f"{key}[{i}]")
    
    results = []
    
    for tx_key in broadcast_order:
        # Handle list items
        if "[" in tx_key:
            base_key, index = tx_key.split("[")
            index = int(index.rstrip("]"))
            if base_key in signed_txs and index < len(signed_txs[base_key]):
                tx_hex = signed_txs[base_key][index]
                tx_label = f"{base_key}[{index}]"
            else:
                continue
        else:
            if tx_key not in signed_txs:
                continue
            tx_hex = signed_txs[tx_key]
            tx_label = tx_key
        
        # Skip empty transactions
        if not tx_hex or tx_hex == "":
            continue
            
        txid = calculate_txid(tx_hex)
        print(f"\n=== Broadcasting {tx_label} ===")
        print(f"TXID: {txid}")
        print(f"Size: {len(tx_hex)//2} bytes")
        
        # Check if already confirmed
        check_url = f"https://mutinynet.com/api/tx/{txid}"
        try:
            check_response = requests.get(check_url)
            if check_response.status_code == 200:
                print(f"✓ Already broadcast: {txid}")
                results.append({"tx": tx_label, "status": "already_broadcast", "txid": txid})
                continue
        except:
            pass
        
        # Broadcast transaction
        print(f"Broadcasting to Mutinynet...")
        result = broadcast_to_mutinynet(tx_hex)
        
        if result["success"]:
            print(f"✅ Success: {result['txid']}")
            results.append({"tx": tx_label, "status": "success", "txid": result['txid']})
        else:
            print(f"❌ Failed: {result['error']}")
            results.append({"tx": tx_label, "status": "failed", "error": result['error']})
        
        # Small delay between broadcasts
        time.sleep(1)
    
    # Summary
    print("\n=== Broadcast Summary ===")
    success_count = sum(1 for r in results if r["status"] in ["success", "already_broadcast"])
    failed_count = sum(1 for r in results if r["status"] == "failed")
    
    print(f"Total: {len(results)} transactions")
    print(f"Success/Already broadcast: {success_count}")
    print(f"Failed: {failed_count}")
    
    if failed_count > 0:
        print("\nFailed transactions:")
        for r in results:
            if r["status"] == "failed":
                print(f"  - {r['tx']}: {r['error']}")
    
    # Save results
    result_file = f"prover_files/{setup_uuid}/broadcast_results.json"
    with open(result_file, 'w') as f:
        json.dump({
            "timestamp": time.time(),
            "results": results,
            "summary": {
                "total": len(results),
                "success": success_count,
                "failed": failed_count
            }
        }, f, indent=2)
    
    print(f"\nResults saved to: {result_file}")
    
    return 0 if failed_count == 0 else 1

if __name__ == "__main__":
    sys.exit(main())