from time import time
from typing import Dict, List, Optional, Union, Tuple
import hashlib
import json
from prover_app.common.hexsafe import bfromhex_safe

from bitcoinutils.constants import LEAF_VERSION_TAPSCRIPT
from bitcoinutils.keys import P2trAddress, PublicKey
from bitcoinutils.utils import (
    b_to_i,
    tagged_hash,
    tapbranch_tagged_hash,
    tapleaf_tagged_hash,
    tweak_taproot_pubkey,
)
from pydantic import BaseModel

from bitvmx_protocol_library.script_generation.services.script_generation.prover.execution_challenge_script_from_key_generator_service import (
    ExecutionChallengeScriptFromKeyGeneratorService,
)
from bitvmx_protocol_library.script_generation.services.split_list_for_merkle_tree_service import (
    SplitListForMerkleTreeService,
)


# Enhanced cache for merkle root calculations with content-based keys
_merkle_cache = {}
_cache_stats = {'hits': 0, 'misses': 0}

def _serialize_execution_tree(tree):
    """Convert execution tree to stable string for caching"""
    if isinstance(tree, str):
        return f"key:{tree}"
    elif isinstance(tree, list):
        if not tree:
            return "empty_list"
        serialized = [_serialize_execution_tree(item) for item in tree]
        return f"list:[{','.join(serialized)}]"
    else:
        return f"other:{str(tree)}"

def _get_stable_execution_cache_key(tree, sig_keys, pub_keys, trace_lengths, checksum_bits):
    """Generate stable cache key for execution scripts"""
    tree_str = _serialize_execution_tree(tree)
    # Create a simplified parameter signature
    params_str = f"sig:{len(sig_keys or [])}:pub:{len(pub_keys or [])}:trace:{str(trace_lengths)}:bits:{checksum_bits}"
    combined = f"{tree_str}:{params_str}"
    return hashlib.sha256(combined.encode('utf-8')).hexdigest()[:32]

def _get_tag_hashed_merkle_root(
    splitted_key_list: Union[List, str],
    signature_public_keys: List[str],
    public_keys: List[List[str]],
    trace_words_lengths: List[int],
    bits_per_digit_checksum: int,
    instruction_dict: Dict[str, str],
    opcode_dict: Dict[str, str],
    trace_to_script_mapping: List[int],
    depth: int,
):

    # Generate content-based cache key
    cache_key = _get_stable_execution_cache_key(
        splitted_key_list,
        signature_public_keys,
        public_keys,
        trace_words_lengths,
        bits_per_digit_checksum
    )
    
    # Check cache with statistics
    if cache_key in _merkle_cache:
        _cache_stats['hits'] += 1
        return _merkle_cache[cache_key]
    
    _cache_stats['misses'] += 1
    
    if not splitted_key_list:
        return b""
    
    execution_challenge_script_from_key_generator_service = (
        ExecutionChallengeScriptFromKeyGeneratorService()
    )
    
    if not isinstance(splitted_key_list, list):
        current_script = execution_challenge_script_from_key_generator_service(
            splitted_key_list,
            signature_public_keys,
            public_keys,
            trace_words_lengths,
            bits_per_digit_checksum,
            instruction_dict,
            opcode_dict,
            trace_to_script_mapping,
        )
        result = tapleaf_tagged_hash(current_script)
        _merkle_cache[cache_key] = result
        return result
    
    # Handle list cases
    if len(splitted_key_list) == 0:
        return b""
    elif len(splitted_key_list) == 1:
        result = _get_tag_hashed_merkle_root(
            splitted_key_list[0],
            signature_public_keys,
            public_keys,
            trace_words_lengths,
            bits_per_digit_checksum,
            instruction_dict,
            opcode_dict,
            trace_to_script_mapping,
            depth + 1
        )
        _merkle_cache[cache_key] = result
        return result
    elif len(splitted_key_list) == 2:
        # Simple recursion without parallelization
        left = _get_tag_hashed_merkle_root(
            splitted_key_list[0],
            signature_public_keys,
            public_keys,
            trace_words_lengths,
            bits_per_digit_checksum,
            instruction_dict,
            opcode_dict,
            trace_to_script_mapping,
            depth + 1
        )
        right = _get_tag_hashed_merkle_root(
            splitted_key_list[1],
            signature_public_keys,
            public_keys,
            trace_words_lengths,
            bits_per_digit_checksum,
            instruction_dict,
            opcode_dict,
            trace_to_script_mapping,
            depth + 1
        )
        result = tapbranch_tagged_hash(left, right)
        _merkle_cache[cache_key] = result
        return result
    else:
        raise ValueError("Invalid Merkle branch: List cannot have more than 2 branches.")


def _traverse_level(
    index: int,
    level: Union[List, str],
    already_traversed: int,
    depth: int,
    signature_public_keys: List[str],
    public_keys: List[List[str]],
    trace_words_lengths: List[int],
    bits_per_digit_checksum: int,
    instruction_dict: Dict[str, str],
    opcode_dict: Dict[str, str],
    trace_to_script_mapping: List[int],
):
    if isinstance(level, list):
        if len(level) == 1:
            return _traverse_level(
                index,
                level[0],
                already_traversed,
                depth,
                signature_public_keys,
                public_keys,
                trace_words_lengths,
                bits_per_digit_checksum,
                instruction_dict,
                opcode_dict,
                trace_to_script_mapping,
            )
        if len(level) == 2:
            current_low_values_per_branch = int(
                (2 ** BitVMXExecutionScriptList.get_tree_depth([level[0]])) / 2
            )
            
            # Simple recursion without parallelization
            a = _traverse_level(
                index,
                level[0],
                already_traversed,
                depth + 1,
                signature_public_keys,
                public_keys,
                trace_words_lengths,
                bits_per_digit_checksum,
                instruction_dict,
                opcode_dict,
                trace_to_script_mapping,
            )
            b = _traverse_level(
                index,
                level[1],
                already_traversed + current_low_values_per_branch,
                depth + 1,
                signature_public_keys,
                public_keys,
                trace_words_lengths,
                bits_per_digit_checksum,
                instruction_dict,
                opcode_dict,
                trace_to_script_mapping,
            )

            if (already_traversed <= index) and (
                index < already_traversed + current_low_values_per_branch
            ):
                return a + b
            if (already_traversed + current_low_values_per_branch <= index) and (
                index < (already_traversed + 2 * current_low_values_per_branch)
            ):
                return b + a
            return tapbranch_tagged_hash(a, b)
        raise ValueError("Invalid Merkle branch: List cannot have more than 2 branches.")
    else:
        if already_traversed == index:
            return b""
        execution_challenge_script_from_key_generator_service = (
            ExecutionChallengeScriptFromKeyGeneratorService()
        )
        return tapleaf_tagged_hash(
            execution_challenge_script_from_key_generator_service(
                level,
                signature_public_keys,
                public_keys,
                trace_words_lengths,
                bits_per_digit_checksum,
                instruction_dict,
                opcode_dict,
                trace_to_script_mapping,
            )
        )


# 클래스 레벨 캐시 (모든 인스턴스가 공유)
_global_control_block_cache: Dict[Tuple[str, int, bool, str], str] = {}
_global_merkle_path_cache: Dict[Tuple[str, int], bytes] = {}

class BitVMXExecutionScriptList(BaseModel):

    key_list: List[str]
    instruction_dict: Dict[str, str]
    opcode_dict: Dict[str, str]
    signature_public_keys: List[str]
    public_keys: List[List[str]]
    trace_words_lengths: List[int]
    bits_per_digit_checksum: int
    taproot_address_pubkey: Optional[str] = None
    taproot_address_is_odd: Optional[bool] = None
    _tree_key: Optional[str] = None  # Pre-computed tree key for consistency
    
    class Config:
        # Pydantic이 private field를 무시하도록 설정
        underscore_attrs_are_private = True

    def set_fixed_tree_keys(self, tree_key: str):
        """Set pre-computed tree key to ensure consistency across regenerations"""
        self._tree_key = tree_key
        print(f"[EXEC_TREE_KEY] Set fixed tree_key: {tree_key[:16]}...")

    @staticmethod
    def get_tree_depth(splitted_key_list: Union[List, str]):
        depth = 1
        current_list = splitted_key_list
        while isinstance(current_list[0], list):
            depth += 1
            current_list = current_list[0]
        return depth

    @staticmethod
    def trace_to_script_mapping():
        return [9, 10, 11, 12, 0, 1, 3, 4, 6, 7, 8]
        # return [9, 10, 11, 12, 3, 4, 0, 1, 6, 7, 8]

    def get_taproot_address(self, public_key: PublicKey):
        if (self.taproot_address_pubkey is not None) and (self.taproot_address_is_odd is not None):
            return P2trAddress(
                witness_program=self.taproot_address_pubkey, is_odd=self.taproot_address_is_odd
            )
        key_x = public_key.to_bytes()[:32]
        if len(self.key_list) == 0:
            tweak = tagged_hash(key_x, "TapTweak")
        else:
            split_list_for_merkle_tree_service = SplitListForMerkleTreeService()
            split_key_list = split_list_for_merkle_tree_service(self.key_list)
            print("Call parallel hashed merkle root")
            init_time = time()
            merkle_root = _get_tag_hashed_merkle_root(
                split_key_list,
                self.signature_public_keys,
                self.public_keys,
                self.trace_words_lengths,
                self.bits_per_digit_checksum,
                self.instruction_dict,
                self.opcode_dict,
                self.trace_to_script_mapping(),
                0
            )
            end_time = time()
            elapsed = end_time - init_time
            if elapsed > 60:
                print(f"End of parallel hashed merkle root in {elapsed / 60:.2f} minutes.")
            else:
                print(f"End of parallel hashed merkle root in {elapsed:.2f} seconds.")
            
            # Print cache statistics
            if _cache_stats['hits'] + _cache_stats['misses'] > 0:
                hit_rate = _cache_stats['hits'] / (_cache_stats['hits'] + _cache_stats['misses']) * 100
                print(f"[CACHE STATS] Hits: {_cache_stats['hits']}, Misses: {_cache_stats['misses']}, Hit Rate: {hit_rate:.1f}%")
            tweak = tagged_hash(key_x + merkle_root, "TapTweak")

        tweak_int = b_to_i(tweak)

        # keep x-only coordinate
        tweak_and_odd = tweak_taproot_pubkey(public_key.key.to_string(), tweak_int)
        pubkey = tweak_and_odd[0][:32]
        is_odd = tweak_and_odd[1]
        self.taproot_address_pubkey = pubkey.hex()
        self.taproot_address_is_odd = is_odd
        return P2trAddress(witness_program=pubkey.hex(), is_odd=is_odd)

    def get_control_block_hex(self, public_key: PublicKey, index: int, is_odd: bool) -> str:
        global _global_control_block_cache, _global_merkle_path_cache
        
        # 캐시 키 생성 (인스턴스 고유 식별자 포함)
        xonly_hex = public_key.to_x_only_hex()
        if isinstance(xonly_hex, bytes):
            xonly_hex = xonly_hex.hex()
        
        # key_list의 첫 번째 요소를 인스턴스 식별자로 사용
        instance_id = self.key_list[0] if self.key_list else ""
        cache_key = (xonly_hex, index, is_odd, instance_id)
        
        # 캐시 확인
        if cache_key in _global_control_block_cache:
            print(f"[CACHE HIT] Control block for index {index} retrieved from cache")
            return _global_control_block_cache[cache_key]
        
        print(f"[CACHE MISS] Computing control block for index {index}")
        
        leaf_version = bytes([(1 if is_odd else 0) + LEAF_VERSION_TAPSCRIPT])
        pub_key = bfromhex_safe(xonly_hex)

        # merkle_path 캐싱 확인
        merkle_cache_key = (instance_id, index)
        if merkle_cache_key in _global_merkle_path_cache:
            print(f"[CACHE HIT] Merkle path for index {index} retrieved from cache")
            merkle_path = _global_merkle_path_cache[merkle_cache_key]
        else:
            init_time = time()
            split_list_for_merkle_tree_service = SplitListForMerkleTreeService()
            print("Start control block computation")
            merkle_path = _traverse_level(
                index,
                split_list_for_merkle_tree_service(self.key_list),
                0,
                0,
                self.signature_public_keys,
                self.public_keys,
                self.trace_words_lengths,
                self.bits_per_digit_checksum,
                self.instruction_dict,
                self.opcode_dict,
                self.trace_to_script_mapping(),
            )
            print("End of control block computation in " + str(time() - init_time) + " seconds.")
            # merkle_path 캐시 저장
            _global_merkle_path_cache[merkle_cache_key] = merkle_path

        control_block_bytes = leaf_version + pub_key + merkle_path
        control_block_hex = control_block_bytes.hex()
        
        # 캐시에 저장
        _global_control_block_cache[cache_key] = control_block_hex
        print(f"[CACHE] Stored control block for index {index} in cache")
        print(f"[CACHE STATS] Control blocks: {len(_global_control_block_cache)}, Merkle paths: {len(_global_merkle_path_cache)}")
        
        return control_block_hex

    def __getitem__(self, index: int):
        # Create a content-based cache key
        cache_key = (
            tuple(self.key_list),
            tuple(self.signature_public_keys),
            tuple(tuple(pk) for pk in self.public_keys),
            tuple(self.trace_words_lengths),
            self.bits_per_digit_checksum,
            index
        )
        cache_key_str = f"script_{hash(cache_key)}"
        
        # Check global script cache
        if not hasattr(self, '_script_cache'):
            self._script_cache = {}
        
        if cache_key_str in self._script_cache:
            print(f"[SCRIPT CACHE HIT] Script for index {index} retrieved from cache")
            return self._script_cache[cache_key_str]
        
        print(f"[SCRIPT CACHE MISS] Generating script for index {index}")
        
        # Generate script
        execution_challenge_script_from_key_generator_service = (
            ExecutionChallengeScriptFromKeyGeneratorService()
        )
        script = execution_challenge_script_from_key_generator_service(
            self.key_list[index],
            self.signature_public_keys,
            self.public_keys,
            self.trace_words_lengths,
            self.bits_per_digit_checksum,
            self.instruction_dict,
            self.opcode_dict,
            self.trace_to_script_mapping(),
        )
        
        # Cache the result
        self._script_cache[cache_key_str] = script
        print(f"[SCRIPT CACHE STORED] Script for index {index} cached")
        
        return script
