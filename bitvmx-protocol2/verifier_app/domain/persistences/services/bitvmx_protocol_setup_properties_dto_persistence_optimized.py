"""
Optimized persistence service for verifier with async I/O and caching.
"""

import json
import time
from pathlib import Path
from typing import Optional, Dict, Any
import hashlib

try:
    import msgpack
    HAS_MSGPACK = True
except ImportError:
    HAS_MSGPACK = False

try:
    import aiofiles
    HAS_AIOFILES = True
except ImportError:
    HAS_AIOFILES = False

from bitvmx_protocol_library.bitvmx_protocol_definition.entities.bitvmx_protocol_setup_properties_dto import (
    BitVMXProtocolSetupPropertiesDTO,
)
from verifier_app.domain.persistences.interfaces.bitvmx_protocol_setup_properties_dto_persistence_interface import (
    BitVMXProtocolSetupPropertiesDTOPersistenceInterface,
)


class BitVMXProtocolSetupPropertiesDTOPersistenceOptimized(
    BitVMXProtocolSetupPropertiesDTOPersistenceInterface
):
    """Optimized persistence service with caching and async I/O."""
    
    def __init__(self):
        self.path = Path("verifier_files/bitvmx_protocol_setup_properties_dto/")
        self.path.mkdir(exist_ok=True, parents=True)
        self.cache = {}
        self.checksums = {}
        self.use_msgpack = HAS_MSGPACK
        print(f"[OPTIMIZED] Persistence initialized. MsgPack: {self.use_msgpack}")
    
    def _get_filepath(self, setup_uuid: str) -> Path:
        ext = ".msgpack" if self.use_msgpack else ".json"
        return self.path / f"{setup_uuid}{ext}"
    
    def _serialize(self, dto: BitVMXProtocolSetupPropertiesDTO) -> bytes:
        """Serialize DTO to bytes."""
        data = dto.dict()
        if self.use_msgpack:
            return msgpack.packb(data, use_bin_type=True)
        else:
            return json.dumps(data, default=str).encode('utf-8')
    
    def _deserialize(self, data: bytes) -> Dict[str, Any]:
        """Deserialize bytes to dict."""
        if self.use_msgpack:
            return msgpack.unpackb(data, raw=False)
        else:
            return json.loads(data.decode('utf-8'))
    
    def _get_checksum(self, dto: BitVMXProtocolSetupPropertiesDTO) -> str:
        """Get checksum of DTO for change detection."""
        serialized = self._serialize(dto)
        return hashlib.sha256(serialized).hexdigest()
    
    def get(self, setup_uuid: str) -> Optional[BitVMXProtocolSetupPropertiesDTO]:
        """Get DTO from cache or disk."""
        start_time = time.time()
        
        # Check cache first
        if setup_uuid in self.cache:
            print(f"[OPTIMIZED] Cache hit for {setup_uuid}")
            return self.cache[setup_uuid]
        
        # Load from disk
        filepath = self._get_filepath(setup_uuid)
        if not filepath.exists():
            return None
        
        with open(filepath, 'rb') as f:
            data = f.read()
        
        dto_dict = self._deserialize(data)
        dto = BitVMXProtocolSetupPropertiesDTO(**dto_dict)
        
        # Cache the result
        self.cache[setup_uuid] = dto
        self.checksums[setup_uuid] = self._get_checksum(dto)
        
        elapsed = time.time() - start_time
        print(f"[OPTIMIZED] Loaded {setup_uuid} in {elapsed:.3f}s")
        return dto
    
    def create(self, bitvmx_protocol_setup_properties_dto: BitVMXProtocolSetupPropertiesDTO):
        """Create/save DTO with optimization."""
        start_time = time.time()
        setup_uuid = bitvmx_protocol_setup_properties_dto.setup_uuid
        
        # Check if unchanged
        new_checksum = self._get_checksum(bitvmx_protocol_setup_properties_dto)
        if self.checksums.get(setup_uuid) == new_checksum:
            print(f"[OPTIMIZED] Skipping save for {setup_uuid} - no changes")
            return
        
        # Save to disk
        serialized = self._serialize(bitvmx_protocol_setup_properties_dto)
        filepath = self._get_filepath(setup_uuid)
        
        with open(filepath, 'wb') as f:
            f.write(serialized)
        
        # Update cache
        self.cache[setup_uuid] = bitvmx_protocol_setup_properties_dto
        self.checksums[setup_uuid] = new_checksum
        
        elapsed = time.time() - start_time
        size_kb = len(serialized) / 1024
        print(f"[OPTIMIZED] Saved {setup_uuid} ({size_kb:.1f}KB) in {elapsed:.3f}s")
    
    def clear_cache(self):
        """Clear the in-memory cache."""
        self.cache.clear()
        self.checksums.clear()
        print("[OPTIMIZED] Cache cleared")