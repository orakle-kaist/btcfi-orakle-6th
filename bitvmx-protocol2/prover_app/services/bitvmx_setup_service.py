#!/usr/bin/env python3
from prover_app.common.hexsafe import bfromhex_safe
"""
BitVMX Setup Service - Parameterized setup creation for BTCFi options
Handles multiple option products with different parameters
"""

import json
import uuid
import hashlib
import os
import time
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from enum import Enum

from bitcoinutils.setup import setup
from bitcoinutils.keys import PrivateKey, PublicKey, P2wpkhAddress
from bitcoinutils.transactions import Transaction

from bitvmx_protocol_library.bitvmx_protocol_definition.entities.bitvmx_protocol_setup_properties_dto import (
    BitVMXProtocolSetupPropertiesDTO,
)
from bitvmx_protocol_library.bitvmx_protocol_definition.entities.bitvmx_protocol_properties_dto import (
    BitVMXProtocolPropertiesDTO,
)
from bitvmx_protocol_library.script_generation.services.bitvmx_bitcoin_scripts_generator_service import (
    BitVMXBitcoinScriptsGeneratorService,
)
from bitvmx_protocol_library.transaction_generation.services.transaction_generator_from_public_keys_service_optimized import (
    TransactionGeneratorFromPublicKeysServiceOptimized,
)
from bitvmx_protocol_library.transaction_generation.services.generate_signatures_service import (
    GenerateSignaturesService,
)
from bitvmx_protocol_library.transaction_generation.services.apply_signatures_to_transactions_service import (
    ApplySignaturesToTransactionsService,
)
from bitvmx_protocol_library.persistence.services.dto_persistence_service_optimized import (
    DTOPersistenceServiceOptimized,
)

# Setup network
setup('testnet')

class OptionType(Enum):
    CALL = 0
    PUT = 1

@dataclass
class OptionProduct:
    """Option product parameters"""
    option_type: OptionType
    strike_price: float  # USD
    quantity: float      # BTC
    expiry: int         # Unix timestamp
    oracle_count: int = 3
    
    def to_commitment(self) -> str:
        """Generate commitment hash for option"""
        data = {
            "type": self.option_type.name,
            "strike": self.strike_price,
            "quantity": self.quantity,
            "expiry": self.expiry,
            "oracles": self.oracle_count
        }
        json_str = json.dumps(data, sort_keys=True, separators=(',', ':'))
        return hashlib.sha256(json_str.encode()).hexdigest()[:8]

@dataclass
class FundingSource:
    """Funding UTXO information"""
    tx_id: str
    index: int
    amount: int  # satoshis
    private_key: str
    public_key: str
    address: str

class BitvmxSetupService:
    """Service for creating and managing BitVMX setups for options"""
    
    def __init__(self, base_dir: str = "prover_files", elf_file_name: str = None):
        self.base_dir = base_dir
        self.persistence = DTOPersistenceServiceOptimized(base_dir)
        self.scripts_generator = BitVMXBitcoinScriptsGeneratorService(elf_file_name=elf_file_name)
        self.tx_generator = TransactionGeneratorFromPublicKeysServiceOptimized()
        self.signature_service = GenerateSignaturesService()
        self.elf_file_name = elf_file_name
        self.apply_signatures_service = ApplySignaturesToTransactionsService()
        
        # Default protocol parameters (optimized for options)
        self.default_protocol_params = {
            "n0": 2,
            "n1": 2,
            "amount_of_nibbles_hash": 4,
            "amount_of_bits_wrong_step_search": 1,
            "amount_of_bits_per_digit_checksum": 4,
            "max_amount_of_steps": 50,  # Reduced for faster execution
            "amount_of_input_words": 4,  # Enough for option data
            "amount_of_bits_per_digit_hex": 4,
            "amount_of_wrong_step_search_iterations": 2,
            "amount_of_wrong_step_search_hashes_per_iteration": 1,
            "amount_of_bits_challenged_step": 4,
            "trace_challenge_amount_of_rounds": 1
        }
        
        # Cache for active setups
        self.active_setups: Dict[str, Dict[str, Any]] = {}
    
    def create_option_setup(
        self,
        option: OptionProduct,
        funding: FundingSource,
        step_fees: int = 3000,
        verifier_key: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Create a new BitVMX setup for an option product
        
        Args:
            option: Option product parameters
            funding: Funding UTXO information
            step_fees: Fee per protocol step in satoshis
            verifier_key: Optional verifier private key (uses dummy if not provided)
            
        Returns:
            Dict with setup_uuid and transaction details
        """
        
        setup_uuid = str(uuid.uuid4())
        print(f"\n=== Creating Setup for Option ===")
        print(f"UUID: {setup_uuid}")
        print(f"Type: {option.option_type.name}")
        print(f"Strike: ${option.strike_price:,.2f}")
        print(f"Quantity: {option.quantity:.4f} BTC")
        print(f"Expiry: {time.strftime('%Y-%m-%d %H:%M', time.localtime(option.expiry))}")
        
        # Generate commitment
        commitment = option.to_commitment()
        print(f"Commitment: {commitment}")
        
        # Create keys
        prover_private_key = PrivateKey(secret_exponent=int(funding.private_key, 16))
        prover_public_key = prover_private_key.get_public_key()
        prover_address = P2wpkhAddress.from_public_key(prover_public_key)
        
        # Verifier keys (dummy or provided)
        if verifier_key:
            verifier_private_key = PrivateKey(secret_exponent=int(verifier_key, 16))
        else:
            # Use dummy verifier for single-party setup
            verifier_private_key = PrivateKey(secret_exponent=int("c" * 64, 16))
        
        verifier_public_key = verifier_private_key.get_public_key()
        verifier_address = P2wpkhAddress.from_public_key(verifier_public_key)
        
        # Destroyed keys for Taproot
        destroyed_key = PublicKey.from_hex("0279BE667EF9DCBBAC55A06295CE870B07029BFCDB2DCE28D959F2815B16F81798")
        
        # Create protocol properties
        protocol_properties = BitVMXProtocolPropertiesDTO(**self.default_protocol_params)
        
        # Create input hex from option data
        input_hex = self._create_option_input_hex(option, commitment)
        
        # Create setup DTO
        setup_dto = BitVMXProtocolSetupPropertiesDTO(
            uuid=setup_uuid,
            bitvmx_protocol_properties_dto=protocol_properties,
            signature_public_keys=[prover_public_key.to_hex(), verifier_public_key.to_hex()],
            prover_signature_public_key=prover_public_key.to_hex(),
            verifier_signature_public_key=verifier_public_key.to_hex(),
            prover_destination_address=prover_address.to_address(),
            verifier_destination_address=verifier_address.to_address(),
            funding_tx_id=funding.tx_id,
            funding_index=funding.index,
            funding_amount_of_satoshis=funding.amount,
            step_fees_satoshis=step_fees,
            input_hex=input_hex,
            unspendable_public_key=destroyed_key,
            prover_destroyed_public_key=destroyed_key,
            verifier_destroyed_public_key=destroyed_key,
            seed_unspendable_public_key=destroyed_key,
            verifier_address_dict={
                0: verifier_address.to_address(),
                1: verifier_address.to_address()
            }
        )
        
        print("\n📝 Generating Bitcoin scripts...")
        setup_dto.bitvmx_bitcoin_scripts_dto = self.scripts_generator(setup_dto)
        
        print("📦 Generating transactions...")
        setup_dto.bitvmx_transactions_dto = self.tx_generator(setup_dto)
        
        print("🔏 Generating signatures...")
        signatures = self.signature_service(
            setup_dto,
            prover_private_key.to_hex(),
            verifier_private_key.to_hex()
        )
        
        print("✍️  Applying signatures...")
        signed_transactions = self.apply_signatures_service(
            setup_dto,
            signatures,
            signatures.verifier_signatures_dto if hasattr(signatures, 'verifier_signatures_dto') else None
        )
        
        # Save setup
        print("💾 Saving setup...")
        self._save_setup(setup_uuid, setup_dto, signed_transactions, option, funding)
        
        # Cache setup
        self.active_setups[setup_uuid] = {
            "option": option,
            "funding": funding,
            "created_at": time.time(),
            "commitment": commitment,
            "signed_transactions": signed_transactions
        }
        
        # Verify witness
        witness_ok = self._verify_witness(signed_transactions)
        
        return {
            "setup_uuid": setup_uuid,
            "commitment": commitment,
            "witness_verified": witness_ok,
            "transactions": {
                "hash_result_tx": self._get_tx_info(signed_transactions.get("hash_result_tx")),
                "trigger_protocol_tx": self._get_tx_info(signed_transactions.get("trigger_protocol_tx")),
                "search_hash_count": len(signed_transactions.get("search_hash_tx_list", [])),
                "search_choice_count": len(signed_transactions.get("search_choice_tx_list", []))
            }
        }
    
    def _create_option_input_hex(self, option: OptionProduct, commitment: str) -> str:
        """Create input hex from option parameters"""
        # Pack option data into hex (simplified for demo)
        # Format: [type:4][strike:8][quantity:8][expiry:8][commitment:4]
        
        option_type = option.option_type.value.to_bytes(4, 'big')
        strike = int(option.strike_price * 100).to_bytes(8, 'big')  # Cents
        quantity = int(option.quantity * 1e8).to_bytes(8, 'big')    # Satoshis
        expiry = option.expiry.to_bytes(8, 'big')
        commitment_bytes = bfromhex_safe(commitment)
        
        input_data = option_type + strike + quantity + expiry + commitment_bytes
        
        # Pad to required length
        while len(input_data) < 64:  # Minimum 64 bytes
            input_data += b'\x00'
        
        return input_data.hex()
    
    def _save_setup(
        self,
        setup_uuid: str,
        setup_dto: BitVMXProtocolSetupPropertiesDTO,
        signed_transactions: Dict[str, Any],
        option: OptionProduct,
        funding: FundingSource
    ):
        """Save setup files to disk"""
        
        setup_dir = os.path.join(self.base_dir, setup_uuid)
        os.makedirs(setup_dir, exist_ok=True)
        
        # Save setup properties
        self.persistence.save_setup_properties_dto(setup_dto)
        
        # Save signed transactions
        with open(os.path.join(setup_dir, "signed_transactions.json"), "w") as f:
            json.dump(signed_transactions, f, indent=2)
        
        # Save option metadata
        option_meta = {
            "setup_uuid": setup_uuid,
            "option": {
                "type": option.option_type.name,
                "strike": option.strike_price,
                "quantity": option.quantity,
                "expiry": option.expiry,
                "oracle_count": option.oracle_count
            },
            "funding": {
                "tx_id": funding.tx_id,
                "index": funding.index,
                "amount": funding.amount,
                "address": funding.address
            },
            "created_at": time.time(),
            "commitment": option.to_commitment()
        }
        
        with open(os.path.join(setup_dir, "option_metadata.json"), "w") as f:
            json.dump(option_meta, f, indent=2)
    
    def _verify_witness(self, signed_transactions: Dict[str, Any]) -> bool:
        """Verify witness is properly included"""
        
        if "search_hash_tx_list" in signed_transactions and signed_transactions["search_hash_tx_list"]:
            first_tx = signed_transactions["search_hash_tx_list"][0]
            if isinstance(first_tx, str):
                # Check for witness marker and reasonable length
                has_witness = "0001" in first_tx[:20] and len(first_tx) > 200
                if has_witness:
                    print(f"✅ Witness verified (length: {len(first_tx)} bytes)")
                    return True
                else:
                    print(f"⚠️  Witness may be missing (length: {len(first_tx)} bytes)")
                    return False
        return False
    
    def _get_tx_info(self, tx_hex: Optional[str]) -> Optional[Dict[str, Any]]:
        """Get transaction info from hex"""
        
        if not tx_hex:
            return None
        
        try:
            tx = Transaction.from_raw(tx_hex)
            return {
                "txid": tx.get_txid(),
                "size": len(tx_hex) // 2,
                "has_witness": "0001" in tx_hex[:20]
            }
        except:
            return None
    
    def get_setup(self, setup_uuid: str) -> Optional[Dict[str, Any]]:
        """Get setup details by UUID"""
        
        # Check cache first
        if setup_uuid in self.active_setups:
            return self.active_setups[setup_uuid]
        
        # Load from disk
        setup_dir = os.path.join(self.base_dir, setup_uuid)
        meta_file = os.path.join(setup_dir, "option_metadata.json")
        
        if os.path.exists(meta_file):
            with open(meta_file, "r") as f:
                return json.load(f)
        
        return None
    
    def list_setups(self) -> List[Dict[str, Any]]:
        """List all available setups"""
        
        setups = []
        
        for setup_dir in os.listdir(self.base_dir):
            meta_file = os.path.join(self.base_dir, setup_dir, "option_metadata.json")
            if os.path.exists(meta_file):
                with open(meta_file, "r") as f:
                    meta = json.load(f)
                    setups.append({
                        "uuid": setup_dir,
                        "option_type": meta["option"]["type"],
                        "strike": meta["option"]["strike"],
                        "quantity": meta["option"]["quantity"],
                        "expiry": meta["option"]["expiry"],
                        "created_at": meta["created_at"]
                    })
        
        return sorted(setups, key=lambda x: x["created_at"], reverse=True)


def main():
    """Example usage"""
    
    service = BitvmxSetupService()
    
    # Example: Create multiple option setups
    options = [
        OptionProduct(OptionType.CALL, 70000, 0.1, int(time.time()) + 86400 * 30),  # 70K call, 30 days
        OptionProduct(OptionType.PUT, 60000, 0.05, int(time.time()) + 86400 * 7),   # 60K put, 7 days
        OptionProduct(OptionType.CALL, 75000, 0.2, int(time.time()) + 86400 * 90),  # 75K call, 90 days
    ]
    
    # Our funding from Mutinynet
    funding = FundingSource(
        tx_id="66115221c1c2ec635371a7ea46eeda175e766b51982fe5b2e710793be8523dff",
        index=0,
        amount=199997187,
        private_key="d8a1e1224e63135765bde9dc8a2c8e403eee8be73d3589d58c5ddbf9dce3fdf4",
        public_key="03bf751f0d2d22e6f0163c9acaa14ae04e6e1a004cb4a24d893c1f86314e79d5de",
        address="tb1qt8rdur557nz338g3lekc6458pj0dl63c0s9904"
    )
    
    print("=" * 60)
    print("BITVMX OPTION SETUP SERVICE")
    print("=" * 60)
    
    for i, option in enumerate(options):
        print(f"\n[{i+1}/{len(options)}] Creating setup for option...")
        
        result = service.create_option_setup(
            option=option,
            funding=funding,  # In production, use different UTXOs
            step_fees=3000
        )
        
        print(f"\n✅ Setup created:")
        print(f"   UUID: {result['setup_uuid']}")
        print(f"   Commitment: {result['commitment']}")
        print(f"   Witness OK: {result['witness_verified']}")
        print(f"   Transactions: {result['transactions']['search_hash_count']} hash, {result['transactions']['search_choice_count']} choice")
    
    # List all setups
    print("\n" + "=" * 60)
    print("ALL SETUPS")
    print("=" * 60)
    
    setups = service.list_setups()
    for setup in setups:
        print(f"\n{setup['uuid'][:8]}... - {setup['option_type']} ${setup['strike']:,.0f} x {setup['quantity']} BTC")


if __name__ == "__main__":
    main()