"""
Oracle Price Verifier for BitVMX

Integrates with the Oracle Node system to fetch and verify BTC prices
from multiple exchanges (Binance, Coinbase, Kraken) and creates
verifiable proofs for BitVMX settlement.
"""

import hashlib
import struct
import json
from typing import Dict, List, Optional, Tuple
from datetime import datetime
import asyncio
import aiohttp


class OraclePriceVerifier:
    """
    Verifies oracle prices and creates Merkle proofs for BitVMX verification.
    
    This class interfaces with the Oracle Node system to:
    1. Collect prices from multiple exchanges
    2. Verify 2/3 consensus
    3. Create Merkle proofs for on-chain verification
    """
    
    def __init__(self, oracle_nodes: List[str], consensus_threshold: float = 0.67):
        """
        Initialize the Oracle Price Verifier.
        
        Args:
            oracle_nodes: List of Oracle Node URLs
            consensus_threshold: Minimum consensus ratio (default 2/3)
        """
        self.oracle_nodes = oracle_nodes
        self.consensus_threshold = consensus_threshold
    
    async def collect_oracle_prices(self) -> List[Dict]:
        """
        Collect BTC prices from all configured Oracle Nodes.
        
        Returns:
            List of price data from each oracle
        """
        prices = []
        
        async with aiohttp.ClientSession() as session:
            tasks = []
            for node_url in self.oracle_nodes:
                tasks.append(self._fetch_price_from_node(session, node_url))
            
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            for result in results:
                if isinstance(result, dict):
                    prices.append(result)
                else:
                    print(f"Failed to fetch from oracle: {result}")
        
        return prices
    
    async def _fetch_price_from_node(self, session: aiohttp.ClientSession, node_url: str) -> Dict:
        """
        Fetch price from a single Oracle Node.
        
        Args:
            session: aiohttp session
            node_url: Oracle Node URL
        
        Returns:
            Price data dictionary
        """
        try:
            async with session.get(f"{node_url}/api/price/btc") as response:
                if response.status == 200:
                    data = await response.json()
                    return {
                        "price": data["price"],
                        "timestamp": data["timestamp"],
                        "source": data["source"],
                        "signature": data.get("signature", "")
                    }
        except Exception as e:
            print(f"Error fetching from {node_url}: {e}")
            raise
    
    def verify_consensus(self, prices: List[Dict]) -> Tuple[bool, float]:
        """
        Verify that prices meet consensus threshold.
        
        Args:
            prices: List of price data from oracles
        
        Returns:
            Tuple of (consensus_met, consensus_price)
        """
        if not prices:
            return False, 0.0
        
        # Extract price values
        price_values = [p["price"] for p in prices]
        
        # Calculate median price
        price_values.sort()
        n = len(price_values)
        if n % 2 == 0:
            median_price = (price_values[n//2 - 1] + price_values[n//2]) / 2
        else:
            median_price = price_values[n//2]
        
        # Count prices within 1% of median
        tolerance = median_price * 0.01
        consensus_count = sum(
            1 for p in price_values 
            if abs(p - median_price) <= tolerance
        )
        
        consensus_ratio = consensus_count / len(prices)
        consensus_met = consensus_ratio >= self.consensus_threshold
        
        return consensus_met, median_price
    
    def create_merkle_tree(self, prices: List[Dict]) -> Dict:
        """
        Create a Merkle tree from oracle prices.
        
        Args:
            prices: List of price data
        
        Returns:
            Merkle tree structure with root and proofs
        """
        # Create leaf nodes
        leaves = []
        for price_data in prices:
            leaf = self._create_leaf_hash(price_data)
            leaves.append(leaf)
        
        # Build Merkle tree
        tree_levels = [leaves]
        current_level = leaves
        
        while len(current_level) > 1:
            next_level = []
            for i in range(0, len(current_level), 2):
                if i + 1 < len(current_level):
                    combined = current_level[i] + current_level[i + 1]
                else:
                    combined = current_level[i] + current_level[i]
                
                parent = hashlib.sha256(combined).digest()
                next_level.append(parent)
            
            tree_levels.append(next_level)
            current_level = next_level
        
        merkle_root = current_level[0] if current_level else b'\x00' * 32
        
        return {
            "root": merkle_root.hex(),
            "leaves": [leaf.hex() for leaf in leaves],
            "levels": [[node.hex() for node in level] for level in tree_levels]
        }
    
    def _create_leaf_hash(self, price_data: Dict) -> bytes:
        """
        Create a leaf hash from price data.
        
        Args:
            price_data: Price information dictionary
        
        Returns:
            32-byte hash
        """
        # Serialize price data
        data_str = f"{price_data['price']}:{price_data['timestamp']}:{price_data['source']}"
        return hashlib.sha256(data_str.encode()).digest()
    
    def create_merkle_proof(self, prices: List[Dict], target_price: float) -> Dict:
        """
        Create a Merkle proof for a specific price.
        
        Args:
            prices: List of all prices
            target_price: The price to create proof for
        
        Returns:
            Merkle proof dictionary
        """
        merkle_tree = self.create_merkle_tree(prices)
        
        # Find the target price in leaves
        target_index = -1
        for i, price_data in enumerate(prices):
            if abs(price_data["price"] - target_price) < 0.01:
                target_index = i
                break
        
        if target_index == -1:
            raise ValueError("Target price not found in price list")
        
        # Build proof path
        proof_path = []
        current_index = target_index
        
        for level in merkle_tree["levels"][:-1]:
            if current_index % 2 == 0:
                # Need right sibling
                sibling_index = current_index + 1
                if sibling_index < len(level):
                    proof_path.append({
                        "position": "right",
                        "hash": level[sibling_index]
                    })
            else:
                # Need left sibling
                sibling_index = current_index - 1
                proof_path.append({
                    "position": "left",
                    "hash": level[sibling_index]
                })
            
            current_index = current_index // 2
        
        return {
            "root": merkle_tree["root"],
            "leaf": merkle_tree["leaves"][target_index],
            "path": proof_path,
            "index": target_index
        }
    
    async def create_price_proof(self, target_timestamp: Optional[int] = None) -> Dict:
        """
        Create a complete price proof for BitVMX verification.
        
        Args:
            target_timestamp: Optional specific timestamp to fetch prices for
        
        Returns:
            Complete proof package for settlement
        """
        # Collect prices from oracles
        prices = await self.collect_oracle_prices()
        
        if not prices:
            raise ValueError("No oracle prices available")
        
        # Verify consensus
        consensus_met, consensus_price = self.verify_consensus(prices)
        
        if not consensus_met:
            raise ValueError("Oracle consensus not met")
        
        # Create Merkle proof
        merkle_proof = self.create_merkle_proof(prices, consensus_price)
        
        # Create BitVMX-compatible proof
        proof_data = {
            "price": int(consensus_price * 100),  # Convert to cents
            "price_usd": consensus_price,
            "timestamp": int(datetime.now().timestamp()),
            "consensus_ratio": len(prices) / len(self.oracle_nodes),
            "merkle_root": merkle_proof["root"],
            "merkle_proof": merkle_proof,
            "oracle_signatures": [p.get("signature", "") for p in prices],
            "sources": [p["source"] for p in prices]
        }
        
        return proof_data
    
    def convert_price_to_bitvmx_input(self, price: float) -> str:
        """
        Convert oracle price to BitVMX 32-byte hex input format.
        
        Args:
            price: Price in USD
        
        Returns:
            32-byte hex string for BitVMX input
        """
        # Convert to cents and pack as 4-byte integer
        price_cents = int(price * 100)
        price_bytes = struct.pack('<I', price_cents)
        
        # Pad to 32 bytes
        padded = price_bytes + b'\x00' * 28
        
        return padded.hex()
    
    def verify_merkle_proof(self, leaf: str, proof: Dict, root: str) -> bool:
        """
        Verify a Merkle proof.
        
        Args:
            leaf: Leaf hash hex string
            proof: Merkle proof with path
            root: Expected root hash hex string
        
        Returns:
            True if proof is valid
        """
        current_hash = bytes.fromhex(leaf)
        
        for step in proof["path"]:
            sibling_hash = bytes.fromhex(step["hash"])
            
            if step["position"] == "left":
                combined = sibling_hash + current_hash
            else:
                combined = current_hash + sibling_hash
            
            current_hash = hashlib.sha256(combined).digest()
        
        return current_hash.hex() == root


class OracleBitVMXBridge:
    """
    Bridge between Oracle system and BitVMX protocol.
    """
    
    def __init__(self, oracle_verifier: OraclePriceVerifier):
        """
        Initialize the bridge.
        
        Args:
            oracle_verifier: Oracle price verifier instance
        """
        self.oracle_verifier = oracle_verifier
    
    async def prepare_settlement_data(
        self,
        option_type: str,
        strike_price: float,
        expiry: int
    ) -> Dict:
        """
        Prepare all necessary data for option settlement.
        
        Args:
            option_type: "CALL" or "PUT"
            strike_price: Strike price in USD
            expiry: Expiry timestamp
        
        Returns:
            Settlement data package
        """
        # Get current oracle price and proof
        price_proof = await self.oracle_verifier.create_price_proof()
        
        # Convert to BitVMX format
        bitvmx_input = self.oracle_verifier.convert_price_to_bitvmx_input(
            price_proof["price_usd"]
        )
        
        # Calculate settlement
        current_price = price_proof["price_usd"]
        
        if option_type == "CALL":
            is_itm = current_price > strike_price
            payout = max(0, current_price - strike_price)
        else:  # PUT
            is_itm = current_price < strike_price
            payout = max(0, strike_price - current_price)
        
        # Convert payout to satoshis (assuming BTC price)
        btc_price = current_price  # If this is BTC/USD
        payout_btc = payout / btc_price if btc_price > 0 else 0
        payout_sats = int(payout_btc * 100_000_000)
        
        return {
            "option_type": option_type,
            "strike_price": strike_price,
            "current_price": current_price,
            "expiry": expiry,
            "is_itm": is_itm,
            "payout_usd": payout,
            "payout_sats": payout_sats,
            "bitvmx_input": bitvmx_input,
            "oracle_proof": price_proof,
            "settlement_time": int(datetime.now().timestamp())
        }