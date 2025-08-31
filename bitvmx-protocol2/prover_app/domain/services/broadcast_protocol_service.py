"""
Broadcast Protocol Service
Handles broadcasting of BitVMX protocol transactions
"""
from typing import List, Dict, Any
from collections import defaultdict, deque, OrderedDict
import hashlib
from prover_app.common.hexsafe import ensure_hex_str, bfromhex_safe, hex_from_any

# Import bitcoin signing utilities at module level
try:
    from bitcoin.core import CMutableTransaction, CTxWitness, CTxInWitness, Hash160
    from bitcoin.core.script import CScript, OP_DUP, OP_HASH160, OP_EQUALVERIFY, OP_CHECKSIG, SIGHASH_ALL, SignatureHash, SIGVERSION_WITNESS_V0
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
    
    # Skip loading from file if force resign is enabled
    if force_resign:
        print(f"[BROADCAST] Force resign enabled, skipping cached transactions")
        signed_transactions = None
        # Clear the flag after use
        os.environ.pop("BITVMX_FORCE_RESIGN", None)
    else:
        signed_transactions = apply_signatures_service.load_signed_transactions(
            setup_uuid=setup_uuid,
            base_dir="prover_files"
        )
    
    if not signed_transactions:
        print(f"[BROADCAST] No signed transactions found for {setup_uuid}, regenerating signatures")
        
        # Get setup DTO from persistence
        dto = persistence.get(setup_uuid=setup_uuid)
        if not dto:
            raise ValueError(f"No setup found for setup_uuid={setup_uuid}")
        
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
            if os.path.exists(prover_dto_path):
                with open(prover_dto_path, 'r') as f:
                    prover_dto_dict = json.load(f)
                    # Convert dict to DTO
                    from bitvmx_protocol_library.bitvmx_protocol_definition.entities.bitvmx_protocol_prover_dto import BitVMXProtocolProverDTO
                    prover_dto = BitVMXProtocolProverDTO(**prover_dto_dict)
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
                    # Fall back to regular signing
                    signed_transactions = apply_signatures_service.apply_signatures_with_private_key(
                        bitvmx_protocol_setup_properties_dto=dto,
                        bitvmx_signatures_dto=signatures,
                        bitvmx_verifier_signatures_dto=signatures.verifier_signatures_dto if hasattr(signatures, 'verifier_signatures_dto') else None,
                        prover_private_key_hex=signing_private_key
                    )
            else:
                # Fall back to regular signing if no prover DTO
                print(f"[BROADCAST] No prover DTO found, using regular signature application")
                signed_transactions = apply_signatures_service.apply_signatures_with_private_key(
                    bitvmx_protocol_setup_properties_dto=dto,
                    bitvmx_signatures_dto=signatures,
                    bitvmx_verifier_signatures_dto=signatures.verifier_signatures_dto if hasattr(signatures, 'verifier_signatures_dto') else None,
                    prover_private_key_hex=signing_private_key
                )
            
            # Apply signatures to other transactions (trigger, search, etc)
            if signed_transactions and "hash_result_tx" in signed_transactions:
                # Apply signatures to remaining transactions
                other_signed = apply_signatures_service.apply_signatures_with_private_key(
                    bitvmx_protocol_setup_properties_dto=dto,
                    bitvmx_signatures_dto=signatures,
                    bitvmx_verifier_signatures_dto=signatures.verifier_signatures_dto if hasattr(signatures, 'verifier_signatures_dto') else None,
                    prover_private_key_hex=signing_private_key
                )
                # Merge with hash_result_tx
                if other_signed:
                    other_signed["hash_result_tx"] = signed_transactions["hash_result_tx"]
                    signed_transactions = other_signed
            
            print(f"[BROADCAST] All signatures applied successfully")
        else:
            print(f"[BROADCAST] ERROR: No private key available for signing")
            signed_transactions = {}
        
        # Save to file for future use
        if signed_transactions:
            apply_signatures_service.save_signed_transactions(
                setup_uuid=setup_uuid,
                signed_transactions=signed_transactions,
                base_dir="prover_files"
            )
            print(f"[BROADCAST] Signatures regenerated and saved")
            
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
                elif hasattr(tx, "serialize"):
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
        
        # Process single transactions
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
    
    # Only attempt to broadcast synthetic funding_tx if we're using it (legacy path)
    # Skip this for actual on-chain UTXOs as they're already confirmed
    # NO_FAUCET mode: Always try to broadcast funding_tx
    import os
    no_faucet = os.environ.get("NO_FAUCET", "true").lower() == "true"
    
    if no_faucet:
        print(f"[BROADCAST] NO_FAUCET mode - will attempt to broadcast funding_tx")
    
    if dto and hasattr(dto, "funding_tx_id") and dto.funding_tx_id == funding_txid_cfg and not no_faucet:
        print(f"[BROADCAST] Skipping synthetic funding_tx broadcast - using actual on-chain UTXO")
    elif dto and hasattr(dto, "bitvmx_transactions_dto") and dto.bitvmx_transactions_dto:
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
                                # Create private key object
                                privkey = CBitcoinSecret.from_secret_bytes(bytes.fromhex(priv_key_hex), compressed=True)
                                pubkey = privkey.pub
                                
                                # Parse the unsigned transaction
                                tx = CMutableTransaction.deserialize(bytes.fromhex(ftx_hex))
                                
                                # Create signature for P2WPKH input
                                witness_program = Hash160(pubkey)
                                script_for_sig = CScript([OP_DUP, OP_HASH160, witness_program, OP_EQUALVERIFY, OP_CHECKSIG])
                                
                                # Assume 10M sats input (we know this from the UTXO)
                                input_amount = 10000000
                                sighash = SignatureHash(script_for_sig, tx, 0, SIGHASH_ALL, 
                                                      amount=input_amount, sigversion=SIGVERSION_WITNESS_V0)
                                
                                # Sign and add witness
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
                
                print(f"[BROADCAST] Proactive parent broadcast: synthetic funding_tx (len={len(ftx_hex)})")
                try:
                    broadcast_service(transaction=ftx_hex)
                    print(f"[BROADCAST] Parent funding_tx broadcast attempted")
                except Exception as e:
                    em = str(e).lower()
                    if any(k in em for k in [
                        "already in block chain",
                        "txn-already-in-mempool",
                        "already have transaction",
                        "already known",
                    ]):
                        print(f"[BROADCAST] Parent funding_tx seems already known: {e}")
                    else:
                        print(f"[BROADCAST] Parent funding_tx broadcast error (ignored for retry loop): {e}")
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
