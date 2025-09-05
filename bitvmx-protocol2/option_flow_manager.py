#!/usr/bin/env python3
"""
BitVMX Option Flow Manager
Manages the complete option lifecycle: Registration -> Purchase -> Settlement
"""

import json
import os
import time
import requests
from datetime import datetime
from typing import Dict, Optional, List

class OptionFlowManager:
    def __init__(self, prover_url="http://localhost:8080", verifier_url="http://localhost:8081"):
        self.prover_url = prover_url
        self.verifier_url = verifier_url
        self.setups = {}  # Track all setups
        self.options = {}  # Track registered options
        
    def load_existing_setups(self):
        """Load existing setups from prover_files"""
        base_dir = "prover_files"
        if not os.path.exists(base_dir):
            return
            
        for setup_uuid in os.listdir(base_dir):
            metadata_file = os.path.join(base_dir, setup_uuid, "setup_metadata.json")
            if os.path.exists(metadata_file):
                with open(metadata_file, 'r') as f:
                    metadata = json.load(f)
                    self.setups[setup_uuid] = metadata
                    
                    # Track option registrations
                    if metadata.get("setup_type") == "OPTION_REGISTRATION":
                        option_id = self._extract_option_id(metadata)
                        if option_id:
                            self.options[option_id] = {
                                "registration_setup": setup_uuid,
                                "metadata": metadata
                            }
    
    def _extract_option_id(self, metadata: Dict) -> Optional[str]:
        """Extract option ID from registration metadata"""
        # Option ID could be derived from setup_uuid or input_hex
        # For simplicity, use first 8 chars of setup_uuid
        return metadata.get("setup_uuid", "")[:8]
    
    def register_option(self, option_type: str, strike_usd: float, expiry: int, pool_size: int) -> Optional[str]:
        """
        Step 1: Register a new option product
        """
        print(f"\n{'='*60}")
        print(f"📝 OPTION REGISTRATION")
        print(f"{'='*60}")
        print(f"Type: {option_type}, Strike: ${strike_usd}, Expiry: {expiry}, Pool: {pool_size}")
        
        # Create input hex for option registration
        option_type_hex = "00000000" if option_type == "CALL" else "00000001"
        strike_hex = f"{int(strike_usd * 100):08x}"  # Convert to cents
        expiry_hex = f"{expiry:08x}"
        pool_hex = f"{pool_size:08x}"
        input_hex = option_type_hex + strike_hex + expiry_hex + pool_hex
        
        # Find available UTXO
        from create_setup_option_registration import find_best_utxo
        funding_tx_id, funding_index, funding_amount = find_best_utxo()
        if not funding_tx_id:
            print("❌ No available UTXO for registration")
            return None
        
        # Generate unique n0, n1
        import hashlib
        timestamp_hash = hashlib.sha256(str(time.time()).encode()).hexdigest()
        n0 = str(int(timestamp_hash[:32], 16) | (1 << 255) | 1)
        n1 = str((int(timestamp_hash[32:], 16) + 2) | (1 << 255) | 1)
        
        # Setup data
        setup_data = {
            "n0": n0,
            "n1": n1,
            "prover_public_key": "b882af3fb540e1c2530d3d9e11993f206bb7626e9cfe19a03e7e42c75e19ad59",
            "input_hex": input_hex,
            "max_amount_of_steps": 16,
            "funding_tx_id": funding_tx_id,
            "funding_index": funding_index,
            "funding_amount": funding_amount,
            "step_fees": 30000,
            "amount_of_bits_wrong_step_search": 2,
            "amount_of_bits_per_digit_checksum": 4,
            "secret_origin_of_funds": "d8a1e1224e63135765bde9dc8a2c8e403eee8be73d3589d58c5ddbf9dce3fdf4",
            "prover_destination_address": "tb1qt8rdur557nz338g3lekc6458pj0dl63c0s9904",
            "verifier_destination_address": "tb1q8fg5jrspc7fn8jvpe5tfr7e5dlwvsh6xw8cq4j",
            "prover_signature_private_key": "d8a1e1224e63135765bde9dc8a2c8e403eee8be73d3589d58c5ddbf9dce3fdf4",
            "prover_signature_public_key": "03bf751f0d2d22e6f0163c9acaa14ae04e6e1a004cb4a24d893c1f86314e79d5de",
            "amount_of_input_words": 4,
            "elf_file_name": "option_registration_final.elf"
        }
        
        # Call prover setup
        print("📤 Creating registration setup...")
        response = requests.post(
            f"{self.prover_url}/api/v1/setup",
            json=setup_data,
            timeout=300
        )
        
        if response.status_code == 200:
            result = response.json()
            setup_uuid = result.get("setup_uuid")
            print(f"✅ Registration setup created: {setup_uuid}")
            
            # Save to tracking
            option_id = setup_uuid[:8]
            self.options[option_id] = {
                "registration_setup": setup_uuid,
                "option_type": option_type,
                "strike": strike_usd,
                "expiry": expiry,
                "pool_size": pool_size,
                "created_at": datetime.now().isoformat()
            }
            
            # Save option registry
            self.save_option_registry()
            
            return option_id
        else:
            print(f"❌ Registration failed: {response.status_code}")
            return None
    
    def purchase_option(self, option_id: str, quantity: int, premium_sats: int) -> Optional[str]:
        """
        Step 2: Purchase an option
        """
        print(f"\n{'='*60}")
        print(f"💰 OPTION PURCHASE")
        print(f"{'='*60}")
        print(f"Option ID: {option_id}, Quantity: {quantity}, Premium: {premium_sats} sats")
        
        if option_id not in self.options:
            print(f"❌ Option {option_id} not found")
            return None
        
        # Create input hex for purchase
        option_id_hex = f"{option_id:0>8}"
        quantity_hex = f"{quantity:08x}"
        premium_hex = f"{premium_sats:08x}"
        input_hex = option_id_hex + quantity_hex + premium_hex + "00000000"  # Padding
        
        # Find available UTXO
        from create_setup_option_registration import find_best_utxo
        funding_tx_id, funding_index, funding_amount = find_best_utxo()
        if not funding_tx_id:
            print("❌ No available UTXO for purchase")
            return None
        
        # Generate unique n0, n1
        import hashlib
        timestamp_hash = hashlib.sha256(str(time.time()).encode()).hexdigest()
        n0 = str(int(timestamp_hash[:32], 16) | (1 << 255) | 1)
        n1 = str((int(timestamp_hash[32:], 16) + 2) | (1 << 255) | 1)
        
        # Setup data (could use different ELF for purchase logic)
        setup_data = {
            "n0": n0,
            "n1": n1,
            "prover_public_key": "b882af3fb540e1c2530d3d9e11993f206bb7626e9cfe19a03e7e42c75e19ad59",
            "input_hex": input_hex,
            "max_amount_of_steps": 16,
            "funding_tx_id": funding_tx_id,
            "funding_index": funding_index,
            "funding_amount": funding_amount,
            "step_fees": 30000,
            "amount_of_bits_wrong_step_search": 2,
            "amount_of_bits_per_digit_checksum": 4,
            "secret_origin_of_funds": "d8a1e1224e63135765bde9dc8a2c8e403eee8be73d3589d58c5ddbf9dce3fdf4",
            "prover_destination_address": "tb1qt8rdur557nz338g3lekc6458pj0dl63c0s9904",
            "verifier_destination_address": "tb1q8fg5jrspc7fn8jvpe5tfr7e5dlwvsh6xw8cq4j",
            "prover_signature_private_key": "d8a1e1224e63135765bde9dc8a2c8e403eee8be73d3589d58c5ddbf9dce3fdf4",
            "prover_signature_public_key": "03bf751f0d2d22e6f0163c9acaa14ae04e6e1a004cb4a24d893c1f86314e79d5de",
            "amount_of_input_words": 4,
            "elf_file_name": "option_purchase.elf"  # Different ELF for purchase
        }
        
        # Call prover setup
        print("📤 Creating purchase setup...")
        response = requests.post(
            f"{self.prover_url}/api/v1/setup",
            json=setup_data,
            timeout=300
        )
        
        if response.status_code == 200:
            result = response.json()
            setup_uuid = result.get("setup_uuid")
            print(f"✅ Purchase setup created: {setup_uuid}")
            
            # Update option tracking
            if "purchases" not in self.options[option_id]:
                self.options[option_id]["purchases"] = []
            
            self.options[option_id]["purchases"].append({
                "purchase_setup": setup_uuid,
                "quantity": quantity,
                "premium": premium_sats,
                "purchased_at": datetime.now().isoformat()
            })
            
            # Save option registry
            self.save_option_registry()
            
            return setup_uuid
        else:
            print(f"❌ Purchase failed: {response.status_code}")
            return None
    
    def settle_option(self, option_id: str, spot_price_usd: float) -> Optional[str]:
        """
        Step 3: Settle an option at expiry
        """
        print(f"\n{'='*60}")
        print(f"⚖️ OPTION SETTLEMENT")
        print(f"{'='*60}")
        print(f"Option ID: {option_id}, Spot Price: ${spot_price_usd}")
        
        if option_id not in self.options:
            print(f"❌ Option {option_id} not found")
            return None
        
        option = self.options[option_id]
        
        # Create input hex for settlement
        option_id_hex = f"{option_id:0>8}"
        spot_price_hex = f"{int(spot_price_usd * 100):08x}"  # Convert to cents
        timestamp_hex = f"{int(time.time()):08x}"
        input_hex = option_id_hex + spot_price_hex + timestamp_hex + "00000000"  # Padding
        
        # Find available UTXO
        from create_setup_option_registration import find_best_utxo
        funding_tx_id, funding_index, funding_amount = find_best_utxo()
        if not funding_tx_id:
            print("❌ No available UTXO for settlement")
            return None
        
        # Generate unique n0, n1
        import hashlib
        timestamp_hash = hashlib.sha256(str(time.time()).encode()).hexdigest()
        n0 = str(int(timestamp_hash[:32], 16) | (1 << 255) | 1)
        n1 = str((int(timestamp_hash[32:], 16) + 2) | (1 << 255) | 1)
        
        # Setup data
        setup_data = {
            "n0": n0,
            "n1": n1,
            "prover_public_key": "b882af3fb540e1c2530d3d9e11993f206bb7626e9cfe19a03e7e42c75e19ad59",
            "input_hex": input_hex,
            "max_amount_of_steps": 16,
            "funding_tx_id": funding_tx_id,
            "funding_index": funding_index,
            "funding_amount": funding_amount,
            "step_fees": 30000,
            "amount_of_bits_wrong_step_search": 2,
            "amount_of_bits_per_digit_checksum": 4,
            "secret_origin_of_funds": "d8a1e1224e63135765bde9dc8a2c8e403eee8be73d3589d58c5ddbf9dce3fdf4",
            "prover_destination_address": "tb1qt8rdur557nz338g3lekc6458pj0dl63c0s9904",
            "verifier_destination_address": "tb1q8fg5jrspc7fn8jvpe5tfr7e5dlwvsh6xw8cq4j",
            "prover_signature_private_key": "d8a1e1224e63135765bde9dc8a2c8e403eee8be73d3589d58c5ddbf9dce3fdf4",
            "prover_signature_public_key": "03bf751f0d2d22e6f0163c9acaa14ae04e6e1a004cb4a24d893c1f86314e79d5de",
            "amount_of_input_words": 4,
            "elf_file_name": "option_settlement.elf"  # Different ELF for settlement
        }
        
        # Call prover setup
        print("📤 Creating settlement setup...")
        response = requests.post(
            f"{self.prover_url}/api/v1/setup",
            json=setup_data,
            timeout=300
        )
        
        if response.status_code == 200:
            result = response.json()
            setup_uuid = result.get("setup_uuid")
            print(f"✅ Settlement setup created: {setup_uuid}")
            
            # Calculate settlement result
            strike = option.get("strike", 0)
            option_type = option.get("option_type", "CALL")
            
            if option_type == "CALL":
                payoff = max(0, spot_price_usd - strike)
            else:  # PUT
                payoff = max(0, strike - spot_price_usd)
            
            # Update option tracking
            self.options[option_id]["settlement"] = {
                "settlement_setup": setup_uuid,
                "spot_price": spot_price_usd,
                "payoff_per_unit": payoff,
                "settled_at": datetime.now().isoformat()
            }
            
            print(f"💵 Payoff: ${payoff:.2f} per unit")
            
            # Save option registry
            self.save_option_registry()
            
            return setup_uuid
        else:
            print(f"❌ Settlement failed: {response.status_code}")
            return None
    
    def execute_next_step(self, setup_uuid: str):
        """Execute next step for any setup"""
        print(f"\n⚡ Executing next step for {setup_uuid}...")
        
        response = requests.post(
            f"{self.prover_url}/api/v1/next_step",
            json={"setup_uuid": setup_uuid},
            timeout=60
        )
        
        if response.status_code == 200:
            result = response.json()
            print(f"✅ Next step result: {result}")
            return result
        else:
            print(f"❌ Next step failed: {response.status_code}")
            return None
    
    def save_option_registry(self):
        """Save option registry to file"""
        with open("option_registry.json", "w") as f:
            json.dump(self.options, f, indent=2)
        print(f"💾 Option registry saved ({len(self.options)} options)")
    
    def load_option_registry(self):
        """Load option registry from file"""
        if os.path.exists("option_registry.json"):
            with open("option_registry.json", "r") as f:
                self.options = json.load(f)
            print(f"📂 Loaded {len(self.options)} options from registry")
    
    def list_options(self):
        """List all registered options"""
        print(f"\n{'='*60}")
        print(f"📋 REGISTERED OPTIONS")
        print(f"{'='*60}")
        
        if not self.options:
            print("No options registered yet")
            return
        
        for option_id, option in self.options.items():
            print(f"\n🔹 Option ID: {option_id}")
            print(f"   Type: {option.get('option_type', 'N/A')}")
            print(f"   Strike: ${option.get('strike', 0)}")
            print(f"   Expiry: {option.get('expiry', 'N/A')}")
            print(f"   Pool Size: {option.get('pool_size', 0)}")
            
            if "purchases" in option:
                print(f"   Purchases: {len(option['purchases'])}")
                
            if "settlement" in option:
                settlement = option["settlement"]
                print(f"   Settlement: ${settlement.get('spot_price', 0)} -> ${settlement.get('payoff_per_unit', 0)} payoff")


def main():
    """Main entry point for option flow management"""
    manager = OptionFlowManager()
    
    # Load existing data
    manager.load_existing_setups()
    manager.load_option_registry()
    
    print(f"\n{'='*60}")
    print(f"🚀 BitVMX Option Flow Manager")
    print(f"{'='*60}")
    
    while True:
        print(f"\nOptions:")
        print(f"1. Register new option")
        print(f"2. Purchase option")
        print(f"3. Settle option")
        print(f"4. Execute next step")
        print(f"5. List all options")
        print(f"6. Exit")
        
        choice = input("\nSelect option (1-6): ").strip()
        
        if choice == "1":
            # Register option
            option_type = input("Option type (CALL/PUT): ").strip().upper()
            strike = float(input("Strike price (USD): "))
            expiry = int(input("Days to expiry: "))
            pool_size = int(input("Pool size: "))
            
            option_id = manager.register_option(option_type, strike, expiry, pool_size)
            if option_id:
                print(f"📌 Option registered with ID: {option_id}")
                
        elif choice == "2":
            # Purchase option
            option_id = input("Option ID: ").strip()
            quantity = int(input("Quantity: "))
            premium = int(input("Premium (sats): "))
            
            setup_uuid = manager.purchase_option(option_id, quantity, premium)
            if setup_uuid:
                print(f"📌 Purchase setup: {setup_uuid}")
                
        elif choice == "3":
            # Settle option
            option_id = input("Option ID: ").strip()
            spot_price = float(input("Spot price at expiry (USD): "))
            
            setup_uuid = manager.settle_option(option_id, spot_price)
            if setup_uuid:
                print(f"📌 Settlement setup: {setup_uuid}")
                
        elif choice == "4":
            # Execute next step
            setup_uuid = input("Setup UUID: ").strip()
            manager.execute_next_step(setup_uuid)
            
        elif choice == "5":
            # List options
            manager.list_options()
            
        elif choice == "6":
            print("👋 Goodbye!")
            break
        
        else:
            print("❌ Invalid option")


if __name__ == "__main__":
    main()