"""
Broadcast Protocol Service
Handles broadcasting of BitVMX protocol transactions
"""
from typing import List, Dict, Any
from collections import defaultdict, deque, OrderedDict
import hashlib

def _ensure_list(x):
    """Ensure x is a list"""
    return x if (x is not None and hasattr(x, "__len__")) else []

def _fallback_read_lists(txdto):
    """Apply fallback mapping from search_* to read_search_* lists"""
    if hasattr(txdto, "read_search_hash_tx_list") and hasattr(txdto, "search_hash_tx_list"):
        if not txdto.read_search_hash_tx_list and txdto.search_hash_tx_list:
            txdto.read_search_hash_tx_list = txdto.search_hash_tx_list
            print("[BROADCAST] Fallback: read_search_hash_tx_list <- search_hash_tx_list")
    
    if hasattr(txdto, "read_search_choice_tx_list") and hasattr(txdto, "search_choice_tx_list"):
        if not txdto.read_search_choice_tx_list and txdto.search_choice_tx_list:
            txdto.read_search_choice_tx_list = txdto.search_choice_tx_list
            print("[BROADCAST] Fallback: read_search_choice_tx_list <- search_choice_tx_list")

def _get_txid(tx_hex: str) -> str:
    """Calculate txid from hex transaction"""
    try:
        raw_bytes = bytes.fromhex(tx_hex)
        hash1 = hashlib.sha256(raw_bytes).digest()
        hash2 = hashlib.sha256(hash1).digest()
        return hash2[::-1].hex()
    except:
        return None

def _get_prevouts(tx_hex: str) -> List[tuple]:
    """Extract prevout (txid, vout) pairs from transaction"""
    prevouts = []
    try:
        b = bytes.fromhex(tx_hex)
        off = 4  # Skip version
        # Check for segwit marker+flag
        if len(b) >= 6 and b[4] == 0x00 and b[5] == 0x01:
            off += 2
        if off >= len(b):
            return prevouts
        n_inputs = b[off]
        off += 1
        
        for _ in range(n_inputs):
            if off + 36 > len(b):
                break
            txid_le = b[off:off+32]
            off += 32
            vout = int.from_bytes(b[off:off+4], "little")
            off += 4
            txid = txid_le[::-1].hex()
            prevouts.append((txid, vout))
            # Skip scriptSig
            if off >= len(b):
                break
            script_len = b[off]
            off += 1 + script_len
            # Skip sequence
            off += 4
    except Exception as e:
        print(f"[BROADCAST] Error parsing prevouts: {e}")
    return prevouts

def _topological_sort(tx_hexes: List[str]) -> List[str]:
    """Sort transactions in topological order (parents before children)"""
    # Build txid map
    id_map = {}
    for hex_str in tx_hexes:
        txid = _get_txid(hex_str)
        if txid:
            id_map[txid] = hex_str
    
    # Build dependency graph
    edges = defaultdict(set)  # parent -> children
    indeg = defaultdict(int)   # incoming degree count
    
    for tx_hex in tx_hexes:
        child_txid = _get_txid(tx_hex)
        if not child_txid:
            continue
            
        prevouts = _get_prevouts(tx_hex)
        for parent_txid, _ in prevouts:
            if parent_txid in id_map:
                edges[parent_txid].add(child_txid)
                indeg[child_txid] += 1
    
    # Kahn's algorithm for topological sort
    queue = deque([txid for txid in id_map if indeg[txid] == 0])
    sorted_order = []
    
    while queue:
        u = queue.popleft()
        sorted_order.append(u)
        for v in edges[u]:
            indeg[v] -= 1
            if indeg[v] == 0:
                queue.append(v)
    
    # Return transactions in topological order
    result = []
    seen = set()
    for txid in sorted_order:
        if txid not in seen:
            result.append(id_map[txid])
            seen.add(txid)
    
    # Add any remaining transactions (cycles or disconnected)
    for tx_hex in tx_hexes:
        if tx_hex not in result:
            result.append(tx_hex)
    
    return result

def _collect_broadcast_list(txdto) -> List[Any]:
    """Collect all transactions to broadcast"""
    lst = []
    for name in (
        "read_search_hash_tx_list",
        "read_search_choice_tx_list", 
        "search_hash_tx_list",
        "search_choice_tx_list",
        "trigger_trace_challenge_tx",
    ):
        v = getattr(txdto, name, None)
        if v is None:
            continue
        if isinstance(v, list):
            lst.extend(v)
        else:
            lst.append(v)
    return lst

def broadcast_protocol_transactions(
    setup_uuid: str,
    persistence,  # bitvmx_protocol_setup_properties_dto_persistence
    broadcast_service,  # broadcast_transaction_service
) -> Dict[str, Any]:
    """
    Broadcast protocol transactions for a given setup
    - Load signed transactions from file
    - Apply fallback mappings
    - Skip funding_tx (already on-chain)
    - Broadcast remaining transactions
    """
    # Try to load signed transactions first
    from bitvmx_protocol_library.transaction_generation.services.apply_signatures_to_transactions_service import (
        ApplySignaturesToTransactionsService,
    )
    
    apply_signatures_service = ApplySignaturesToTransactionsService()
    signed_transactions = apply_signatures_service.load_signed_transactions(
        setup_uuid=setup_uuid,
        base_dir="prover_files"
    )
    
    if not signed_transactions:
        print(f"[BROADCAST] No signed transactions found for {setup_uuid}, falling back to unsigned")
        
        # Get setup DTO from persistence
        dto = persistence.get(setup_uuid=setup_uuid)
        if not dto:
            raise ValueError(f"No setup found for setup_uuid={setup_uuid}")
        
        if not hasattr(dto, "bitvmx_transactions_dto") or not dto.bitvmx_transactions_dto:
            raise ValueError(f"No transactions to broadcast for setup_uuid={setup_uuid}")
        
        txdto = dto.bitvmx_transactions_dto
        
        # Apply fallback mappings
        _fallback_read_lists(txdto)
        
        # Collect all transactions
        candidates = _collect_broadcast_list(txdto)
        
        # Convert to hex strings if needed
        tx_hexes = []
        for tx in candidates:
            if isinstance(tx, str):
                tx_hexes.append(tx)
            elif hasattr(tx, "serialize"):
                tx_hexes.append(tx.serialize())
            else:
                print(f"[BROADCAST] Warning: Cannot serialize transaction {type(tx)}")
    else:
        print(f"[BROADCAST] Using signed transactions from file")
        
        # Collect all signed transactions to broadcast
        tx_hexes = []
        
        # Process lists (search and read_search transactions)
        for key in ["read_search_hash_tx_list", "read_search_choice_tx_list",
                    "search_hash_tx_list", "search_choice_tx_list"]:
            if key in signed_transactions:
                tx_list = signed_transactions[key]
                if isinstance(tx_list, list):
                    tx_hexes.extend(tx_list)
        
        # Process single transactions
        for key in ["trigger_trace_challenge_tx"]:
            if key in signed_transactions:
                tx_hexes.append(signed_transactions[key])
    
    # Get funding_tx_id to skip
    dto = persistence.get(setup_uuid=setup_uuid)
    funding_txid_cfg = getattr(dto, "funding_tx_id", None) if dto else None
    if funding_txid_cfg:
        funding_txid_cfg = funding_txid_cfg.lower()
    
    # Sort transactions in topological order (parents before children)
    sorted_txes = _topological_sort(tx_hexes)
    print(f"[BROADCAST] Sorted {len(sorted_txes)} transactions in topological order")
    
    # Filter and broadcast
    broadcasted = []
    skipped = []
    failed = []
    
    # Skip RPC validation for Mutinynet - directly broadcast
    for tx_hex in sorted_txes:
        try:
            # Get txid from hex
            txid = _get_txid(tx_hex)
            
            # Skip funding_tx
            if txid and funding_txid_cfg and txid.lower() == funding_txid_cfg:
                print(f"[BROADCAST] Skip funding txid={txid}")
                skipped.append(txid)
                continue
            
            # Directly broadcast to Mutinynet (no local RPC validation)
            print(f"[BROADCAST] Broadcasting transaction {txid or 'unknown'} to Mutinynet...")
            broadcast_service(transaction=tx_hex)
            broadcasted.append(txid or "<unknown>")
            print(f"[BROADCAST] Success: {txid or 'unknown'}")
            
        except Exception as e:
            error_msg = str(e)
            if "min relay fee" in error_msg:
                print(f"[BROADCAST] Fee too low for {txid or 'unknown'}: {error_msg}")
            else:
                print(f"[BROADCAST] Failed for {txid or 'unknown'}: {error_msg}")
            failed.append({"txid": txid or "<unknown>", "error": error_msg})
    
    result = {
        "setup_uuid": setup_uuid,
        "broadcasted_count": len(broadcasted),
        "broadcasted_txids": broadcasted,
        "skipped_count": len(skipped),
        "skipped_txids": skipped,
        "failed_count": len(failed),
        "failed_txs": failed,
    }
    
    print(f"[BROADCAST] Summary: {len(broadcasted)} broadcasted, {len(skipped)} skipped, {len(failed)} failed")
    
    return result