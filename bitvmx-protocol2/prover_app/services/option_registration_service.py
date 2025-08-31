#!/usr/bin/env python3
from prover_app.common.hexsafe import bfromhex_safe
"""
BTCFi Option Registration Service
Complete BitVMX protocol flow automation for option product registration
"""
import json
import time
import hashlib
import requests
from typing import Dict, Any, List, Optional
from datetime import datetime


class OptionRegistrationService:
    """Service to handle complete option registration flow on BitVMX"""
    
    def __init__(self, network: str = "mutinynet"):
        self.network = network
        self.api_base = "http://localhost:8081"  # Prover backend
        self.verifier_url = "http://verifier-backend:80"
        self.blockchain_api = "https://mutinynet.com/api" if network == "mutinynet" else None
        
    def create_option_commitment(self, option_data: Dict[str, Any]) -> str:
        """Create 32-byte commitment from option data"""
        # Ensure consistent JSON serialization
        option_json = json.dumps(option_data, sort_keys=True, separators=(',', ':'))
        full_commitment = hashlib.sha256(option_json.encode()).hexdigest()
        # Return first 4 bytes for on-chain storage (BitVMX principle)
        return full_commitment[:8]
    
    def create_setup(self, funding_data: Dict[str, Any], option_data: Dict[str, Any], 
                     allocation_amount: int = None) -> Optional[str]:
        """
        Step 1: Create BitVMX setup with option commitment
        
        Args:
            funding_data: Dict with tx_id, index, amount, private_key, public_key, address
            option_data: Dict with type, strike, spot, quantity
            allocation_amount: Amount to allocate for this option (default: 100,000 sats)
            
        Returns:
            setup_uuid if successful, None otherwise
        """
        print("\n=== Step 1: Creating BitVMX Setup ===")
        
        # Create option commitment
        commitment = self.create_option_commitment(option_data)
        print(f"Option commitment: {commitment}")
        
        # Calculate appropriate allocation
        if allocation_amount is None:
            # Default: allocate 100,000 sats for option registration
            # This leaves plenty for future transactions
            allocation_amount = min(100000, funding_data["amount"] // 10)
        
        print(f"Funding available: {funding_data['amount']} sats")
        print(f"Allocating for option: {allocation_amount} sats")
        print(f"Remaining after allocation: {funding_data['amount'] - allocation_amount} sats")
        
        # Prepare setup input
        setup_input = {
            "max_amount_of_steps": 100,
            "amount_of_bits_wrong_step_search": 1,
            "funding_tx_id": funding_data["tx_id"],
            "funding_index": funding_data["index"],
            "funding_amount_of_satoshis": funding_data["amount"],  # Total available
            "allocation_amount_of_satoshis": allocation_amount,  # Amount to use for this option
            "secret_origin_of_funds": funding_data["private_key"],
            "prover_destination_address": funding_data["address"],
            "prover_signature_private_key": funding_data["private_key"],
            "prover_signature_public_key": funding_data["public_key"],
            "amount_of_input_words": 1,
            "step_fees_satoshis": 3000,
            "max_fee_allowed": 50000,
            "amount_of_public_inputs": 1,
            "list_of_public_inputs": [commitment],
            "verifier_list": [self.verifier_url]
        }
        
        try:
            # Call setup endpoint
            response = requests.post(
                f"{self.api_base}/api/v1/setup",
                json=setup_input,
                timeout=300
            )
            
            if response.status_code == 200:
                result = response.json()
                setup_uuid = result.get("setup_uuid")
                print(f"✅ Setup created: {setup_uuid}")
                
                # Save option metadata
                self._save_option_metadata(setup_uuid, option_data, commitment)
                
                return setup_uuid
            else:
                print(f"❌ Setup failed: {response.status_code} - {response.text}")
                return None
                
        except Exception as e:
            print(f"❌ Error creating setup: {e}")
            return None
    
    def _save_option_metadata(self, setup_uuid: str, option_data: Dict, commitment: str):
        """Save option metadata for future reference"""
        import os
        
        metadata = {
            "setup_uuid": setup_uuid,
            "option_data": option_data,
            "commitment": commitment,
            "timestamp": datetime.now().isoformat()
        }
        
        # Save to prover_files directory
        metadata_file = f"prover_files/{setup_uuid}/option_metadata.json"
        os.makedirs(os.path.dirname(metadata_file), exist_ok=True)
        
        with open(metadata_file, 'w') as f:
            json.dump(metadata, f, indent=2)
        
        print(f"  Metadata saved: {metadata_file}")
    
    def load_signed_transactions(self, setup_uuid: str) -> Optional[Dict[str, Any]]:
        """Load signed transactions from file"""
        signed_file = f"prover_files/{setup_uuid}/signed_transactions.json"
        
        try:
            with open(signed_file, 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            print(f"❌ Signed transactions not found: {signed_file}")
            return None
    
    def broadcast_transaction(self, tx_hex: str, tx_name: str = "transaction") -> Optional[str]:
        """
        Broadcast a single transaction to blockchain
        
        Returns:
            txid if successful, None otherwise
        """
        if not self.blockchain_api:
            print(f"❌ No blockchain API configured for {self.network}")
            return None
        
        try:
            # Calculate TXID
            raw_bytes = bfromhex_safe(tx_hex)
            hash1 = hashlib.sha256(raw_bytes).digest()
            hash2 = hashlib.sha256(hash1).digest()
            txid = hash2[::-1].hex()
            
            print(f"  Broadcasting {tx_name}: {txid}")
            
            # Check if already broadcast
            check_response = requests.get(f"{self.blockchain_api}/tx/{txid}")
            if check_response.status_code == 200:
                print(f"  ✓ Already broadcast: {txid}")
                return txid
            
            # Broadcast to network
            response = requests.post(
                f"{self.blockchain_api}/tx",
                data=tx_hex,
                headers={"Content-Type": "text/plain"}
            )
            
            if response.status_code == 200:
                print(f"  ✅ Success: {txid}")
                return txid
            else:
                print(f"  ❌ Failed: {response.text}")
                return None
                
        except Exception as e:
            print(f"  ❌ Error: {e}")
            return None
    
    def broadcast_protocol_transactions(self, setup_uuid: str) -> Dict[str, Any]:
        """
        Step 2: Broadcast all protocol transactions in correct order
        
        Returns:
            Dict with broadcast results
        """
        print(f"\n=== Step 2: Broadcasting Protocol Transactions ===")
        
        # Load signed transactions
        signed_txs = self.load_signed_transactions(setup_uuid)
        if not signed_txs:
            return {"error": "No signed transactions found"}
        
        results = {
            "setup_uuid": setup_uuid,
            "broadcasted": [],
            "failed": [],
            "skipped": []
        }
        
        # BitVMX transaction order (topological)
        broadcast_order = [
            ("hash_result_tx", None),           # Single tx
            ("trigger_protocol_tx", None),      # Single tx
            ("search_hash_tx_list", "list"),    # List of txs
            ("search_choice_tx_list", "list"),  # List of txs
            ("read_search_hash_tx_list", "list"),
            ("read_search_choice_tx_list", "list")
        ]
        
        for tx_key, tx_type in broadcast_order:
            if tx_key not in signed_txs:
                continue
                
            if tx_type == "list":
                # Handle list of transactions
                tx_list = signed_txs[tx_key]
                if not isinstance(tx_list, list):
                    continue
                    
                for i, tx_hex in enumerate(tx_list):
                    tx_name = f"{tx_key}[{i}]"
                    txid = self.broadcast_transaction(tx_hex, tx_name)
                    
                    if txid:
                        results["broadcasted"].append({"name": tx_name, "txid": txid})
                    else:
                        results["failed"].append({"name": tx_name})
                    
                    time.sleep(0.5)  # Small delay between broadcasts
            else:
                # Handle single transaction
                tx_hex = signed_txs[tx_key]
                txid = self.broadcast_transaction(tx_hex, tx_key)
                
                if txid:
                    results["broadcasted"].append({"name": tx_key, "txid": txid})
                else:
                    results["failed"].append({"name": tx_key})
                
                time.sleep(0.5)
        
        # Summary
        print(f"\n=== Broadcast Summary ===")
        print(f"Broadcasted: {len(results['broadcasted'])} transactions")
        print(f"Failed: {len(results['failed'])} transactions")
        
        return results
    
    def wait_for_confirmations(self, txid: str, confirmations: int = 1, timeout: int = 600):
        """
        Wait for transaction confirmations
        
        Args:
            txid: Transaction ID to wait for
            confirmations: Number of confirmations required
            timeout: Maximum wait time in seconds
        """
        print(f"\n=== Waiting for {confirmations} confirmations ===")
        print(f"TXID: {txid}")
        
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            try:
                response = requests.get(f"{self.blockchain_api}/tx/{txid}")
                if response.status_code == 200:
                    tx_data = response.json()
                    status = tx_data.get("status", {})
                    
                    if status.get("confirmed"):
                        print(f"✅ Transaction confirmed!")
                        print(f"  Block height: {status.get('block_height')}")
                        return True
                
                print(".", end="", flush=True)
                time.sleep(10)
                
            except Exception as e:
                print(f"\n❌ Error checking confirmation: {e}")
                time.sleep(10)
        
        print(f"\n⏱️ Timeout waiting for confirmations")
        return False
    
    def register_option(self, funding_data: Dict[str, Any], option_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Complete option registration flow
        
        Args:
            funding_data: Funding UTXO information
            option_data: Option product details
            
        Returns:
            Dict with registration results
        """
        print("\n" + "="*60)
        print("     BTCFi Option Registration - BitVMX Protocol")
        print("="*60)
        
        # Step 1: Create setup
        setup_uuid = self.create_setup(funding_data, option_data)
        if not setup_uuid:
            return {"success": False, "error": "Failed to create setup"}
        
        # Step 2: Broadcast transactions
        broadcast_results = self.broadcast_protocol_transactions(setup_uuid)
        
        if not broadcast_results.get("broadcasted"):
            return {"success": False, "error": "No transactions broadcasted", "results": broadcast_results}
        
        # Step 3: Wait for first transaction confirmation (optional)
        first_tx = broadcast_results["broadcasted"][0]
        if first_tx:
            self.wait_for_confirmations(first_tx["txid"], confirmations=1, timeout=60)
        
        # Complete
        print("\n" + "="*60)
        print("✅ Option Registration Complete!")
        print(f"Setup UUID: {setup_uuid}")
        print(f"Transactions: {len(broadcast_results['broadcasted'])} broadcasted")
        
        if broadcast_results['broadcasted']:
            print("\nView on Mutinynet:")
            for tx in broadcast_results['broadcasted'][:3]:  # Show first 3
                print(f"  https://mutinynet.com/tx/{tx['txid']}")
        
        print("="*60)
        
        return {
            "success": True,
            "setup_uuid": setup_uuid,
            "broadcast_results": broadcast_results
        }


# Convenience function for direct usage
def register_btcfi_option(funding_data: Dict[str, Any], option_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Register a BTCFi option using BitVMX protocol
    
    Example:
        funding_data = {
            "tx_id": "66115221c1c2ec635371a7ea46eeda175e766b51982fe5b2e710793be8523dff",
            "index": 0,
            "amount": 199997187,
            "private_key": "d8a1e1224e63135765bde9dc8a2c8e403eee8be73d3589d58c5ddbf9dce3fdf4",
            "public_key": "03bf751f0d2d22e6f0163c9acaa14ae04e6e1a004cb4a24d893c1f86314e79d5de",
            "address": "tb1qt8rdur557nz338g3lekc6458pj0dl63c0s9904"
        }
        
        option_data = {
            "type": "PUT",
            "strike": 50000,
            "spot": 54000,
            "quantity": 100
        }
        
        result = register_btcfi_option(funding_data, option_data)
    """
    service = OptionRegistrationService(network="mutinynet")
    return service.register_option(funding_data, option_data)


if __name__ == "__main__":
    # Test with our funding
    funding = {
        "tx_id": "66115221c1c2ec635371a7ea46eeda175e766b51982fe5b2e710793be8523dff",
        "index": 0,
        "amount": 199997187,
        "private_key": "d8a1e1224e63135765bde9dc8a2c8e403eee8be73d3589d58c5ddbf9dce3fdf4",
        "public_key": "03bf751f0d2d22e6f0163c9acaa14ae04e6e1a004cb4a24d893c1f86314e79d5de",
        "address": "tb1qt8rdur557nz338g3lekc6458pj0dl63c0s9904"
    }
    
    option = {
        "type": "PUT",
        "strike": 50000,
        "spot": 54000,
        "quantity": 100
    }
    
    result = register_btcfi_option(funding, option)
    print(f"\nFinal result: {json.dumps(result, indent=2)}")