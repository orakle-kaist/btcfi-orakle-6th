"""
Broadcast Protocol Service
Handles broadcasting of BitVMX protocol transactions
"""
from typing import List, Dict, Any
from collections import defaultdict, deque, OrderedDict
import hashlib
import time
import requests
from prover_app.common.hexsafe import ensure_hex_str, bfromhex_safe, hex_from_any

# Import bitcoin signing utilities at module level
try:
    from bitcoin.core import CMutableTransaction, CTxWitness, CTxInWitness, Hash160
    from bitcoin.core.script import CScript, OP_DUP, OP_HASH160, OP_EQUALVERIFY, OP_CHECKSIG, OP_1, SIGHASH_ALL, SignatureHash, SIGVERSION_WITNESS_V0
    from bitcoin.wallet import CBitcoinSecret
    import bitcoin
    BITCOIN_LIB_AVAILABLE = True
except ImportError:
    BITCOIN_LIB_AVAILABLE = False

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
        tx_bytes = bfromhex_safe(tx_hex)
        if not tx_bytes:
            return None
        hash1 = hashlib.sha256(tx_bytes).digest()
        hash2 = hashlib.sha256(hash1).digest()
        return hash2[::-1].hex()
    except:
        return None

def _get_prevouts(tx_hex: str) -> List[tuple]:
    """Extract prevout (txid, vout) pairs from transaction"""
    prevouts = []
    try:
        b = bfromhex_safe(tx_hex)
        if not b:
            return prevouts
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

def _wait_for_mempool_propagation(txid: str, network: str = "mutinynet", max_wait: int = 30) -> bool:
    """Wait for transaction to appear in mempool"""
    if network == "mutinynet":
        api_url = f"https://mutinynet.com/api/tx/{txid}"
    elif network == "testnet":
        api_url = f"https://mempool.space/testnet/api/tx/{txid}"
    else:
        api_url = f"https://mempool.space/api/tx/{txid}"
    
    for i in range(max_wait):
        try:
            response = requests.get(api_url, timeout=5)
            if response.status_code == 200:
                print(f"[BROADCAST] Transaction {txid[:8]}... found in mempool")
                return True
            print(f"[BROADCAST] Waiting for mempool... ({i+1}/{max_wait})")
        except Exception:
            pass
        time.sleep(1)
    
    return False

def broadcast_protocol_transactions(
    setup_uuid: str,
    persistence,  # bitvmx_protocol_setup_properties_dto_persistence
    broadcast_service,  # broadcast_transaction_service
    force_resign: bool = False,  # Add as parameter
) -> Dict[str, Any]:
    """
    Broadcast protocol transactions for a given setup
    - Load signed transactions from file
    - Apply fallback mappings
    - Skip funding_tx (already on-chain)
    - Broadcast remaining transactions
    """
    import os
    
    # Check if we should force regeneration - parameter takes precedence over env
    if not force_resign:
        force_resign = os.environ.get("BITVMX_FORCE_RESIGN") == "1"
    
    # Try to load signed transactions first
    from bitvmx_protocol_library.transaction_generation.services.apply_signatures_to_transactions_service import (
        ApplySignaturesToTransactionsService,
    )
    
    apply_signatures_service = ApplySignaturesToTransactionsService()
    
    # Initialize tx_hexes list for collecting transactions
    tx_hexes = []
    
    # Get DTO first to check prevout consistency
    dto = persistence.get(setup_uuid=setup_uuid)
    if not dto:
        raise ValueError(f"No setup found for setup_uuid={setup_uuid}")
    
    # Check if cached transactions have correct prevout
    needs_resign = force_resign
    
    # Get chain prevout info for validation
    from blockchain_query_services.services.mutinynet_api.transaction_info_service import TransactionInfoService
    
    expected_funding_txid = dto.funding_tx_id.lower()
    expected_funding_index = dto.funding_index
    expected_script = None
    expected_amount = None
    
    # Query chain for actual prevout details
    try:
        tx_info_service = TransactionInfoService()
        funding_tx_info = tx_info_service(tx_id=expected_funding_txid)
        if expected_funding_index < len(funding_tx_info.outputs):
            funding_output = funding_tx_info.outputs[expected_funding_index]
            expected_script = funding_output.scriptpubkey_hex
            expected_amount = funding_output.value
            print(f"[BROADCAST] Expected prevout: {expected_funding_txid}:{expected_funding_index}")
            print(f"[BROADCAST] Chain prevout script: {expected_script}, amount: {expected_amount}")
    except Exception as e:
        print(f"[BROADCAST] Failed to query chain prevout: {e}")
    
    if not needs_resign:
        # Load cached transactions to check prevout
        signed_transactions = apply_signatures_service.load_signed_transactions(
            setup_uuid=setup_uuid,
            base_dir="prover_files"
        )
        
        if signed_transactions:
            # Check cache info for prevout validation
            cache_info = signed_transactions.get('cache_info', {})
            cached_txid = cache_info.get('funding_tx_id', '').lower()
            cached_index = cache_info.get('funding_index', -1)
            cached_script = cache_info.get('prevout_script', '')
            cached_amount = cache_info.get('prevout_amount', -1)
            
            # Validate cache against current expectations
            if (cached_txid != expected_funding_txid or 
                cached_index != expected_funding_index or
                (expected_script and cached_script != expected_script) or
                (expected_amount and cached_amount != expected_amount)):
                print(f"[BROADCAST] Cache mismatch detected!")
                print(f"[BROADCAST] Expected: txid={expected_funding_txid}, index={expected_funding_index}")
                print(f"[BROADCAST] Cached:   txid={cached_txid}, index={cached_index}")
                print(f"[BROADCAST] DETAILS: Script mismatch: {cached_script != expected_script}")
                print(f"  - Expected Script: {expected_script}")
                print(f"  - Cached Script:   {cached_script}")
                print(f"[BROADCAST] DETAILS: Amount mismatch: {cached_amount != expected_amount}")
                print(f"  - Expected Amount: {expected_amount}")
                print(f"  - Cached Amount:   {cached_amount}")
                print(f"[BROADCAST] Forcing re-sign due to prevout change")
                needs_resign = True
                signed_transactions = None
            else:
                print(f"[BROADCAST] Cache prevout matches expected")
    else:
        print(f"[BROADCAST] Force resign enabled, skipping cached transactions")
        signed_transactions = None
        # Clear the flag after use
        os.environ.pop("BITVMX_FORCE_RESIGN", None)
    
    if not signed_transactions or needs_resign:
        if needs_resign:
            print(f"[BROADCAST] Regenerating signatures due to prevout change or force flag")
        else:
            print(f"[BROADCAST] No signed transactions found for {setup_uuid}, regenerating signatures")
        
        if not hasattr(dto, "bitvmx_transactions_dto") or not dto.bitvmx_transactions_dto:
            raise ValueError(f"No transactions to broadcast for setup_uuid={setup_uuid}")
        
        # Regenerate signatures
        print(f"[BROADCAST] Regenerating signatures for setup {setup_uuid}")
        from bitvmx_protocol_library.transaction_generation.services.generate_signatures_service import (
            GenerateSignaturesService
        )
        
        # Load prover private key for hash_result_tx signing
        import json
        import os
        
        # Try to get the prover's private key for funding UTXO
        prover_private_key_hex = None
        
        # Try to get from the setup DTO first
        if hasattr(dto, 'secret_origin_of_funds'):
            prover_private_key_hex = dto.secret_origin_of_funds
            print(f"[BROADCAST] Found secret_origin_of_funds in setup DTO")
        
        # Try to load from prover_private_dto.json
        if not prover_private_key_hex:
            prover_private_key_path = f"prover_files/{setup_uuid}/bitvmx_protocol_prover_private_dto.json"
            if os.path.exists(prover_private_key_path):
                with open(prover_private_key_path, 'r') as f:
                    prover_private_dto = json.load(f)
                    prover_private_key_hex = prover_private_dto.get('prover_signature_private_key')
                    if prover_private_key_hex:
                        print(f"[BROADCAST] Found prover_signature_private_key in prover_private_dto.json")
        
        # Fallback to hardcoded key from .env_prover
        if not prover_private_key_hex:
            # This should match the PROVER_PRIVATE_KEY in .env_prover
            prover_private_key_hex = "d8a1e1224e63135765bde9dc8a2c8e403eee8be73d3589d58c5ddbf9dce3fdf4"
            if prover_private_key_hex:
                print(f"[BROADCAST] Using hardcoded PROVER_PRIVATE_KEY for funding")
        
        # Also load verifier private key for other signatures
        verifier_private_key = None
        verifier_key_path = f"prover_files/{setup_uuid}/bitvmx_protocol_verifier_private_dto.json"
        if os.path.exists(verifier_key_path):
            with open(verifier_key_path, 'r') as f:
                verifier_dto = json.load(f)
                verifier_private_key = verifier_dto.get('prover_signature_private_key')
                
        # Use prover private key as the main signing key
        signing_private_key = prover_private_key_hex if prover_private_key_hex else verifier_private_key
        
        if signing_private_key:
            print(f"[BROADCAST] Using private key for signature generation")
            
            # Convert private key string to PrivateKey object
            from bitcoinutils.keys import PrivateKey
            privkey_obj = PrivateKey(b=bfromhex_safe(signing_private_key))
            
            # Get destroyed public key from setup
            destroyed_public_key = dto.unspendable_public_key if hasattr(dto, 'unspendable_public_key') else dto.destroyed_public_key
            
            print(f"[BROADCAST] Generating signatures with GenerateSignaturesService...")
            generate_signatures_service = GenerateSignaturesService(
                privkey_obj, 
                destroyed_public_key
            )
            signatures = generate_signatures_service(
                bitvmx_protocol_setup_properties_dto=dto
            )
            print(f"[BROADCAST] Signatures generated successfully")
            
            # Debug: Check if hash_result_signature is present
            if hasattr(signatures, 'hash_result_signature'):
                print(f"[BROADCAST] hash_result_signature present: {signatures.hash_result_signature is not None}")
            else:
                print(f"[BROADCAST] WARNING: hash_result_signature not in signatures DTO")
            
            # CRITICAL: Use PublishHashTransactionService for hash_result_tx to get complete witness stack
            print(f"[BROADCAST] Building hash_result_tx with complete witness stack...")
            
            # Load prover DTO for input_hex and verifier signatures
            prover_dto_path = f"prover_files/{setup_uuid}/bitvmx_protocol_prover_dto.json"
            prover_dto = None
            print(f"[BROADCAST DEBUG] Looking for prover DTO at: {prover_dto_path}")
            print(f"[BROADCAST DEBUG] File exists: {os.path.exists(prover_dto_path)}")
            if os.path.exists(prover_dto_path):
                with open(prover_dto_path, 'r') as f:
                    prover_dto_dict = json.load(f)
                    print(f"[BROADCAST DEBUG] Loaded dict with keys: {list(prover_dto_dict.keys())[:5]}")
                    print(f"[BROADCAST DEBUG] Dict input_hex: {prover_dto_dict.get('input_hex')}")
                    # Convert dict to DTO
                    from bitvmx_protocol_library.bitvmx_protocol_definition.entities.bitvmx_protocol_prover_dto import BitVMXProtocolProverDTO
                    prover_dto = BitVMXProtocolProverDTO(**prover_dto_dict)
                    print(f"[BROADCAST DEBUG] DTO created, input_hex: {prover_dto.input_hex}")
                    print(f"[BROADCAST] Loaded prover DTO with input_hex: {prover_dto.input_hex is not None}")
            
            if prover_dto and hasattr(dto, 'bitvmx_transactions_dto') and dto.bitvmx_transactions_dto:
                # Use PublishHashTransactionServiceNoBroadcast to build complete witness for hash_result_tx
                from bitvmx_protocol_library.transaction_generation.services.publication_services.prover.publish_hash_transaction_service_no_broadcast import (
                    PublishHashTransactionServiceNoBroadcast
                )
                
                # Create service with prover private key
                publish_hash_service = PublishHashTransactionServiceNoBroadcast(privkey_obj)
                
                try:
                    # Build hash_result_tx with complete witness stack
                    # This adds all signatures + witness data + tapscript + control block
                    hash_result_tx = publish_hash_service(
                        setup_uuid=setup_uuid,
                        bitvmx_protocol_setup_properties_dto=dto,
                        bitvmx_protocol_prover_dto=prover_dto
                    )
                    
                    # Serialize with segwit
                    hash_result_hex = hash_result_tx.to_bytes(has_segwit=True).hex()
                    print(f"[BROADCAST] hash_result_tx built with complete witness, hex length: {len(hash_result_hex)}")
                    
                    # Store in signed_transactions
                    signed_transactions = {"hash_result_tx": hash_result_hex}
                    
                except Exception as e:
                    print(f"[BROADCAST] Failed to build hash_result_tx with PublishHashTransactionService: {e}")
                    # If input is required but missing, abort early with clear status
                    try:
                        needs_input = (
                            dto.bitvmx_protocol_properties_dto.amount_of_input_words > 0 and
                            (getattr(signatures, 'prover_signatures_dto', None) is None or
                             getattr(dto, 'bitvmx_protocol_prover_dto', None) is None or
                             getattr(dto.bitvmx_protocol_prover_dto, 'input_hex', None) in (None, ''))
                        )
                    except Exception:
                        needs_input = False
                    if 'Input should be set' in str(e) or needs_input:
                        print("[BROADCAST] CRITICAL: input_hex is required to publish hash_result_tx. Aborting next_step.")
                        return {
                            "setup_uuid": setup_uuid,
                            "broadcasted_count": 0,
                            "broadcasted_txids": [],
                            "skipped_count": 0,
                            "skipped_txids": [],
                            "failed_count": 0,
                            "failed_txs": [],
                            "status": "input_missing",
                            "message": "Input is required (input_hex not set). Set input via API and retry next_step."
                        }
                    # Do NOT fall back to minimal witness for hash_result (would cause OP_EQUALVERIFY)
                    print("[BROADCAST] Aborting: hash_result_tx build failed for non-input reason. No unsafe fallback.")
                    return {
                        "setup_uuid": setup_uuid,
                        "broadcasted_count": 0,
                        "broadcasted_txids": [],
                        "skipped_count": 0,
                        "skipped_txids": [],
                        "failed_count": 0,
                        "failed_txs": [],
                        "status": "hash_build_failed",
                        "message": f"PublishHashTransactionService failed: {e}"
                    }
            else:
                # Fall back to regular signing if no prover DTO
                print(f"[BROADCAST] No prover DTO found, using regular signature application")
                signed_transactions = apply_signatures_service.apply_signatures_with_private_key(
                    bitvmx_protocol_setup_properties_dto=dto,
                    bitvmx_signatures_dto=signatures,
                    bitvmx_verifier_signatures_dto=signatures.verifier_signatures_dto,
                    prover_private_key_hex=signing_private_key
                )
            
            # Apply signatures to other transactions (trigger, search, etc)
            if signed_transactions and "hash_result_tx" in signed_transactions:
                # Save our correctly built hash_result_tx
                our_hash_result_tx = signed_transactions["hash_result_tx"]
                
                # Apply signatures to remaining transactions
                other_signed = apply_signatures_service.apply_signatures_with_private_key(
                    bitvmx_protocol_setup_properties_dto=dto,
                    bitvmx_signatures_dto=signatures,
                    bitvmx_verifier_signatures_dto=signatures.verifier_signatures_dto if hasattr(signatures, 'verifier_signatures_dto') else None,
                    prover_private_key_hex=signing_private_key
                )
                # CRITICAL: Always use our hash_result_tx, not the one from apply_signatures_service
                if other_signed:
                    # Keep our hash_result_tx, replace theirs
                    other_signed["hash_result_tx"] = our_hash_result_tx
                    signed_transactions = other_signed
                    print(f"[BROADCAST] Preserved our hash_result_tx with complete witness")
            
            print(f"[BROADCAST] All signatures applied successfully")
        else:
            print(f"[BROADCAST] ERROR: No private key available for signing")
            signed_transactions = {}
        
        # Save to file for future use with cache info
        if signed_transactions:
            # Add cache info for validation
            signed_transactions['cache_info'] = {
                'funding_tx_id': expected_funding_txid,
                'funding_index': expected_funding_index,
                'prevout_script': expected_script or '',
                'prevout_amount': expected_amount or 0
            }
            apply_signatures_service.save_signed_transactions(
                setup_uuid=setup_uuid,
                signed_transactions=signed_transactions,
                base_dir="prover_files"
            )
            print(f"[BROADCAST] Signatures regenerated and saved with cache info")
            
            # CRITICAL: Use the SIGNED transactions, not the unsigned dto.serialize()!
            print(f"[BROADCAST] Using regenerated signed transactions")
            
            # Process lists (search and read_search transactions)
            for key in ["read_search_hash_tx_list", "read_search_choice_tx_list",
                        "search_hash_tx_list", "search_choice_tx_list"]:
                if key in signed_transactions:
                    tx_list = signed_transactions[key]
                    if isinstance(tx_list, list):
                        for tx in tx_list:
                            tx_hexes.append(ensure_hex_str(tx))
                        print(f"[BROADCAST] Added {len(tx_list)} {key} transactions")
            
            # Process single transactions
            for key in ["hash_result_tx", "trigger_protocol_tx", "trigger_trace_challenge_tx",
                        "trigger_execution_challenge_tx", "trace_tx", "read_trace_tx"]:
                if key in signed_transactions:
                    tx_hex = ensure_hex_str(signed_transactions[key])
                    tx_hexes.append(tx_hex)
                    print(f"[BROADCAST] Added {key} to broadcast queue (len={len(tx_hex)})")
        else:
            # Fallback: use unsigned transactions if signing failed
            print(f"[BROADCAST] WARNING: No signed transactions, falling back to unsigned")
            txdto = dto.bitvmx_transactions_dto
            
            # Apply fallback mappings
            _fallback_read_lists(txdto)
            
            # Collect all transactions
            candidates = _collect_broadcast_list(txdto)
            
            # Convert to hex strings if needed
            for tx in candidates:
                if isinstance(tx, str):
                    tx_hexes.append(ensure_hex_str(tx))
                elif hasattr(tx, "to_hex"):
                    # Prefer to_hex() which includes witness data
                    tx_hexes.append(ensure_hex_str(tx.to_hex()))
                elif hasattr(tx, "serialize"):
                    # Fallback to serialize() if to_hex() not available
                    tx_hexes.append(ensure_hex_str(tx.serialize()))
                else:
                    print(f"[BROADCAST] Warning: Cannot serialize transaction {type(tx)}")
    else:
        print(f"[BROADCAST] Using signed transactions from file")
        
        # Process lists (search and read_search transactions)
        for key in ["read_search_hash_tx_list", "read_search_choice_tx_list",
                    "search_hash_tx_list", "search_choice_tx_list"]:
            if key in signed_transactions:
                tx_list = signed_transactions[key]
                if isinstance(tx_list, list):
                    for tx in tx_list:
                        tx_hexes.append(ensure_hex_str(tx))
        
        # Process single transactions (EXCLUDE funding_tx here, handle it separately as parent)
        for key in ["hash_result_tx", "trigger_protocol_tx", "trigger_trace_challenge_tx"]:
            if key in signed_transactions:
                tx_hexes.append(ensure_hex_str(signed_transactions[key]))
                print(f"[BROADCAST] Added {key} to broadcast queue")
    
    # Prefer actual funding UTXO over synthetic funding_tx
    dto = persistence.get(setup_uuid=setup_uuid)
    funding_txid_cfg = None
    
    # First try to use the actual on-chain funding UTXO
    if dto and hasattr(dto, "funding_tx_id") and dto.funding_tx_id:
        funding_txid_cfg = dto.funding_tx_id
        print(f"[BROADCAST] Using actual funding UTXO ID: {funding_txid_cfg}")
    # Fallback to generated funding_tx for legacy setups
    elif dto and hasattr(dto, "bitvmx_transactions_dto") and dto.bitvmx_transactions_dto:
        if hasattr(dto.bitvmx_transactions_dto, "funding_tx") and dto.bitvmx_transactions_dto.funding_tx:
            funding_txid_cfg = dto.bitvmx_transactions_dto.funding_tx.get_txid()
            print(f"[BROADCAST] Using generated funding_tx ID (legacy): {funding_txid_cfg}")
    
    # Error if no parent found
    if not funding_txid_cfg:
        print(f"[BROADCAST] ERROR: No funding parent found for setup {setup_uuid}")
        print(f"[BROADCAST] This setup needs transaction regeneration. Use regen_transactions=true flag.")
        return {
            "setup_uuid": setup_uuid,
            "broadcasted_count": 0,
            "skipped_count": 0,
            "failed_count": len(tx_hexes) if tx_hexes else 0,
            "error": "funding_tx_missing",
            "message": "No funding parent found. Setup needs transaction regeneration."
        }
    
    if funding_txid_cfg:
        funding_txid_cfg = funding_txid_cfg.lower()
    
    # Always attempt to broadcast funding_tx first (parent-first principle)
    # If already broadcast, we'll get "already known" error which is fine
    if dto and hasattr(dto, "bitvmx_transactions_dto") and dto.bitvmx_transactions_dto:
        try:
            ftx = getattr(dto.bitvmx_transactions_dto, "funding_tx", None)
            if ftx:
                # Sign the funding transaction if it's unsigned
                ftx_hex = ftx.to_bytes(has_segwit=True).hex()
                
                # Check if transaction has witness data (signed)
                if len(ftx_hex) < 200:  # Unsigned tx is ~192 bytes
                    print(f"[BROADCAST] Funding TX appears unsigned, attempting to sign...")
                    if BITCOIN_LIB_AVAILABLE:
                        try:
                            import os as _os2
                            
                            bitcoin.SelectParams('testnet')
                            
                            # Get private key from environment
                            priv_key_hex = _os2.environ.get("PROVER_PRIVATE_KEY")
                            if priv_key_hex:
                                # Check if transaction is already signed (has witness data)
                                # Signed transactions are typically >400 chars for simple P2WPKH
                                if len(ftx_hex) > 400 and "0247304402" in ftx_hex:  # Contains signature pattern
                                    print(f"[BROADCAST] Funding TX is already signed (length: {len(ftx_hex)}), broadcasting directly")
                                    # Transaction is already signed, broadcast as-is
                                    pass
                                else:
                                    # Create private key object
                                    privkey = CBitcoinSecret.from_secret_bytes(bytes.fromhex(priv_key_hex), compressed=True)
                                    pubkey = privkey.pub
                                    
                                    # Parse the unsigned transaction
                                    tx = CMutableTransaction.deserialize(bytes.fromhex(ftx_hex))
                                
                                # CRITICAL: Get exact input UTXO amount from blockchain
                                # BIP143 requires the exact input amount, not output amount
                                input_amount = None
                                try:
                                    # Get funding tx details from DTO
                                    funding_tx_id = dto.funding_tx_id
                                    funding_index = dto.funding_index
                                    
                                    # Import correct transaction info service (mutinynet)
                                    from blockchain_query_services.services.mutinynet_api.transaction_info_service import TransactionInfoService
                                    tx_info_service = TransactionInfoService()
                                    
                                    # Get the actual UTXO from chain
                                    funding_tx_info = tx_info_service(tx_id=funding_tx_id)
                                    if funding_index < len(funding_tx_info.outputs):
                                        input_amount = funding_tx_info.outputs[funding_index].value
                                        print(f"[BROADCAST] Got exact input UTXO amount from chain: {input_amount} sats")
                                    else:
                                        print(f"[BROADCAST] ERROR: Invalid funding index {funding_index}")
                                        raise ValueError(f"Funding index {funding_index} out of range")
                                except Exception as e:
                                    print(f"[BROADCAST] ERROR: Failed to get exact UTXO amount: {e}")
                                    # This is critical - we cannot sign without exact amount
                                    print(f"[BROADCAST] Cannot sign funding_tx without exact input amount")
                                    input_amount = None
                                
                                    if input_amount is None:
                                        print(f"[BROADCAST] Skipping funding_tx signature due to missing input amount")
                                        ftx_hex = tx.serialize().hex()  # Keep unsigned version
                                    else:
                                        # Detect input type based on address prefix
                                        prover_address = _os2.environ.get("PROVER_ADDRESS", "")
                                        
                                        if prover_address.startswith("tb1q"):
                                            # P2WPKH signing (tb1q...)
                                            print(f"[BROADCAST] Detected P2WPKH address, using BIP143 signing")
                                            witness_program = Hash160(pubkey)
                                            script_for_sig = CScript([OP_DUP, OP_HASH160, witness_program, OP_EQUALVERIFY, OP_CHECKSIG])
                                            
                                            sighash = SignatureHash(script_for_sig, tx, 0, SIGHASH_ALL, 
                                                                  amount=input_amount, sigversion=SIGVERSION_WITNESS_V0)
                                            
                                            # Sign and add witness
                                            sig = privkey.sign(sighash) + bytes([SIGHASH_ALL])
                                            tx.wit = CTxWitness([CTxInWitness([sig, pubkey])])
                                        
                                        elif prover_address.startswith("tb1p"):
                                            # P2TR signing (tb1p...) - Taproot key path
                                            print(f"[BROADCAST] Detected P2TR address, using Taproot key-path signing")
                                            from bitcoin.core.script import SIGHASH_DEFAULT, TaprootSignatureHash
                                            
                                            # For key-path spending, we need taproot sighash
                                            sighash = TaprootSignatureHash(
                                                txTo=tx, 
                                                spent_utxos=[(input_amount, CScript([OP_1, pubkey[1:]]))],  # P2TR scriptPubKey
                                                hash_type=SIGHASH_DEFAULT,
                                                input_index=0
                                            )
                                            
                                            # Schnorr signature (64 bytes, no sighash byte for DEFAULT)
                                            sig = privkey.sign_schnorr(sighash)
                                            tx.wit = CTxWitness([CTxInWitness([sig])])
                                            
                                        else:
                                            # Default to P2WPKH if unknown
                                            print(f"[BROADCAST] Unknown address type, defaulting to P2WPKH")
                                            witness_program = Hash160(pubkey)
                                            script_for_sig = CScript([OP_DUP, OP_HASH160, witness_program, OP_EQUALVERIFY, OP_CHECKSIG])
                                            
                                            sighash = SignatureHash(script_for_sig, tx, 0, SIGHASH_ALL, 
                                                                  amount=input_amount, sigversion=SIGVERSION_WITNESS_V0)
                                            
                                            sig = privkey.sign(sighash) + bytes([SIGHASH_ALL])
                                            tx.wit = CTxWitness([CTxInWitness([sig, pubkey])])
                                        
                                        # Get signed hex
                                        ftx_hex = tx.serialize().hex()
                                        print(f"[BROADCAST] Funding TX signed successfully (len={len(ftx_hex)})")
                            else:
                                print(f"[BROADCAST] No PROVER_PRIVATE_KEY found, using unsigned tx")
                        except Exception as sign_e:
                            print(f"[BROADCAST] Failed to sign funding TX: {sign_e}")
                            print(f"[BROADCAST] Using unsigned tx (may fail)")
                    else:
                        print(f"[BROADCAST] Bitcoin library not available, cannot sign funding TX")
                
                # Check if wrapper TX is already confirmed before trying to broadcast
                wrapper_txid = _get_txid(ftx_hex)
                if wrapper_txid:
                    try:
                        # Check if already confirmed
                        import requests
                        check_url = f"https://mutinynet.com/api/tx/{wrapper_txid}"
                        resp = requests.get(check_url, timeout=5)
                        if resp.status_code == 200:
                            tx_data = resp.json()
                            if tx_data.get("status", {}).get("confirmed", False):
                                print(f"[BROADCAST] Wrapper TX {wrapper_txid[:8]}... already confirmed, skipping broadcast")
                            else:
                                print(f"[BROADCAST] Wrapper TX {wrapper_txid[:8]}... found but unconfirmed, will try broadcast")
                                # Only broadcast synthetic funding_tx if explicitly enabled (for faucet mode)
                                import os
                                if os.environ.get("BITVMX_BROADCAST_FUNDING") == "1":
                                    try:
                                        broadcast_service(transaction=ftx_hex)
                                        print(f"[BROADCAST] Parent funding_tx broadcast attempted")
                                    except Exception as e:
                                        print(f"[BROADCAST] Parent funding_tx broadcast error: {e}")
                        else:
                            # TX not found, try to broadcast
                            print(f"[BROADCAST] Wrapper TX not found on chain, attempting broadcast...")
                            import os
                            if os.environ.get("BITVMX_BROADCAST_FUNDING") == "1":
                                try:
                                    broadcast_service(transaction=ftx_hex)
                                    print(f"[BROADCAST] Parent funding_tx broadcast attempted")
                                except Exception as e:
                                    print(f"[BROADCAST] Parent funding_tx broadcast error: {e}")
                    except Exception as e:
                        print(f"[BROADCAST] Could not check wrapper TX status: {e}")
                else:
                    print(f"[BROADCAST] Skipping synthetic funding_tx broadcast (using external UTXO)")
        except Exception as e:
            print(f"[BROADCAST] Unexpected error preparing parent broadcast: {e}")

    # Sort transactions in topological order (parents before children)
    sorted_txes = _topological_sort(tx_hexes)
    print(f"[BROADCAST] Sorted {len(sorted_txes)} transactions in topological order")
    
    # Filter and broadcast
    broadcasted = []
    skipped = []
    failed = []
    
    # CRITICAL: Check funding_tx is confirmed first
    if funding_txid_cfg:
        import os as _os
        skip_confirm = _os.environ.get("BITVMX_SKIP_FUNDING_MEMPOOL_CHECK") == "1"
        if skip_confirm:
            print(f"[BROADCAST] Skipping funding mempool confirmation (BITVMX_SKIP_FUNDING_MEMPOOL_CHECK=1)")
        else:
            print(f"[BROADCAST] Checking funding_tx {funding_txid_cfg} is confirmed...")
            import time as time_module
            import httpx
            
            funding_confirmed = False
            max_retries = 5  # keep route latency reasonable during outages
            
            for retry in range(max_retries):
                try:
                    check_url = f"https://mutinynet.com/api/tx/{funding_txid_cfg}"
                    with httpx.Client(timeout=8) as client:
                        response = client.get(check_url)
                        if response.status_code == 200:
                            print(f"[BROADCAST] Funding_tx {funding_txid_cfg} is confirmed")
                            funding_confirmed = True
                            break
                        else:
                            print(f"[BROADCAST] Funding_tx not found (status={response.status_code}), retry {retry+1}/{max_retries}")
                except Exception as e:
                    print(f"[BROADCAST] Error checking funding_tx: {e}")
                # Exponential backoff but cap total wait
                if retry < max_retries - 1:
                    delay = 2 * (retry + 1)
                    print(f"[BROADCAST] Waiting {delay} seconds before retry...")
                    time_module.sleep(delay)
            
            if not funding_confirmed:
                print(f"[BROADCAST] WARNING: Funding_tx {funding_txid_cfg} not confirmed; proceeding due to outage")
    
    # Check if funding UTXO is already Taproot (no wrapper needed)
    # IMPORTANT: In no-faucet mode, the wrapper TX creates a Taproot output
    # If the current funding_tx_id is the wrapper TX (already broadcasted), it IS Taproot
    is_taproot_utxo = False
    
    # First, check if this is a wrapper TX that was already created and confirmed
    if dto and hasattr(dto, "funding_tx_id"):
        current_funding_txid = dto.funding_tx_id
        # Check if this funding TX is already confirmed
        try:
            import requests
            check_url = f"https://mutinynet.com/api/tx/{current_funding_txid}"
            resp = requests.get(check_url, timeout=5)
            if resp.status_code == 200:
                tx_data = resp.json()
                if tx_data.get("status", {}).get("confirmed", False):
                    # TX is confirmed, check if it's a Taproot output
                    if "vout" in tx_data and expected_funding_index < len(tx_data["vout"]):
                        scriptpubkey = tx_data["vout"][expected_funding_index].get("scriptpubkey", "")
                        if scriptpubkey.startswith('5120'):  # Taproot (OP_1 + 32 bytes)
                            is_taproot_utxo = True
                            print(f"[BROADCAST] Funding TX {current_funding_txid[:8]}... is confirmed Taproot (wrapper already done)")
                        else:
                            print(f"[BROADCAST] Funding TX is confirmed but not Taproot: {scriptpubkey[:10]}...")
                else:
                    print(f"[BROADCAST] Funding TX {current_funding_txid[:8]}... exists but unconfirmed")
        except Exception as e:
            print(f"[BROADCAST] Could not check current funding TX status: {e}")
    
    # Fallback: Check using transaction info service
    if not is_taproot_utxo:
        try:
            from blockchain_query_services.services.mutinynet_api.transaction_info_service import TransactionInfoService
            tx_info_service = TransactionInfoService()
            funding_info = tx_info_service(tx_id=expected_funding_txid)
            if expected_funding_index < len(funding_info.outputs):
                scriptpubkey = funding_info.outputs[expected_funding_index].scriptpubkey
                if scriptpubkey and scriptpubkey.startswith('5120'):  # Taproot
                    is_taproot_utxo = True
                    print(f"[BROADCAST] Funding UTXO is already Taproot, skipping wrapper TX")
        except Exception as e:
            print(f"[BROADCAST] Could not check funding UTXO type via service: {e}")
    
    # CRITICAL: Broadcast funding_tx (wrapper) FIRST if it exists and needed
    # This wraps P2WPKH UTXO to Taproot for BitVMX compatibility
    funding_broadcasted = False
    if not is_taproot_utxo and 'funding_tx' in signed_transactions:
        funding_hex = ensure_hex_str(signed_transactions['funding_tx'])
        if funding_hex and len(funding_hex) > 100:  # Valid signed tx should be >100 chars
            try:
                print(f"[BROADCAST] Broadcasting funding_tx (wrapper) FIRST...")
                print(f"[BROADCAST] Funding TX hex length: {len(funding_hex)} chars")
                broadcast_service(transaction=funding_hex)
                funding_broadcasted = True
                print(f"[BROADCAST] SUCCESS: funding_tx (wrapper) broadcast completed")
                # Wait for wrapper to propagate
                wrapper_txid = _get_txid(funding_hex)
                if wrapper_txid:
                    print(f"[BROADCAST] Waiting for wrapper TX {wrapper_txid[:8]}... to propagate")
                    if not _wait_for_mempool_propagation(wrapper_txid):
                        print(f"[BROADCAST] ERROR: Wrapper TX not found in mempool after 30s")
                        return {
                            "setup_uuid": setup_uuid,
                            "broadcasted_count": 0,
                            "skipped_count": 0,
                            "failed_count": 1,
                            "error": "wrapper_not_propagated",
                            "message": "Wrapper transaction failed to propagate to mempool"
                        }
                
                # Give mempool time to propagate
                import time as _time
                _time.sleep(2)
                
            except Exception as e:
                error_msg = str(e).lower()
                if any(phrase in error_msg for phrase in [
                    "already in block chain",
                    "txn-already-in-mempool", 
                    "txn-mempool-conflict",
                    "already have transaction"
                ]):
                    print(f"[BROADCAST] funding_tx already in mempool/chain (good)")
                    funding_broadcasted = True
                else:
                    print(f"[BROADCAST] WARNING: Failed to broadcast funding_tx: {e}")
        else:
            print(f"[BROADCAST] WARNING: Invalid or missing funding_tx hex")
    
    # Fallback: Try from DTO if not in signed_transactions
    # IMPORTANT: Skip if is_taproot_utxo is True (wrapper already done)
    if not funding_broadcasted and not is_taproot_utxo:
        try:
            from os import getenv as _getenv
            auto_broadcast_funding = _getenv("BITVMX_BROADCAST_FUNDING", "1") == "1"
            if auto_broadcast_funding and dto and hasattr(dto, 'bitvmx_transactions_dto') and dto.bitvmx_transactions_dto:
                ftx_obj = getattr(dto.bitvmx_transactions_dto, 'funding_tx', None)
                if ftx_obj:
                    try:
                        # Ensure a minimal fee for funding wrapper
                        try:
                            from math import ceil
                            def _estimate_vsize_from_hex(tx_hex: str) -> int:
                                try:
                                    b = bytes.fromhex(tx_hex)
                                    segwit = len(b) > 6 and b[4] == 0x00 and b[5] == 0x01
                                    return ceil(len(b) * 0.75) if segwit else len(b)
                                except Exception:
                                    return 180
                            min_sat_vb = int(_getenv('FUNDING_MIN_SAT_VB', '3'))
                        except Exception:
                            min_sat_vb = 3
                        # If we know prevout amount, reduce output to pay min fee
                        if expected_amount and hasattr(ftx_obj, 'outputs') and ftx_obj.outputs:
                            provisional_hex = ensure_hex_str(ftx_obj.to_hex() if hasattr(ftx_obj, 'to_hex') else '')
                            vsize = _estimate_vsize_from_hex(provisional_hex) if provisional_hex else 180
                            need_fee = vsize * min_sat_vb
                            target_amount = max(0, int(expected_amount) - int(need_fee))
                            if ftx_obj.outputs[0].amount > target_amount:
                                ftx_obj.outputs[0].amount = target_amount
                                print(f"[BROADCAST] Adjusted funding output for fee: vsize={vsize}, fee>={need_fee} sats")
                        ftx_hex = ensure_hex_str(ftx_obj.to_hex() if hasattr(ftx_obj, 'to_hex') else ftx_obj)
                        if ftx_hex and len(ftx_hex) > 100:
                            print(f"[BROADCAST] Broadcasting funding_tx from DTO (fallback)...")
                            broadcast_service(transaction=ftx_hex)
                            print(f"[BROADCAST] Success broadcasting funding_tx from DTO")
                            funding_broadcasted = True
                            # Wait for funding to propagate
                            dto_ftx_txid = _get_txid(ftx_hex)
                            if dto_ftx_txid:
                                print(f"[BROADCAST] Waiting for DTO funding TX {dto_ftx_txid[:8]}... to propagate")
                                if not _wait_for_mempool_propagation(dto_ftx_txid):
                                    print(f"[BROADCAST] WARNING: DTO funding TX not found in mempool after 30s")
                    except Exception as e:
                        print(f"[BROADCAST] WARNING: Failed to broadcast funding_tx from DTO: {e}")
        except Exception as e:
            print(f"[BROADCAST] Fallback funding broadcast error: {e}")

    # If funding still not propagated, abort children to avoid inputs-missingorspent
    # UNLESS the UTXO is already Taproot (wrapper was done in setup phase)
    try:
        if not funding_broadcasted and not is_taproot_utxo and expected_funding_txid:
            print(f"[BROADCAST] WARNING: Funding not broadcasted; aborting children")
            return {
                "setup_uuid": setup_uuid,
                "broadcasted_count": 0,
                "broadcasted_txids": [],
                "skipped_count": 0,
                "skipped_txids": [],
                "failed_count": 0,
                "failed_txs": [],
                "status": "funding_not_broadcasted",
            }
        elif is_taproot_utxo:
            print(f"[BROADCAST] Funding is already Taproot, proceeding with child transactions")
    except Exception:
        pass

    # Parent-first mode: Broadcast hash_result_tx first and wait for confirmation
    hash_result_txid = None
    parent_confirmed = False
    
    # Find and broadcast hash_result_tx first
    if 'hash_result_tx' in signed_transactions:
        hash_result_hex = ensure_hex_str(signed_transactions['hash_result_tx'])
        hash_result_txid = _get_txid(hash_result_hex)
        
        if hash_result_txid:
            print(f"[BROADCAST] Parent-first mode: Broadcasting hash_result_tx {hash_result_txid}")
            try:
                broadcast_service(transaction=hash_result_hex)
                broadcasted.append(hash_result_txid)
                print(f"[BROADCAST] Success: hash_result_tx {hash_result_txid}")
                parent_confirmed = True  # Mark as confirmed if broadcast succeeds
                
            except Exception as e:
                error_msg = str(e)
                print(f"[BROADCAST] hash_result_tx broadcast error: {error_msg}")
                
                # Check various error messages that indicate already confirmed
                already_confirmed = any(phrase in error_msg.lower() for phrase in [
                    "already in block chain",
                    "txn-already-in-mempool",
                    "txn-mempool-conflict",
                    "already have transaction"
                ])
                
                if already_confirmed:
                    print(f"[BROADCAST] hash_result_tx appears to be already confirmed: {hash_result_txid}")
                    broadcasted.append(hash_result_txid)
                    parent_confirmed = True  # Already confirmed
                else:
                    print(f"[BROADCAST] Failed to broadcast hash_result_tx: {e}")
                    failed.append({"txid": hash_result_txid, "error": error_msg})
                    parent_confirmed = False  # Failed to broadcast
                    
            # Enhanced parent confirmation gating
            if parent_confirmed:
                # Wait for parent to propagate with stronger gating
                import time as time_module2
                import httpx
                max_retries = 8  # Increased from 2 to 8
                retry_delay = 5  # Increased from 3 to 5
                parent_in_mempool = False
                
                print(f"[BROADCAST] Waiting for parent {hash_result_txid} to propagate to mempool...")
                
                for retry in range(max_retries):
                    time_module2.sleep(retry_delay)
                    try:
                        # Check if transaction is in mempool
                        check_url = f"https://mutinynet.com/api/tx/{hash_result_txid}"
                        with httpx.Client(timeout=10) as client:
                            response = client.get(check_url)
                            if response.status_code == 200:
                                print(f"[BROADCAST] Parent confirmed in mempool after {retry+1} retries: {hash_result_txid}")
                                parent_in_mempool = True
                                break
                            else:
                                print(f"[BROADCAST] Parent not yet in mempool, retry {retry+1}/{max_retries}")
                                # Exponential backoff after 3rd retry
                                if retry >= 2:
                                    retry_delay = min(retry_delay * 1.5, 10)
                    except Exception as check_e:
                        print(f"[BROADCAST] Error checking parent: {check_e}")
                
                # CRITICAL: Block child transactions if parent is not confirmed
                if not parent_in_mempool:
                    print(f"[BROADCAST] CRITICAL: Parent {hash_result_txid} not propagated after {max_retries} retries")
                    print(f"[BROADCAST] Aborting child transactions to prevent inputs-missingorspent errors")
                    return {
                        "setup_uuid": setup_uuid,
                        "broadcasted_count": len(broadcasted),
                        "broadcasted_txids": broadcasted,
                        "skipped_count": len(skipped),
                        "skipped_txids": skipped,
                        "failed_count": 0,
                        "failed_txs": [],
                        "status": "parent_not_propagated",
                        "message": f"Parent transaction {hash_result_txid} not confirmed in mempool. Please retry /next_step in 30-60 seconds."
                    }
    
    # Skip RPC validation for Mutinynet - directly broadcast remaining transactions
    for tx_hex in sorted_txes:
        try:
            # Get txid from hex
            txid = _get_txid(tx_hex)
            
            # Skip funding_tx
            if txid and funding_txid_cfg and txid.lower() == funding_txid_cfg:
                print(f"[BROADCAST] Skip funding txid={txid}")
                skipped.append(txid)
                continue
            
            # Skip hash_result_tx (already broadcasted in parent-first mode)
            if txid and hash_result_txid and txid.lower() == hash_result_txid.lower():
                print(f"[BROADCAST] Skip hash_result_tx (already broadcasted)")
                continue
            
            # Ensure tx_hex is a string before broadcasting
            tx_hex_str = ensure_hex_str(tx_hex)
            if not tx_hex_str:
                print(f"[BROADCAST] Warning: Empty or invalid tx hex, skipping")
                continue
                
            # Directly broadcast to Mutinynet (no local RPC validation)
            print(f"[BROADCAST] Broadcasting transaction {txid or 'unknown'} to Mutinynet...")
            print(f"[BROADCAST] tx_hex type={type(tx_hex_str)} len={len(tx_hex_str)}")
            broadcast_service(transaction=tx_hex_str)
            broadcasted.append(txid or "<unknown>")
            print(f"[BROADCAST] Success: {txid or 'unknown'}")
            
        except Exception as e:
            error_msg = str(e)
            print(f"[BROADCAST ERROR] Exception type: {type(e).__name__}")
            print(f"[BROADCAST ERROR] Message: {error_msg}")
            if "min relay fee" in error_msg:
                print(f"[BROADCAST] Fee too low for {txid or 'unknown'}: {error_msg}")
            elif "fromhex" in error_msg:
                print(f"[BROADCAST] Type error for {txid or 'unknown'}: {error_msg}")
                # Add traceback for debugging
                import traceback
                traceback.print_exc()
                # Re-raise to see full stack
                raise
            else:
                print(f"[BROADCAST] Failed for {txid or 'unknown'}: {error_msg}")
                # Add traceback for debugging
                import traceback
                traceback.print_exc()
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
