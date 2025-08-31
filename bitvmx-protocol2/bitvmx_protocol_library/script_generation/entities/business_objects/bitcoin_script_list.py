from multiprocessing import Manager, Process
from multiprocessing.managers import ListProxy
from typing import List, Optional, Union

from bitcoinutils.keys import P2trAddress, PublicKey
from bitcoinutils.utils import (
    b_to_i,
    tagged_hash,
    tapbranch_tagged_hash,
    tapleaf_tagged_hash,
    tweak_taproot_pubkey,
)

from bitvmx_protocol_library.script_generation.entities.business_objects.bitcoin_script import (
    BitcoinScript,
)
from bitvmx_protocol_library.script_generation.services.split_list_for_merkle_tree_service import (
    SplitListForMerkleTreeService,
)

# Tapscript leaf version constant
LEAF_VERSION_TAPSCRIPT = 0xC0


def _get_tag_hashed_merkle_root(
    splitted_key_list: Union[List, BitcoinScript],
    depth: int,
    shared_list: Optional[ListProxy] = None,
):

    if not splitted_key_list:
        return b""
    if isinstance(splitted_key_list, BitcoinScript):
        result = tapleaf_tagged_hash(splitted_key_list)
        if shared_list:
            shared_list[0] = result
        else:
            return result
    # list
    else:
        if len(splitted_key_list) == 0:
            return b""
        elif len(splitted_key_list) == 1:
            if depth < 4:
                manager = Manager()
                new_shared_list = manager.list([None])
                process = Process(
                    target=_get_tag_hashed_merkle_root,
                    args=(
                        splitted_key_list[0],
                        depth + 1,
                        new_shared_list,
                    ),
                )
                process.start()
                process.join()
                result = new_shared_list[0]
            else:
                result = _get_tag_hashed_merkle_root(
                    splitted_key_list[0],
                    depth + 1,
                )
            if shared_list:
                shared_list[0] = result
            else:
                return result
        elif len(splitted_key_list) == 2:
            if depth < 4:
                manager = Manager()
                new_left_shared_list = manager.list([None])
                new_right_shared_list = manager.list([None])
                left_process = Process(
                    target=_get_tag_hashed_merkle_root,
                    args=(
                        splitted_key_list[0],
                        depth + 1,
                        new_left_shared_list,
                    ),
                )
                right_process = Process(
                    target=_get_tag_hashed_merkle_root,
                    args=(
                        splitted_key_list[1],
                        depth + 1,
                        new_right_shared_list,
                    ),
                )
                left_process.start()
                right_process.start()
                left_process.join()
                right_process.join()
                left_result = new_left_shared_list[0]
                right_result = new_right_shared_list[0]
                result = tapbranch_tagged_hash(left_result, right_result)
            else:
                left = _get_tag_hashed_merkle_root(
                    splitted_key_list[0],
                    depth + 1,
                )
                right = _get_tag_hashed_merkle_root(
                    splitted_key_list[1],
                    depth + 1,
                )
                result = tapbranch_tagged_hash(left, right)
            if shared_list:
                shared_list[0] = result
            else:
                return result
        else:
            # Raise an error if a branch node contains more than two elements
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


def _count_scripts_in_tree(tree: Union[List, BitcoinScript]) -> int:
    """Count the number of BitcoinScript leaves in the tree."""
    if isinstance(tree, BitcoinScript):
        return 1
    if not tree:
        return 0
    return sum(_count_scripts_in_tree(child) for child in tree)


def _traverse_for_merkle_path(
    target_index: int,
    tree: Union[List, BitcoinScript],
    already_traversed: int = 0,
    depth: int = 0,
) -> bytes:
    """
    Traverse the tree to build merkle path for target_index.
    Returns concatenated sibling hashes needed to reconstruct the root.
    """
    # If we've reached a BitcoinScript (leaf)
    if isinstance(tree, BitcoinScript):
        # At the target leaf, return empty path
        if already_traversed == target_index:
            return b""
        # Not our target
        return tapleaf_tagged_hash(tree)
    
    # Empty tree
    if not tree:
        return b""
    
    # Single element list - recurse
    if len(tree) == 1:
        return _traverse_for_merkle_path(target_index, tree[0], already_traversed, depth + 1)
    
    # Binary branch
    if len(tree) == 2:
        left_tree = tree[0]
        right_tree = tree[1]
        
        # Count scripts in left subtree
        left_count = _count_scripts_in_tree(left_tree)
        
        # Calculate hashes for both subtrees
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
            return left_path + right_hash
        elif already_traversed + left_count <= target_index:
            # Target is in right subtree
            # Get path from right subtree and append left sibling hash
            right_path = _traverse_for_merkle_path(
                target_index, right_tree, already_traversed + left_count, depth + 1
            )
            # When going right, we need the left sibling for the path
            return right_path + left_hash
        else:
            # Target index out of range - return combined hash
            return tapbranch_tagged_hash(left_hash, right_hash)
    
    raise ValueError(f"Invalid tree structure: more than 2 branches at depth {depth}")


class BitcoinScriptList:

    def __init__(self, script_list: Optional[Union[BitcoinScript, List[BitcoinScript]]] = None):
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

    def append(self, script: BitcoinScript):
        self.script_list.append(script)

    def extend(self, scripts: List[BitcoinScript]):
        for elem in scripts:
            assert isinstance(elem, BitcoinScript)
        self.script_list.extend(scripts)

    def __getitem__(self, index: int):
        return self.script_list[index]

    def __add__(self, other: Union["BitcoinScriptList", BitcoinScript]) -> "BitcoinScriptList":
        assert isinstance(other, BitcoinScriptList) or isinstance(other, BitcoinScript)
        if isinstance(other, BitcoinScript):
            script_list_copy = self.script_list.copy()
            script_list_copy.append(other)
            return BitcoinScriptList(script_list_copy)
        elif isinstance(other, BitcoinScriptList):
            return BitcoinScriptList(self.script_list + other.script_list)
        raise Exception("Type not supported")

    def __len__(self):
        return len(self.script_list)

    def to_scripts_tree(self):
        if len(self.script_list) == 1:
            return [self.script_list]
        else:
            split_list_for_merkle_tree_service = SplitListForMerkleTreeService()
            return split_list_for_merkle_tree_service(self.script_list)

    def get_taproot_address(self, public_key: PublicKey) -> P2trAddress:
        key_x = public_key.to_bytes()[:32]
        if len(self.script_list) == 0:
            tweak = tagged_hash(key_x, "TapTweak")
        else:
            merkle_root = _get_tag_hashed_merkle_root(
                self.to_scripts_tree(),
                0,
            )
            tweak = tagged_hash(key_x + merkle_root, "TapTweak")

        tweak_int = b_to_i(tweak)

        # keep x-only coordinate
        tweak_and_odd = tweak_taproot_pubkey(public_key.key.to_string(), tweak_int)
        pubkey = tweak_and_odd[0][:32]
        is_odd = tweak_and_odd[1]
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
            
            # Use the same traversal logic as BitVMXExecutionScriptList
            merkle_path = _traverse_for_merkle_path(
                target_index=index,
                tree=scripts_tree,
                already_traversed=0,
                depth=0
            )
        
        # Combine: version + internal_key + merkle_path
        control_block = leaf_version + pub_key_bytes + merkle_path
        
        # Debug logging
        print(f"[DEBUG] Control block for index {index}:")
        print(f"  - Leaf version: 0x{leaf_version.hex()}")
        print(f"  - Public key: {xonly_hex}")
        print(f"  - Merkle path length: {len(merkle_path)} bytes")
        print(f"  - Total control block length: {len(control_block)} bytes")
        
        return control_block.hex()
