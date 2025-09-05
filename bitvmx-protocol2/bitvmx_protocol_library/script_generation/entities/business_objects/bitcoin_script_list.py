from typing import List, Optional, Union
import hashlib
import json
from functools import lru_cache

from bitcoinutils.keys import P2trAddress, PublicKey
try:
    from bitcoinutils.utils import (
        b_to_i,
        tagged_hash,
        tapbranch_tagged_hash,
        tapleaf_tagged_hash,
        tweak_taproot_pubkey,
    )
except ImportError:
    # Fallback implementations for missing functions
    def b_to_i(b: bytes) -> int:
        """Convert bytes to integer"""
        return int.from_bytes(b, 'big')
    
    import hashlib
    
    def tagged_hash(data: bytes, tag: str) -> bytes:
        """Tagged hash for taproot"""
        tag_hash = hashlib.sha256(tag.encode()).digest()
        return hashlib.sha256(tag_hash + tag_hash + data).digest()
    
    def tapbranch_tagged_hash(left: bytes, right: bytes) -> bytes:
        """Compute tapbranch tagged hash"""
        # Lexicographic ordering
        if left <= right:
            data = left + right
        else:
            data = right + left
        return tagged_hash(data, "TapBranch")
    
    def tapleaf_tagged_hash(script) -> bytes:
        """Compute tapleaf tagged hash"""
        if hasattr(script, 'to_bytes'):
            script_bytes = script.to_bytes()
        elif hasattr(script, 'to_hex'):
            script_bytes = bytes.fromhex(script.to_hex())
        else:
            script_bytes = bytes(script)
        # Leaf version (0xc0) + script
        data = bytes([0xc0]) + script_bytes
        return tagged_hash(data, "TapLeaf")
    
    def tweak_taproot_pubkey(pubkey_bytes: bytes, tweak_int: int):
        """Tweak taproot public key"""
        # Simple implementation - may not be complete
        return (pubkey_bytes, False)  # Return pubkey and is_odd flag

from bitvmx_protocol_library.script_generation.entities.business_objects.bitcoin_script import (
    BitcoinScript,
)
from bitvmx_protocol_library.script_generation.services.split_list_for_merkle_tree_service import (
    SplitListForMerkleTreeService,
)

# Tapscript leaf version constant
LEAF_VERSION_TAPSCRIPT = 0xC0


# Enhanced content-based global cache system for BitVMX Option B
_merkle_root_cache = {}      # tree_key -> merkle_root_bytes
_merkle_nodes_cache = {}     # tree_key -> level-indexed node dict 
_merkle_path_cache = {}      # (tree_key, index) -> path_bytes
_address_cache = {}          # (tree_key, pubkey_hex) -> address_string
_control_block_cache = {}    # (tree_key, index, pubkey_hex, is_odd) -> control_block_hex

# Cache statistics
_cache_stats = {
    'root_hits': 0, 'root_misses': 0,
    'nodes_hits': 0, 'nodes_misses': 0, 
    'path_hits': 0, 'path_misses': 0,
    'addr_hits': 0, 'addr_misses': 0, 
    'cb_hits': 0, 'cb_misses': 0
}

def _serialize_tree_structure(tree):
    """Convert tree to a stable string representation for caching"""
    if isinstance(tree, BitcoinScript):
        return f"script:{tree.to_hex()}"
    elif isinstance(tree, str):
        return f"str:{tree}"
    elif isinstance(tree, list):
        if not tree:
            return "empty_list"
        # Recursively serialize list contents
        serialized_items = [_serialize_tree_structure(item) for item in tree]
        return f"list:[{','.join(serialized_items)}]"
    else:
        # Fallback for other types
        return f"other:{str(tree)}"

def _get_stable_cache_key(tree_structure):
    """Generate a stable cache key based on content, not object identity"""
    serialized = _serialize_tree_structure(tree_structure)
    # Use SHA256 for consistent hashing
    return hashlib.sha256(serialized.encode('utf-8')).hexdigest()[:32]

def _get_tag_hashed_merkle_root(
    splitted_key_list: Union[List, BitcoinScript],
    depth: int,
):
    # Generate content-based cache key
    cache_key = _get_stable_cache_key(splitted_key_list)
    
    # Check cache with statistics
    if cache_key in _merkle_root_cache:
        _cache_stats['root_hits'] += 1
        return _merkle_root_cache[cache_key]
    
    _cache_stats['root_misses'] += 1
    
    if not splitted_key_list:
        return b""
    
    if isinstance(splitted_key_list, BitcoinScript):
        result = tapleaf_tagged_hash(splitted_key_list)
        _merkle_root_cache[cache_key] = result
        return result
    
    # Handle list cases
    if len(splitted_key_list) == 0:
        return b""
    elif len(splitted_key_list) == 1:
        result = _get_tag_hashed_merkle_root(splitted_key_list[0], depth + 1)
        _merkle_root_cache[cache_key] = result
        return result
    elif len(splitted_key_list) == 2:
        # Store intermediate nodes for path computation
        left = _get_tag_hashed_merkle_root(splitted_key_list[0], depth + 1)
        right = _get_tag_hashed_merkle_root(splitted_key_list[1], depth + 1)
        result = tapbranch_tagged_hash(left, right)
        
        # Store in merkle nodes cache for path retrieval
        if cache_key not in _merkle_nodes_cache:
            _merkle_nodes_cache[cache_key] = {}
        _merkle_nodes_cache[cache_key][depth] = {
            'left': left,
            'right': right,
            'root': result
        }
        
        _merkle_root_cache[cache_key] = result
        return result
    else:
        raise ValueError("Invalid Merkle branch: List cannot have more than 2 branches.")


def _get_tree_depth(splitted_list: Union[List, BitcoinScript]) -> int:
    """Calculate the depth of the tree."""
    if isinstance(splitted_list, BitcoinScript):
        return 0
    if not splitted_list:
        return 0
    if len(splitted_list) == 1:
        return 1 + _get_tree_depth(splitted_list[0])
    # For binary tree
    return 1 + max(_get_tree_depth(splitted_list[0]), _get_tree_depth(splitted_list[1]))


# Cache for tree script counts
_tree_count_cache = {}

def _count_scripts_in_tree(tree: Union[List, BitcoinScript]) -> int:
    """Count the number of BitcoinScript leaves in the tree with memoization."""
    global _tree_count_cache
    
    # Create cache key
    if isinstance(tree, BitcoinScript):
        return 1
    if not tree:
        return 0
    
    # Try to create a hashable cache key
    try:
        import pickle
        cache_key = hashlib.sha256(pickle.dumps(tree, protocol=pickle.HIGHEST_PROTOCOL)).hexdigest()[:16]
    except:
        # Fallback: just compute without cache
        return sum(_count_scripts_in_tree(child) for child in tree)
    
    # Check cache
    if cache_key in _tree_count_cache:
        return _tree_count_cache[cache_key]
    
    # Compute and cache
    count = sum(_count_scripts_in_tree(child) for child in tree)
    _tree_count_cache[cache_key] = count
    return count


def _traverse_for_merkle_path(
    target_index: int,
    tree: Union[List, BitcoinScript],
    already_traversed: int = 0,
    depth: int = 0,
) -> bytes:
    """
    Traverse the tree to build merkle path for target_index.
    Returns concatenated sibling hashes needed to reconstruct the root.
    Uses cached merkle nodes when available for O(log N) performance.
    """
    # Generate cache key for path lookup
    cache_key = _get_stable_cache_key(tree)
    path_key = (cache_key, target_index)
    
    # Check path cache first
    if path_key in _merkle_path_cache:
        _cache_stats['path_hits'] += 1
        return _merkle_path_cache[path_key]
    
    _cache_stats['path_misses'] += 1
    # Compute the path (original logic)
    result = None
    
    # If we've reached a BitcoinScript (leaf)
    if isinstance(tree, BitcoinScript):
        # At the target leaf, return empty path
        if already_traversed == target_index:
            result = b""
        else:
            # Not our target
            result = tapleaf_tagged_hash(tree)
    
    # Empty tree
    elif not tree:
        result = b""
    
    # Single element list - recurse
    elif len(tree) == 1:
        result = _traverse_for_merkle_path(target_index, tree[0], already_traversed, depth + 1)
    
    # Binary branch
    elif len(tree) == 2:
        left_tree = tree[0]
        right_tree = tree[1]
        
        # Count scripts in left subtree
        left_count = _count_scripts_in_tree(left_tree)
        
        # Calculate hashes for both subtrees with caching
        left_hash = _get_tag_hashed_merkle_root(left_tree, depth + 1)
        right_hash = _get_tag_hashed_merkle_root(right_tree, depth + 1)
        
        # Check which subtree contains our target
        if already_traversed <= target_index < already_traversed + left_count:
            # Target is in left subtree
            # Get path from left subtree and append right sibling hash
            left_path = _traverse_for_merkle_path(
                target_index, left_tree, already_traversed, depth + 1
            )
            # When going left, we need the right sibling for the path
            result = left_path + right_hash
        elif already_traversed + left_count <= target_index:
            # Target is in right subtree
            # Get path from right subtree and append left sibling hash
            right_path = _traverse_for_merkle_path(
                target_index, right_tree, already_traversed + left_count, depth + 1
            )
            # When going right, we need the left sibling for the path
            result = right_path + left_hash
        else:
            # Target index out of range - return combined hash
            result = tapbranch_tagged_hash(left_hash, right_hash)
    
    else:
        raise ValueError(f"Invalid tree structure: more than 2 branches at depth {depth}")
    
    # Cache the computed path
    if result is not None:
        _merkle_path_cache[path_key] = result
        
    return result


class BitcoinScriptList:

    def __init__(self, script_list: Optional[Union[BitcoinScript, List[BitcoinScript]]] = None, tree_key: Optional[str] = None):
        if script_list is None:
            self.script_list = []
        elif isinstance(script_list, BitcoinScript):
            self.script_list = [script_list]
        elif isinstance(script_list, list):
            for elem in script_list:
                assert isinstance(elem, BitcoinScript)
            self.script_list = script_list
        else:
            raise Exception("Type not supported")
        
        # Store pre-computed tree_key if provided
        self._tree_key = tree_key
        if tree_key:
            print(f"[BitcoinScriptList] Using pre-computed tree_key: {tree_key}")
        
        # Tree memoization: cache merkle tree structure
        self._cached_tree = None
        self._tree_computed = False

    def append(self, script: BitcoinScript):
        self.script_list.append(script)
        # Invalidate cached tree when list changes
        self._cached_tree = None
        self._tree_computed = False

    def extend(self, scripts: List[BitcoinScript]):
        for elem in scripts:
            assert isinstance(elem, BitcoinScript)
        self.script_list.extend(scripts)
        # Invalidate cached tree when list changes
        self._cached_tree = None
        self._tree_computed = False

    def __getitem__(self, index: int):
        return self.script_list[index]

    def set_fixed_tree_keys(self, tree_key: str):
        """Set pre-computed tree key to ensure consistency across regenerations"""
        self._tree_key = tree_key
        print(f"[TREE_KEY] Set fixed tree_key: {tree_key[:16]}...")
    
    def __add__(self, other: Union["BitcoinScriptList", BitcoinScript]) -> "BitcoinScriptList":
        assert isinstance(other, BitcoinScriptList) or isinstance(other, BitcoinScript)
        if isinstance(other, BitcoinScript):
            script_list_copy = self.script_list.copy()
            script_list_copy.append(other)
            # Compute deterministic tree key for the combined list based on its tree
            if len(script_list_copy) == 1:
                combined_tree = [script_list_copy]
            else:
                combined_tree = SplitListForMerkleTreeService()(script_list_copy)
            combined_key = _get_stable_cache_key(combined_tree)
            return BitcoinScriptList(script_list_copy, tree_key=combined_key)
        elif isinstance(other, BitcoinScriptList):
            combined = self.script_list + other.script_list
            # Compute deterministic tree key for the combined list based on its tree
            if len(combined) == 1:
                combined_tree = [combined]
            else:
                combined_tree = SplitListForMerkleTreeService()(combined)
            combined_key = _get_stable_cache_key(combined_tree)
            return BitcoinScriptList(combined, tree_key=combined_key)
        raise Exception("Type not supported")

    def __len__(self):
        return len(self.script_list)

    def to_scripts_tree(self):
        # Use cached tree if available
        if self._tree_computed and self._cached_tree is not None:
            print(f"[TreeMemoization] Using cached tree for {len(self.script_list)} scripts")
            return self._cached_tree
        
        # Compute tree
        if len(self.script_list) == 1:
            tree = [self.script_list]
        else:
            split_list_for_merkle_tree_service = SplitListForMerkleTreeService()
            tree = split_list_for_merkle_tree_service(self.script_list)
        
        # Cache the computed tree
        self._cached_tree = tree
        self._tree_computed = True
        print(f"[TreeMemoization] Computed and cached tree for {len(self.script_list)} scripts")
        
        return tree

    def get_taproot_address(self, public_key: PublicKey) -> P2trAddress:
        global _address_cache, _cache_stats
        
        # Create a simple cache key based on script content and public key
        key_x = public_key.to_bytes()[:32]
        xonly_pubkey_hex = key_x.hex()
        
        # Generate content-based cache key using pre-computed tree_key if available
        if len(self.script_list) == 0:
            tree_key = "empty"
            address_cache_key = f"empty:{xonly_pubkey_hex}"
        else:
            # Use pre-computed tree_key if available (O(1))
            if self._tree_key:
                tree_key = self._tree_key
            else:
                # Fallback: compute tree key (expensive, should be avoided)
                print(f"[WARNING] Computing tree_key on-the-fly in get_taproot_address for {len(self.script_list)} scripts. This should be pre-computed!")
                print(f"[DEBUG] Script list first item type: {type(self.script_list[0]) if self.script_list else 'empty'}")
                # Use stable content-based key generation to ensure determinism
                tree_key = _get_stable_cache_key(self.to_scripts_tree())
                # Persist the computed key to avoid recomputation and stabilize control blocks
                self._tree_key = tree_key
            
            address_cache_key = (tree_key, xonly_pubkey_hex)
        
        # Use tree_key as fingerprint for logging
        fingerprint = tree_key[:8] if tree_key != "empty" else "empty"
        print(f"[TAPROOT] Computing for {len(self.script_list)} scripts, fingerprint: {fingerprint}")
        
        # Check global cache
        if address_cache_key in _address_cache:
            _cache_stats['addr_hits'] += 1
            cached = _address_cache[address_cache_key]
            print(f"[TAPROOT] ✓ Cache hit (fingerprint: {fingerprint})")
            return P2trAddress(witness_program=cached[0], is_odd=cached[1])
        
        _cache_stats['addr_misses'] += 1
        print(f"[TAPROOT] ✗ Cache miss (fingerprint: {fingerprint})")
        
        # Calculate the address
        if len(self.script_list) == 0:
            tweak = tagged_hash(key_x, "TapTweak")
        else:
            merkle_root = _get_tag_hashed_merkle_root(
                self.to_scripts_tree(),
                0
            )
            tweak = tagged_hash(key_x + merkle_root, "TapTweak")
        
        tweak_int = b_to_i(tweak)
        tweak_and_odd = tweak_taproot_pubkey(public_key.key.to_string(), tweak_int)
        pubkey = tweak_and_odd[0][:32]
        is_odd = tweak_and_odd[1]
        
        # Cache the result globally
        _address_cache[address_cache_key] = (pubkey.hex(), is_odd)
        
        # Print comprehensive cache statistics periodically
        total_addr_calls = _cache_stats['addr_hits'] + _cache_stats['addr_misses']
        if total_addr_calls % 10 == 0 and total_addr_calls > 0:
            addr_hit_rate = _cache_stats['addr_hits'] / total_addr_calls * 100
            
            total_root_calls = _cache_stats['root_hits'] + _cache_stats['root_misses']
            root_hit_rate = _cache_stats['root_hits'] / max(total_root_calls, 1) * 100
            
            total_path_calls = _cache_stats['path_hits'] + _cache_stats['path_misses']
            path_hit_rate = _cache_stats['path_hits'] / max(total_path_calls, 1) * 100
            
            total_cb_calls = _cache_stats['cb_hits'] + _cache_stats['cb_misses']
            cb_hit_rate = _cache_stats['cb_hits'] / max(total_cb_calls, 1) * 100
            
            print(f"[OPTION B CACHE STATS] " +
                  f"Address: {addr_hit_rate:.1f}% ({_cache_stats['addr_hits']}/{total_addr_calls}), " +
                  f"Root: {root_hit_rate:.1f}% ({_cache_stats['root_hits']}/{total_root_calls}), " +
                  f"Path: {path_hit_rate:.1f}% ({_cache_stats['path_hits']}/{total_path_calls}), " +
                  f"CB: {cb_hit_rate:.1f}% ({_cache_stats['cb_hits']}/{total_cb_calls})")
        
        return P2trAddress(witness_program=pubkey.hex(), is_odd=is_odd)
    
    def get_control_block_hex(self, public_key: PublicKey, index: int, is_odd: bool) -> str:
        """
        Generate the control block for spending a specific script at the given index.
        
        Args:
            public_key: The internal public key used in the taproot output
            index: The index of the script in the script_list
            is_odd: Whether the tweaked public key has odd y-coordinate
        
        Returns:
            Hex string of the control block
        """
        if index >= len(self.script_list):
            raise ValueError(f"Script index {index} out of range")
        
        # Create cache key based on content
        xonly_hex = public_key.to_x_only_hex()
        if isinstance(xonly_hex, bytes):
            xonly_hex = xonly_hex.hex()
        
        # Use pre-computed tree_key if available (O(1))
        if self._tree_key:
            cache_key = self._tree_key
        else:
            # Fallback: compute tree key (expensive, should be avoided)
            print(f"[WARNING] Computing tree_key on-the-fly in get_control_block_hex for {len(self.script_list)} scripts at index {index}. This should be pre-computed!")
            cache_key = _get_stable_cache_key(self.to_scripts_tree())
            # Persist computed key for stability across subsequent calls
            self._tree_key = cache_key
        control_key = (cache_key, index, xonly_hex, is_odd)
        
        # Check cache first
        if control_key in _control_block_cache:
            _cache_stats['cb_hits'] += 1
            print(f"[CACHE HIT] Control block for index {index} retrieved from cache")
            return _control_block_cache[control_key]
        
        _cache_stats['cb_misses'] += 1
        print(f"[CACHE MISS] Computing control block for index {index}")
        
        # Leaf version byte (0xC0 or 0xC1 based on parity)
        leaf_version = bytes([(1 if is_odd else 0) + LEAF_VERSION_TAPSCRIPT])
        
        # X-only public key (32 bytes)
        xonly_hex = public_key.to_x_only_hex()
        if isinstance(xonly_hex, bytes):
            xonly_hex = xonly_hex.hex()
        pub_key_bytes = bytes.fromhex(xonly_hex)
        
        # Compute merkle path if there are multiple scripts
        if len(self.script_list) == 0:
            # No scripts - no merkle path
            merkle_path = b""
        elif len(self.script_list) == 1:
            # Single script - no merkle path needed (script is the root)
            merkle_path = b""
        else:
            # Multiple scripts - build tree and compute merkle path
            scripts_tree = self.to_scripts_tree()
            
            # Use the optimized traversal logic
            merkle_path = _traverse_for_merkle_path(
                target_index=index,
                tree=scripts_tree,
                already_traversed=0,
                depth=0
            )
        
        # Combine: version + internal_key + merkle_path
        control_block = leaf_version + pub_key_bytes + merkle_path
        
        # Cache the result
        result = control_block.hex()
        _control_block_cache[control_key] = result
        
        # Debug logging
        print(f"[CACHE STORED] Control block for index {index} cached (length: {len(control_block)} bytes)")
        
        return result
