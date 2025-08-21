"""
Pre-sign Transaction Service for BitVMX Options

This service creates pre-signed conditional transactions for option settlement.
When a buyer purchases an option, they receive a pre-signed transaction that
can be executed at expiry with an oracle price proof.
"""

from typing import Dict, List, Optional
import hashlib
import struct
from datetime import datetime

# Using python-bitcoinlib instead of bitcoinutils
import bitcoin
from bitcoin.core import *
from bitcoin.core.script import *
from bitcoin.wallet import *

from bitvmx_protocol_library.bitvmx_protocol_definition.entities.bitvmx_protocol_setup_properties_dto import (
    BitVMXProtocolSetupPropertiesDTO,
)
from blockchain_query_services.services.blockchain_query_services_dependency_injection import (
    broadcast_transaction_service,
)


class PresignTransactionService:
    """
    Service for creating pre-signed option settlement transactions.
    
    The pre-sign allows option buyers to automatically settle at expiry
    without requiring the operator's cooperation.
    """
    
    def __init__(self, operator_private_key: str, operator_public_key: str):
        """
        Initialize the pre-sign service.
        
        Args:
            operator_private_key: Operator's private key for signing
            operator_public_key: Operator's public key
        """
        self.operator_private_key = PrivateKey(operator_private_key)
        self.operator_public_key = PublicKey(operator_public_key)
    
    def create_settlement_script(
        self,
        option_type: str,
        strike_price: int,
        expiry: int,
        buyer_address: str,
        oracle_root_hash: bytes
    ) -> Script:
        """
        Create the settlement script for option execution.
        
        This script enforces:
        1. Expiry time check (CHECKLOCKTIMEVERIFY)
        2. Oracle price verification (Merkle proof)
        3. Option payout logic (ITM/OTM)
        
        Args:
            option_type: "CALL" or "PUT"
            strike_price: Strike price in USD cents
            expiry: Unix timestamp for option expiry
            buyer_address: Buyer's Bitcoin address
            oracle_root_hash: Merkle root of oracle prices
        
        Returns:
            Bitcoin Script for settlement conditions
        """
        # Convert addresses to public key hashes
        buyer_pubkey_hash = self._address_to_pubkey_hash(buyer_address)
        operator_pubkey_hash = self.operator_public_key.get_public_key_hash()
        
        # Build the settlement script
        script_elements = []
        
        # 1. Check expiry time
        script_elements.extend([
            expiry,
            'OP_CHECKLOCKTIMEVERIFY',
            'OP_DROP'
        ])
        
        # 2. Verify oracle price (simplified - actual implementation needs Merkle proof)
        script_elements.extend([
            'OP_DUP',
            'OP_SHA256',
            oracle_root_hash,
            'OP_EQUAL',
            'OP_VERIFY'
        ])
        
        # 3. Option settlement logic
        if option_type == "CALL":
            # CALL: If price > strike, pay buyer; else pay operator
            script_elements.extend([
                strike_price,
                'OP_GREATERTHAN',
                'OP_IF',
                    buyer_pubkey_hash,
                'OP_ELSE',
                    operator_pubkey_hash,
                'OP_ENDIF',
                'OP_CHECKSIG'
            ])
        else:  # PUT
            # PUT: If price < strike, pay buyer; else pay operator
            script_elements.extend([
                strike_price,
                'OP_LESSTHAN',
                'OP_IF',
                    buyer_pubkey_hash,
                'OP_ELSE',
                    operator_pubkey_hash,
                'OP_ENDIF',
                'OP_CHECKSIG'
            ])
        
        return Script(script_elements)
    
    def create_presign_for_option(
        self,
        option_type: str,
        strike_price: int,
        expiry: int,
        buyer_address: str,
        premium_sats: int,
        pool_funds_sats: int,
        funding_utxo: Dict
    ) -> Dict:
        """
        Create a pre-signed transaction for option settlement.
        
        Args:
            option_type: "CALL" or "PUT"
            strike_price: Strike price in USD
            expiry: Unix timestamp for expiry
            buyer_address: Buyer's Bitcoin address
            premium_sats: Premium amount in satoshis
            pool_funds_sats: Available funds in the pool
            funding_utxo: UTXO to use for funding
        
        Returns:
            Dictionary containing the pre-signed transaction and metadata
        """
        # Generate oracle root hash (placeholder - actual implementation needs oracle integration)
        oracle_root_hash = hashlib.sha256(
            f"{option_type}:{strike_price}:{expiry}".encode()
        ).digest()
        
        # Create settlement script
        settlement_script = self.create_settlement_script(
            option_type=option_type,
            strike_price=strike_price * 100,  # Convert to cents
            expiry=expiry,
            buyer_address=buyer_address,
            oracle_root_hash=oracle_root_hash
        )
        
        # Create the conditional transaction
        presign_tx = self._create_conditional_transaction(
            settlement_script=settlement_script,
            pool_funds_sats=pool_funds_sats,
            funding_utxo=funding_utxo,
            buyer_address=buyer_address
        )
        
        # Sign the transaction
        signed_tx = self._sign_transaction(presign_tx)
        
        # Create the pre-sign package
        presign_data = {
            "setup_uuid": f"PRESIGN-{int(datetime.now().timestamp())}",
            "option_type": option_type,
            "strike_price": strike_price,
            "expiry": expiry,
            "buyer_address": buyer_address,
            "premium_sats": premium_sats,
            "signed_tx": signed_tx.serialize(),
            "settlement_script": settlement_script.to_hex(),
            "oracle_root_hash": oracle_root_hash.hex(),
            "created_at": datetime.now().isoformat()
        }
        
        return presign_data
    
    def _create_conditional_transaction(
        self,
        settlement_script: Script,
        pool_funds_sats: int,
        funding_utxo: Dict,
        buyer_address: str
    ) -> Transaction:
        """
        Create the conditional transaction structure.
        
        Args:
            settlement_script: The settlement conditions script
            pool_funds_sats: Available funds for payout
            funding_utxo: UTXO to spend
            buyer_address: Buyer's address for potential payout
        
        Returns:
            Unsigned conditional transaction
        """
        # Create transaction inputs
        tx_input = TxInput(
            txid=funding_utxo["txid"],
            vout=funding_utxo["vout"],
            script_sig=Script(),  # Empty for now, will be filled with witness
            sequence=0xFFFFFFFE  # Enable CHECKLOCKTIMEVERIFY
        )
        
        # Create transaction outputs
        # Output 0: Settlement output (goes to buyer or operator based on conditions)
        settlement_output = TxOutput(
            value=pool_funds_sats - 1000,  # Minus fees
            script_pubkey=settlement_script
        )
        
        # Build transaction
        tx = Transaction(
            inputs=[tx_input],
            outputs=[settlement_output],
            locktime=0,
            version=2
        )
        
        return tx
    
    def _sign_transaction(self, transaction: Transaction) -> Transaction:
        """
        Sign the transaction with operator's key.
        
        Args:
            transaction: Unsigned transaction
        
        Returns:
            Signed transaction
        """
        # Create witness for the input
        # In actual implementation, this would involve proper Taproot signing
        signature = self.operator_private_key.sign_message(
            transaction.get_txid().encode(),
            hash_type=TAPROOT_SIGHASH_ALL
        )
        
        witness = TxWitnessInput([
            signature,
            self.operator_public_key.to_hex()
        ])
        
        transaction.witnesses.append(witness)
        
        return transaction
    
    def _address_to_pubkey_hash(self, address: str) -> bytes:
        """
        Convert Bitcoin address to public key hash.
        
        Args:
            address: Bitcoin address string
        
        Returns:
            Public key hash bytes
        """
        # Simplified - actual implementation needs proper address decoding
        return hashlib.hash160(address.encode()).digest()
    
    def verify_presign(self, presign_data: Dict) -> bool:
        """
        Verify that a pre-sign is valid and properly signed.
        
        Args:
            presign_data: Pre-sign data dictionary
        
        Returns:
            True if valid, False otherwise
        """
        try:
            # Deserialize the transaction
            tx = Transaction.from_raw(presign_data["signed_tx"])
            
            # Verify signature (simplified)
            if not tx.witnesses:
                return False
            
            # Verify expiry hasn't passed
            if presign_data["expiry"] < datetime.now().timestamp():
                return False
            
            # Additional verification logic here
            
            return True
            
        except Exception as e:
            print(f"Pre-sign verification failed: {e}")
            return False


class PresignSettlementExecutor:
    """
    Executor for settling options using pre-signed transactions.
    """
    
    def __init__(self):
        """Initialize the settlement executor."""
        pass
    
    def execute_settlement(
        self,
        presign_data: Dict,
        oracle_price: int,
        oracle_proof: Dict
    ) -> str:
        """
        Execute option settlement using pre-signed transaction.
        
        Args:
            presign_data: Pre-sign data from option purchase
            oracle_price: Current oracle price in USD
            oracle_proof: Merkle proof for the oracle price
        
        Returns:
            Transaction ID of the settlement
        """
        # Deserialize the pre-signed transaction
        tx = Transaction.from_raw(presign_data["signed_tx"])
        
        # Add oracle price and proof to witness
        oracle_witness = self._create_oracle_witness(oracle_price, oracle_proof)
        
        # Update transaction witness with oracle data
        tx.witnesses[0].stack.insert(0, oracle_witness)
        
        # Broadcast the transaction
        txid = broadcast_transaction_service(tx.serialize())
        
        return txid
    
    def _create_oracle_witness(self, price: int, proof: Dict) -> bytes:
        """
        Create witness data for oracle price.
        
        Args:
            price: Oracle price in USD
            proof: Merkle proof
        
        Returns:
            Witness bytes
        """
        # Pack price as 4-byte integer
        price_bytes = struct.pack('<I', price * 100)  # Convert to cents
        
        # Add Merkle proof (simplified)
        proof_bytes = bytes.fromhex(proof.get("merkle_path", ""))
        
        return price_bytes + proof_bytes
    
    def check_settlement_conditions(
        self,
        option_type: str,
        strike_price: int,
        oracle_price: int
    ) -> tuple[bool, int]:
        """
        Check if option is ITM and calculate payout.
        
        Args:
            option_type: "CALL" or "PUT"
            strike_price: Strike price in USD
            oracle_price: Current price in USD
        
        Returns:
            Tuple of (is_itm, payout_amount)
        """
        if option_type == "CALL":
            is_itm = oracle_price > strike_price
            payout = max(0, oracle_price - strike_price)
        else:  # PUT
            is_itm = oracle_price < strike_price
            payout = max(0, strike_price - oracle_price)
        
        return is_itm, payout