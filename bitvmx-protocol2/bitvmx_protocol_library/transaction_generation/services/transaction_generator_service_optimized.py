"""
Optimized transaction generator with caching and parallel processing.
"""

import hashlib
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from functools import lru_cache
from typing import Dict, List, Optional, Any
import pickle

from bitvmx_protocol_library.bitvmx_protocol_definition.entities.bitvmx_protocol_setup_properties_dto import (
    BitVMXProtocolSetupPropertiesDTO,
)


class TransactionCache:
    """Simple cache for transaction generation results."""
    
    def __init__(self, max_size: int = 100):
        self.cache: Dict[str, Any] = {}
        self.max_size = max_size
        self.hits = 0
        self.misses = 0
    
    def get_key(self, *args, **kwargs) -> str:
        """Generate cache key from arguments."""
        key_data = pickle.dumps((args, sorted(kwargs.items())))
        return hashlib.sha256(key_data).hexdigest()
    
    def get(self, key: str) -> Optional[Any]:
        """Get value from cache."""
        if key in self.cache:
            self.hits += 1
            return self.cache[key]
        self.misses += 1
        return None
    
    def set(self, key: str, value: Any):
        """Set value in cache."""
        if len(self.cache) >= self.max_size:
            # Simple LRU: remove first item
            first_key = next(iter(self.cache))
            del self.cache[first_key]
        self.cache[key] = value
    
    def stats(self) -> Dict[str, int]:
        """Get cache statistics."""
        return {
            "hits": self.hits,
            "misses": self.misses,
            "size": len(self.cache),
            "hit_rate": self.hits / (self.hits + self.misses) if (self.hits + self.misses) > 0 else 0
        }


class TransactionGeneratorServiceOptimized:
    """Optimized transaction generator with caching and parallel processing."""
    
    def __init__(self, max_workers: int = 10):
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
        self.script_cache = TransactionCache(max_size=200)
        self.transaction_cache = TransactionCache(max_size=100)
    
    @lru_cache(maxsize=128)
    def _generate_script_cached(self, script_type: str, params_hash: str) -> Any:
        """Generate script with caching based on type and parameters hash."""
        # This would call the actual script generation logic
        # For now, it's a placeholder
        return f"script_{script_type}_{params_hash}"
    
    def _generate_single_transaction(
        self,
        tx_type: str,
        setup_properties: BitVMXProtocolSetupPropertiesDTO,
        index: int,
        **kwargs
    ) -> Any:
        """Generate a single transaction."""
        cache_key = self.transaction_cache.get_key(tx_type, index, **kwargs)
        cached_result = self.transaction_cache.get(cache_key)
        
        if cached_result is not None:
            return cached_result
        
        # Simulate transaction generation
        # In real implementation, this would call the actual transaction generation logic
        time.sleep(0.01)  # Simulate work
        
        result = {
            "type": tx_type,
            "index": index,
            "timestamp": time.time(),
            "data": f"transaction_{tx_type}_{index}"
        }
        
        self.transaction_cache.set(cache_key, result)
        return result
    
    def generate_transactions_parallel(
        self,
        setup_properties: BitVMXProtocolSetupPropertiesDTO,
        transaction_types: List[str],
        count_per_type: int = 10
    ) -> Dict[str, List[Any]]:
        """Generate multiple transactions in parallel."""
        start_time = time.time()
        results = {tx_type: [] for tx_type in transaction_types}
        futures = []
        
        # Submit all transaction generation tasks
        for tx_type in transaction_types:
            for i in range(count_per_type):
                future = self.executor.submit(
                    self._generate_single_transaction,
                    tx_type,
                    setup_properties,
                    i
                )
                futures.append((future, tx_type))
        
        # Collect results as they complete
        completed = 0
        total = len(futures)
        
        for future, tx_type in futures:
            try:
                result = future.result(timeout=30)
                results[tx_type].append(result)
                completed += 1
                
                if completed % 10 == 0:
                    print(f"[OPTIMIZED] Generated {completed}/{total} transactions...")
            except Exception as e:
                print(f"Error generating transaction {tx_type}: {e}")
        
        elapsed = time.time() - start_time
        print(f"[OPTIMIZED] Generated {completed} transactions in {elapsed:.2f} seconds")
        print(f"[OPTIMIZED] Cache stats - Script: {self.script_cache.stats()}")
        print(f"[OPTIMIZED] Cache stats - Transaction: {self.transaction_cache.stats()}")
        
        return results
    
    def generate_challenge_transactions(
        self,
        setup_properties: BitVMXProtocolSetupPropertiesDTO,
        challenge_types: List[str]
    ) -> Dict[str, Any]:
        """Generate challenge-related transactions with optimization."""
        start_time = time.time()
        
        # These can be generated in parallel as they don't depend on each other
        challenge_transactions = self.generate_transactions_parallel(
            setup_properties,
            challenge_types,
            count_per_type=1
        )
        
        elapsed = time.time() - start_time
        print(f"[OPTIMIZED] Challenge transactions generated in {elapsed:.2f} seconds")
        
        return challenge_transactions
    
    def __del__(self):
        """Cleanup thread pool on deletion."""
        if hasattr(self, 'executor'):
            self.executor.shutdown(wait=False)