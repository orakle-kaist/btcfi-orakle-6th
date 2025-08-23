"""
Optimized DTO persistence service with async I/O and MessagePack serialization.
"""

import asyncio
import json
import time
from pathlib import Path
from typing import Any, Dict, Optional
import hashlib

try:
    import msgpack
    HAS_MSGPACK = True
except ImportError:
    HAS_MSGPACK = False
    print("Warning: msgpack not installed. Using JSON fallback.")

try:
    import aiofiles
    HAS_AIOFILES = True
except ImportError:
    HAS_AIOFILES = False
    print("Warning: aiofiles not installed. Using synchronous I/O.")


class DTOPersistenceServiceOptimized:
    """Optimized persistence service for DTO objects."""
    
    def __init__(self, base_path: str = "optimized_data/"):
        self.base_path = Path(base_path)
        self.base_path.mkdir(parents=True, exist_ok=True)
        self.use_msgpack = HAS_MSGPACK
        self.use_async = HAS_AIOFILES
    
    def _get_file_path(self, key: str, extension: str = None) -> Path:
        """Get file path for a given key."""
        if extension is None:
            extension = ".msgpack" if self.use_msgpack else ".json"
        return self.base_path / f"{key}{extension}"
    
    def _serialize(self, data: Dict[str, Any]) -> bytes:
        """Serialize data to bytes."""
        if self.use_msgpack:
            return msgpack.packb(data, use_bin_type=True)
        else:
            return json.dumps(data, default=str).encode('utf-8')
    
    def _deserialize(self, data: bytes) -> Dict[str, Any]:
        """Deserialize bytes to data."""
        if self.use_msgpack:
            return msgpack.unpackb(data, raw=False)
        else:
            return json.loads(data.decode('utf-8'))
    
    async def save_async(self, key: str, data: Dict[str, Any]) -> float:
        """Save data asynchronously."""
        start_time = time.time()
        file_path = self._get_file_path(key)
        serialized = self._serialize(data)
        
        if self.use_async:
            async with aiofiles.open(file_path, 'wb') as f:
                await f.write(serialized)
        else:
            # Fallback to sync I/O in thread pool
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, self._save_sync, file_path, serialized)
        
        elapsed = time.time() - start_time
        print(f"[OPTIMIZED] Saved {key} ({len(serialized)} bytes) in {elapsed:.3f} seconds")
        return elapsed
    
    def _save_sync(self, file_path: Path, data: bytes):
        """Synchronous save (fallback)."""
        with open(file_path, 'wb') as f:
            f.write(data)
    
    def save(self, key: str, data: Dict[str, Any]) -> float:
        """Save data synchronously."""
        start_time = time.time()
        file_path = self._get_file_path(key)
        serialized = self._serialize(data)
        
        with open(file_path, 'wb') as f:
            f.write(serialized)
        
        elapsed = time.time() - start_time
        print(f"[OPTIMIZED] Saved {key} ({len(serialized)} bytes) in {elapsed:.3f} seconds")
        return elapsed
    
    async def load_async(self, key: str) -> Optional[Dict[str, Any]]:
        """Load data asynchronously."""
        start_time = time.time()
        file_path = self._get_file_path(key)
        
        if not file_path.exists():
            return None
        
        if self.use_async:
            async with aiofiles.open(file_path, 'rb') as f:
                data = await f.read()
        else:
            # Fallback to sync I/O in thread pool
            loop = asyncio.get_event_loop()
            data = await loop.run_in_executor(None, self._load_sync, file_path)
        
        result = self._deserialize(data)
        elapsed = time.time() - start_time
        print(f"[OPTIMIZED] Loaded {key} in {elapsed:.3f} seconds")
        return result
    
    def _load_sync(self, file_path: Path) -> bytes:
        """Synchronous load (fallback)."""
        with open(file_path, 'rb') as f:
            return f.read()
    
    def load(self, key: str) -> Optional[Dict[str, Any]]:
        """Load data synchronously."""
        start_time = time.time()
        file_path = self._get_file_path(key)
        
        if not file_path.exists():
            return None
        
        with open(file_path, 'rb') as f:
            data = f.read()
        
        result = self._deserialize(data)
        elapsed = time.time() - start_time
        print(f"[OPTIMIZED] Loaded {key} in {elapsed:.3f} seconds")
        return result
    
    async def save_batch_async(self, items: Dict[str, Dict[str, Any]]) -> float:
        """Save multiple items in parallel."""
        start_time = time.time()
        tasks = []
        
        for key, data in items.items():
            task = self.save_async(key, data)
            tasks.append(task)
        
        await asyncio.gather(*tasks)
        
        elapsed = time.time() - start_time
        print(f"[OPTIMIZED] Batch saved {len(items)} items in {elapsed:.3f} seconds")
        return elapsed
    
    def get_checksum(self, data: Dict[str, Any]) -> str:
        """Get checksum of data for caching purposes."""
        serialized = self._serialize(data)
        return hashlib.sha256(serialized).hexdigest()


class BitVMXSetupPersistenceOptimized:
    """Optimized persistence for BitVMX setup properties."""
    
    def __init__(self, base_path: str = "optimized_setups/"):
        self.persistence = DTOPersistenceServiceOptimized(base_path)
        self.checksum_cache = {}
    
    async def save_setup_properties_async(
        self,
        setup_uuid: str,
        properties_dto: Any
    ) -> float:
        """Save setup properties asynchronously."""
        # Convert DTO to dict
        data = properties_dto.dict() if hasattr(properties_dto, 'dict') else properties_dto
        
        # Check if data has changed
        checksum = self.persistence.get_checksum(data)
        if self.checksum_cache.get(setup_uuid) == checksum:
            print(f"[OPTIMIZED] Skipping save for {setup_uuid} - no changes detected")
            return 0
        
        # Save with optimizations
        elapsed = await self.persistence.save_async(f"setup_{setup_uuid}", data)
        self.checksum_cache[setup_uuid] = checksum
        
        return elapsed
    
    def save_setup_properties(
        self,
        setup_uuid: str,
        properties_dto: Any
    ) -> float:
        """Save setup properties synchronously."""
        # Convert DTO to dict
        data = properties_dto.dict() if hasattr(properties_dto, 'dict') else properties_dto
        
        # Check if data has changed
        checksum = self.persistence.get_checksum(data)
        if self.checksum_cache.get(setup_uuid) == checksum:
            print(f"[OPTIMIZED] Skipping save for {setup_uuid} - no changes detected")
            return 0
        
        # Save with optimizations
        elapsed = self.persistence.save(f"setup_{setup_uuid}", data)
        self.checksum_cache[setup_uuid] = checksum
        
        return elapsed
    
    async def load_setup_properties_async(self, setup_uuid: str) -> Optional[Dict[str, Any]]:
        """Load setup properties asynchronously."""
        return await self.persistence.load_async(f"setup_{setup_uuid}")
    
    def load_setup_properties(self, setup_uuid: str) -> Optional[Dict[str, Any]]:
        """Load setup properties synchronously."""
        return self.persistence.load(f"setup_{setup_uuid}")