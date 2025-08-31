#!/usr/bin/env python3
"""
BitVMX API Client Service - Production-ready API client for Docker services
Follows microservice best practices with proper separation of concerns
"""

import json
import time
import uuid
import hashlib
import requests
from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass, asdict
from enum import Enum
import logging
from datetime import datetime
import os

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


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
class FundingPool:
    """Pre-funded UTXO pool for fast setup creation"""
    utxos: List[Dict[str, Any]]
    
    def allocate_utxo(self) -> Optional[Dict[str, Any]]:
        """Allocate a UTXO from the pool"""
        if self.utxos:
            return self.utxos.pop(0)
        return None
    
    def return_utxo(self, utxo: Dict[str, Any]):
        """Return unused UTXO to pool"""
        self.utxos.append(utxo)


class BitVMXApiClient:
    """
    Production API client for BitVMX Docker services
    Handles all communication with Prover/Verifier containers
    """
    
    def __init__(
        self,
        prover_url: str = "http://localhost:8081",
        verifier_url: str = "http://localhost:8082",
        timeout: int = 300,
        retry_count: int = 3
    ):
        self.prover_url = prover_url
        self.verifier_url = verifier_url
        self.timeout = timeout
        self.retry_count = retry_count
        
        # Session for connection pooling
        self.session = requests.Session()
        
        # Idempotency tracking
        self.idempotency_keys: Dict[str, str] = {}
        
        # Funding pool (in production, this would be from DB)
        self.funding_pool = FundingPool(utxos=[])
    
    def health_check(self) -> Tuple[bool, bool]:
        """Check if Docker services are running"""
        prover_ok = False
        verifier_ok = False
        
        try:
            resp = self.session.get(f"{self.prover_url}/healthcheck", timeout=2)
            prover_ok = resp.status_code == 200
            logger.info(f"Prover health: {resp.json() if prover_ok else 'DOWN'}")
        except Exception as e:
            logger.error(f"Prover health check failed: {e}")
        
        try:
            resp = self.session.get(f"{self.verifier_url}/healthcheck", timeout=2)
            verifier_ok = resp.status_code == 200
            logger.info(f"Verifier health: {resp.json() if verifier_ok else 'DOWN'}")
        except Exception as e:
            logger.error(f"Verifier health check failed: {e}")
        
        return prover_ok, verifier_ok
    
    def create_setup(
        self,
        option: OptionProduct,
        funding_utxo: Dict[str, Any],
        step_fees: int = 3000,
        max_steps: int = 100
    ) -> Optional[Dict[str, Any]]:
        """
        Create a new BitVMX setup for an option via API
        
        Args:
            option: Option product parameters
            funding_utxo: Pre-funded Taproot UTXO
            step_fees: Fee per protocol step
            max_steps: Maximum computation steps
            
        Returns:
            Setup result with UUID and transaction details
        """
        
        # Generate idempotency key
        idempotency_key = self._generate_idempotency_key(option, funding_utxo)
        
        # Check if already processed
        if idempotency_key in self.idempotency_keys:
            logger.info(f"Setup already exists for idempotency key: {idempotency_key}")
            return {"setup_uuid": self.idempotency_keys[idempotency_key], "cached": True}
        
        # Prepare setup input
        commitment = option.to_commitment()
        setup_input = {
            # Core parameters
            "max_amount_of_steps": max_steps,
            "amount_of_bits_wrong_step_search": 1,
            "funding_tx_id": funding_utxo["tx_id"],
            "funding_index": funding_utxo["index"],
            "funding_amount_of_satoshis": funding_utxo["amount"],
            "prover_destination_address": funding_utxo["address"],
            "amount_of_input_words": 4,  # For option data
            
            # Keys (in production, from secure key management)
            "secret_origin_of_funds": funding_utxo.get("private_key", ""),
            "prover_signature_private_key": funding_utxo.get("private_key", ""),
            "prover_signature_public_key": funding_utxo.get("public_key", ""),
            
            # Verifier (dummy for now)
            "verifier_signature_private_key": "c" * 64,
            "verifier_signature_public_key": "03" + "6" * 64,
            "verifier_destination_address": "tb1qvenenenen7nenen7nenen7nenen7nenen7nene07t93p",
            
            # Fees
            "step_fees_satoshis": step_fees,
            "max_fee_allowed": step_fees * 10,
            
            # Option commitment as public input
            "amount_of_public_inputs": 1,
            "list_of_public_inputs": [commitment],
            
            # Use verifier service if available
            "verifier_list": [f"{self.verifier_url}"] if self.verifier_url else []
        }
        
        # Add option metadata for tracking
        setup_input["metadata"] = {
            "option": asdict(option),
            "commitment": commitment,
            "created_at": datetime.utcnow().isoformat()
        }
        
        logger.info(f"Creating setup for option: {option.option_type.name} ${option.strike_price}")
        
        # Call API with retry logic
        for attempt in range(self.retry_count):
            try:
                response = self.session.post(
                    f"{self.prover_url}/api/v1/setup",
                    json=setup_input,
                    timeout=self.timeout,
                    headers={"X-Idempotency-Key": idempotency_key}
                )
                
                if response.status_code == 200:
                    result = response.json()
                    setup_uuid = result.get("setup_uuid")
                    
                    # Store idempotency mapping
                    self.idempotency_keys[idempotency_key] = setup_uuid
                    
                    logger.info(f"Setup created successfully: {setup_uuid}")
                    
                    # Store metadata locally
                    self._store_setup_metadata(setup_uuid, option, funding_utxo, result)
                    
                    return {
                        "setup_uuid": setup_uuid,
                        "commitment": commitment,
                        "result": result,
                        "option": asdict(option)
                    }
                
                elif response.status_code == 409:
                    # Already exists (idempotency)
                    logger.info("Setup already exists (409)")
                    return response.json()
                
                else:
                    logger.error(f"Setup failed with status {response.status_code}: {response.text}")
                    
                    # Retry on 5xx errors
                    if response.status_code >= 500 and attempt < self.retry_count - 1:
                        wait_time = 2 ** attempt  # Exponential backoff
                        logger.info(f"Retrying after {wait_time}s...")
                        time.sleep(wait_time)
                        continue
                    
                    return None
                    
            except requests.RequestException as e:
                logger.error(f"Request failed (attempt {attempt + 1}): {e}")
                if attempt < self.retry_count - 1:
                    time.sleep(2 ** attempt)
                    continue
                return None
        
        return None
    
    def fund_setup(self, setup_uuid: str) -> Optional[Dict[str, Any]]:
        """
        Fund a setup using /setup/fund endpoint
        Creates the initial Taproot UTXO
        """
        
        try:
            response = self.session.post(
                f"{self.prover_url}/api/v1/setup/{setup_uuid}/fund",
                timeout=self.timeout
            )
            
            if response.status_code == 200:
                result = response.json()
                logger.info(f"Setup funded: {result.get('funding_tx_id')}")
                return result
            else:
                logger.error(f"Funding failed: {response.text}")
                return None
                
        except requests.RequestException as e:
            logger.error(f"Funding request failed: {e}")
            return None
    
    def submit_input(self, setup_uuid: str, input_data: bytes) -> Optional[Dict[str, Any]]:
        """
        Submit input data to a setup via /input endpoint
        """
        
        try:
            response = self.session.post(
                f"{self.prover_url}/api/v1/input/{setup_uuid}",
                data=input_data.hex(),
                headers={"Content-Type": "text/plain"},
                timeout=self.timeout
            )
            
            if response.status_code == 200:
                result = response.json()
                logger.info(f"Input submitted for {setup_uuid}")
                return result
            else:
                logger.error(f"Input submission failed: {response.text}")
                return None
                
        except requests.RequestException as e:
            logger.error(f"Input submission failed: {e}")
            return None
    
    def next_step(self, setup_uuid: str) -> Optional[Dict[str, Any]]:
        """
        Execute next protocol step via /next_step endpoint
        """
        
        try:
            response = self.session.post(
                f"{self.prover_url}/api/v1/next_step/{setup_uuid}",
                timeout=self.timeout
            )
            
            if response.status_code == 200:
                result = response.json()
                step = result.get("current_step", "unknown")
                logger.info(f"Next step executed for {setup_uuid}: {step}")
                return result
            else:
                logger.error(f"Next step failed: {response.text}")
                return None
                
        except requests.RequestException as e:
            logger.error(f"Next step failed: {e}")
            return None
    
    def get_signed_transactions(self, setup_uuid: str) -> Optional[Dict[str, Any]]:
        """
        Get signed transactions for a setup
        """
        
        try:
            # Check local files first (Docker volume mount)
            local_path = f"prover_files/{setup_uuid}/signed_transactions.json"
            if os.path.exists(local_path):
                with open(local_path, 'r') as f:
                    return json.load(f)
            
            # Otherwise try API endpoint (if available)
            response = self.session.get(
                f"{self.prover_url}/api/v1/setup/{setup_uuid}/transactions",
                timeout=30
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"Failed to get transactions: {response.text}")
                return None
                
        except Exception as e:
            logger.error(f"Failed to get signed transactions: {e}")
            return None
    
    def _generate_idempotency_key(self, option: OptionProduct, funding_utxo: Dict[str, Any]) -> str:
        """Generate idempotency key for deduplication"""
        
        key_data = {
            "option": asdict(option),
            "funding": f"{funding_utxo['tx_id']}:{funding_utxo['index']}"
        }
        key_str = json.dumps(key_data, sort_keys=True)
        return hashlib.sha256(key_str.encode()).hexdigest()
    
    def _store_setup_metadata(
        self,
        setup_uuid: str,
        option: OptionProduct,
        funding_utxo: Dict[str, Any],
        api_result: Dict[str, Any]
    ):
        """Store setup metadata locally for tracking"""
        
        metadata = {
            "setup_uuid": setup_uuid,
            "option": asdict(option),
            "funding": funding_utxo,
            "api_result": api_result,
            "created_at": datetime.utcnow().isoformat()
        }
        
        # In production, store in database
        # For now, save to local file
        os.makedirs("prover_files", exist_ok=True)
        metadata_file = f"prover_files/{setup_uuid}_metadata.json"
        
        with open(metadata_file, 'w') as f:
            json.dump(metadata, f, indent=2)
        
        logger.info(f"Metadata saved: {metadata_file}")


def main():
    """Example usage"""
    
    # Initialize API client
    client = BitVMXApiClient()
    
    # Check health
    prover_ok, verifier_ok = client.health_check()
    if not prover_ok:
        print("❌ Prover service not running. Start with: docker compose up prover-backend")
        return
    
    # Create option
    option = OptionProduct(
        option_type=OptionType.CALL,
        strike_price=70000,
        quantity=0.1,
        expiry=int(time.time()) + 86400 * 30  # 30 days
    )
    
    # Use existing funding from Mutinynet
    funding_utxo = {
        "tx_id": "66115221c1c2ec635371a7ea46eeda175e766b51982fe5b2e710793be8523dff",
        "index": 0,
        "amount": 199997187,
        "private_key": "d8a1e1224e63135765bde9dc8a2c8e403eee8be73d3589d58c5ddbf9dce3fdf4",
        "public_key": "03bf751f0d2d22e6f0163c9acaa14ae04e6e1a004cb4a24d893c1f86314e79d5de",
        "address": "tb1qt8rdur557nz338g3lekc6458pj0dl63c0s9904"
    }
    
    print("\n=== Creating BitVMX Setup via API ===")
    result = client.create_setup(
        option=option,
        funding_utxo=funding_utxo,
        step_fees=3000,
        max_steps=100
    )
    
    if result:
        print(f"\n✅ Setup created successfully!")
        print(f"   UUID: {result['setup_uuid']}")
        print(f"   Commitment: {result['commitment']}")
        print(f"   Option: {result['option']['option_type']} ${result['option']['strike_price']:,.0f}")
        
        # Get signed transactions
        setup_uuid = result['setup_uuid']
        transactions = client.get_signed_transactions(setup_uuid)
        
        if transactions:
            print(f"\n📝 Signed transactions ready:")
            for tx_type in ['hash_result_tx', 'trigger_protocol_tx']:
                if tx_type in transactions:
                    print(f"   - {tx_type}: {len(transactions[tx_type]) if isinstance(transactions[tx_type], str) else 'list'}")
    else:
        print("❌ Failed to create setup")


if __name__ == "__main__":
    main()