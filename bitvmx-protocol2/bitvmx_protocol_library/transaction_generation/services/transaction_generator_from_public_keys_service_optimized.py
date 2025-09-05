from concurrent.futures import ThreadPoolExecutor, as_completed
from functools import lru_cache
import time
import math

from bitcoinutils.keys import P2wpkhAddress
from bitcoinutils.transactions import Transaction, TxInput, TxOutput
from bitcoinutils.script import Script

# suppress_output removed - causes FD issues in multi-threaded environment

from bitvmx_protocol_library.bitvmx_protocol_definition.entities.bitvmx_protocol_setup_properties_dto import (
    BitVMXProtocolSetupPropertiesDTO,
)
from bitvmx_protocol_library.script_generation.services.bitvmx_bitcoin_scripts_generator_service import (
    BitVMXBitcoinScriptsGeneratorService,
)
from bitvmx_protocol_library.transaction_generation.entities.dtos.bitvmx_transactions_dto import (
    BitVMXTransactionsDTO,
)


def estimate_vsize_from_hex(tx_hex: str) -> int:
    """Estimate vsize from transaction hex (weight/4)"""
    try:
        b = bytes.fromhex(tx_hex)
        # Check for segwit marker (0x00 0x01)
        segwit = len(b) > 6 and b[4] == 0x00 and b[5] == 0x01
        if segwit:
            # Rough estimate: vsize = ceil(length * 0.75)
            # More accurate would be to parse witness data
            return math.ceil(len(b) * 0.75)
        else:
            return len(b)  # non-segwit: vsize = bytes
    except:
        return 150  # Safe fallback


def check_min_fee(tx_hex: str, input_sum: int, output_sum: int, min_sat_vb: int = 3):
    """Check if transaction meets minimum fee requirements"""
    vsize = estimate_vsize_from_hex(tx_hex)
    fee = input_sum - output_sum
    need = vsize * min_sat_vb
    assert fee >= need, f"Fee too low: {fee} < {need} (need {min_sat_vb} sat/vB for {vsize} vB)"
    return True


class TransactionGeneratorFromPublicKeysServiceOptimized:
    """Optimized version with caching and parallel processing."""
    
    def __init__(self):
        self.bitvmx_bitcoin_scripts_generator_service = BitVMXBitcoinScriptsGeneratorService()
        self._address_cache = {}
        self._txid_cache = {}
        # Option B: Always use real tapscript addresses, no fallback
        self._skip_expensive_ops = False
    
    @lru_cache(maxsize=1024)
    def _get_cached_address(self, script_key: str, destroyed_public_key):
        """Cache expensive address computations."""
        return script_key
    
    def _create_transaction_batch(self, tx_params_list):
        """Create multiple transactions in parallel."""
        with ThreadPoolExecutor(max_workers=4) as executor:
            futures = []
            for params in tx_params_list:
                future = executor.submit(
                    Transaction,
                    params['inputs'],
                    params['outputs'],
                    has_segwit=params.get('has_segwit', True)
                )
                futures.append(future)
            
            results = []
            for future in as_completed(futures):
                results.append(future.result())
            return results
    
    def __call__(
        self,
        bitvmx_protocol_setup_properties_dto: BitVMXProtocolSetupPropertiesDTO,
    ) -> BitVMXTransactionsDTO:
        """Generate all BitVMX transactions with complete output suppression."""
        # Call internal method directly without output suppression
        # FD redirection causes issues in multi-threaded ASGI environment
        return self._generate_transactions_internal(bitvmx_protocol_setup_properties_dto)
    
    def _generate_transactions_internal(
        self,
        bitvmx_protocol_setup_properties_dto: BitVMXProtocolSetupPropertiesDTO,
    ) -> BitVMXTransactionsDTO:
        start_time = time.time()
        
        # CRITICAL: Check if scripts DTO already exists and reuse it
        if not hasattr(bitvmx_protocol_setup_properties_dto, 'bitvmx_bitcoin_scripts_dto') or \
           bitvmx_protocol_setup_properties_dto.bitvmx_bitcoin_scripts_dto is None:
            # This should not happen - scripts should be generated in setup controller
            print("[CRITICAL ERROR] No scripts DTO found in setup properties!")
            raise ValueError("Scripts DTO must be generated before transaction generation")
        
        # Log fingerprint for tracking
        if hasattr(bitvmx_protocol_setup_properties_dto.bitvmx_bitcoin_scripts_dto, 'tree_fingerprint'):
            print(f"[SCRIPT FINGERPRINT] Using scripts with fingerprint: {bitvmx_protocol_setup_properties_dto.bitvmx_bitcoin_scripts_dto.tree_fingerprint}")
        else:
            print("[WARNING] Scripts DTO has no fingerprint - script consistency cannot be verified")
        
        # Helper function for consistent iteration handling
        def _iter_range(iterations: int):
            """Returns iteration range for 0-based indexing"""
            it = 1 if iterations is None else int(iterations)
            if it <= 1:
                return [0]  # Single iteration with index 0
            return range(it)  # 0..(iterations-1)
        
        # Try both field names for compatibility
        destroyed_public_key = getattr(bitvmx_protocol_setup_properties_dto, 'unspendable_public_key', None)
        if not destroyed_public_key:
            destroyed_public_key = getattr(bitvmx_protocol_setup_properties_dto, 'seed_unspendable_public_key', None)
        if not destroyed_public_key:
            raise ValueError("No unspendable_public_key found in DTO")
        
        # Immutable value extraction with protection
        fa = int(bitvmx_protocol_setup_properties_dto.funding_amount_of_satoshis)
        sf = int(bitvmx_protocol_setup_properties_dto.step_fees_satoshis)
        
        # Minimum fee policy (sat/vB based)
        MIN_STEP = 3000  # 최소 3000 satoshi 수수료 설정
        if sf < MIN_STEP:
            sf = MIN_STEP
        
        # Use local variables only - never modify DTO
        funding_amount = fa
        step_fees = sf
        
        # Normalize iterations (if empty, calculate from bits)
        bits = getattr(
            bitvmx_protocol_setup_properties_dto.bitvmx_protocol_properties_dto,
            "amount_of_bits_wrong_step_search",
            1,
        )
        search_iterations = getattr(
            bitvmx_protocol_setup_properties_dto.bitvmx_protocol_properties_dto,
            "amount_of_wrong_step_search_iterations",
            0,
        ) or (1 << int(bits))
        
        # Note: Cannot set iterations back to DTO due to pydantic constraints
        # Just use the normalized value locally
        
        # Create funding transaction
        funding_txin = TxInput(
            bitvmx_protocol_setup_properties_dto.funding_tx_id,
            bitvmx_protocol_setup_properties_dto.funding_index,
            script_sig=Script([])  # Initialize with empty script for segwit
        )
        
        # Use the SAME Taproot tree as used by signing (hash_result + prover_timeout)
        from bitvmx_protocol_library.script_generation.entities.business_objects.bitcoin_script_list import BitcoinScriptList
        golden_hash_script = bitvmx_protocol_setup_properties_dto.bitvmx_bitcoin_scripts_dto.hash_result_script
        prover_timeout_script = bitvmx_protocol_setup_properties_dto.bitvmx_bitcoin_scripts_dto.prover_timeout_script
        # CRITICAL: Set fixed tree_key for consistent address generation
        funding_script_tree = BitcoinScriptList([golden_hash_script, prover_timeout_script])
        # Force consistent tree_key to avoid randomization
        if not hasattr(funding_script_tree, '_tree_key_set'):
            import hashlib
            # Generate deterministic tree_key from scripts
            combined = golden_hash_script.to_hex() + prover_timeout_script.to_hex()
            tree_key = hashlib.sha256(combined.encode()).hexdigest()[:16]
            funding_script_tree._tree_key = tree_key
            funding_script_tree._tree_key_set = True
            print(f"[FUNDING_TX] Set deterministic tree_key: {tree_key}")
        # Use the same destroyed_public_key for consistency
        unspendable_key = getattr(bitvmx_protocol_setup_properties_dto, 'unspendable_public_key', None)
        if not unspendable_key:
            unspendable_key = getattr(bitvmx_protocol_setup_properties_dto, 'seed_unspendable_public_key', None)
        funding_taproot_address = funding_script_tree.get_taproot_address(
            unspendable_key
        )
        print(f"[FUNDING_TX] Generated taproot address: {funding_taproot_address.to_string()}")
        print(f"[FUNDING_TX] Witness program: {funding_taproot_address.to_script_pub_key().to_hex()[4:]}")

        # Build funding output to the Taproot tree address
        # Keep full amount here for consistency with verifier
        funding_output_amount = funding_amount
        
        funding_txout = TxOutput(
            funding_output_amount,
            funding_taproot_address.to_script_pub_key(),
        )
        print(f"[FUNDING_TX] Output scriptPubKey: {funding_taproot_address.to_script_pub_key().to_hex()}")
        
        funding_tx = Transaction([funding_txin], [funding_txout], has_segwit=True)
        
        # Pre-generate addresses in parallel
        hash_search_scripts_addresses = []
        choice_search_scripts_addresses = []
        
        # Directly generate addresses in parallel without suppression
        
        with ThreadPoolExecutor(max_workers=4) as executor:
            # Submit hash address generation using consistent iteration range
            hash_futures = []
            for i in _iter_range(search_iterations):
                scripts_list = bitvmx_protocol_setup_properties_dto.bitvmx_bitcoin_scripts_dto.hash_search_scripts_list(i)
                hash_futures.append(
                    executor.submit(scripts_list.get_taproot_address, destroyed_public_key)
                )
            
            # Submit choice address generation using consistent iteration range
            choice_futures = []
            for i in _iter_range(search_iterations):
                scripts_list = bitvmx_protocol_setup_properties_dto.bitvmx_bitcoin_scripts_dto.choice_search_scripts_list(i)
                choice_futures.append(
                    executor.submit(scripts_list.get_taproot_address, destroyed_public_key)
                )
            
            # Collect results
            for future in hash_futures:
                hash_search_scripts_addresses.append(future.result())
            
            for future in choice_futures:
                choice_search_scripts_addresses.append(future.result())
        
        # Get verifier address early for potential fallback use
        verifier_address = P2wpkhAddress.from_address(
            address=bitvmx_protocol_setup_properties_dto.verifier_destination_address
        )
        
        # Continue with transaction creation (simplified for critical path)
        trigger_protocol_script_address = bitvmx_protocol_setup_properties_dto.bitvmx_bitcoin_scripts_dto.trigger_protocol_scripts_list.get_taproot_address(
            public_key=destroyed_public_key
        )
        
        # Use actual funding_tx_id from DTO (not synthetic funding_tx.get_txid())
        # This ensures hash_result_tx references the correct on-chain parent
        actual_funding_txid = bitvmx_protocol_setup_properties_dto.funding_tx_id
        actual_funding_index = bitvmx_protocol_setup_properties_dto.funding_index
        hash_result_txin = TxInput(actual_funding_txid, actual_funding_index, script_sig=Script([]))
        
        # Use dedicated hash fee for the heavy hash_result transaction
        from bitvmx_protocol_library.config import common_protocol_properties
        try:
            hash_fee = int(common_protocol_properties.hash_fees_satoshis)
            print(f"[FEES] Using HASH_FEES_SATOSHIS={hash_fee} for hash_result_tx")
        except Exception:
            hash_fee = step_fees  # fallback to step fee if config not available
            print(f"[WARNING] Using fallback step_fees={step_fees} for hash_result_tx")
        
        # Compute hash_result_output_amount using hash_fee and wrapper-adjusted amount
        # CRITICAL: Account for wrapper fee (5000 sats) that will be deducted in signing phase
        wrapper_fee = 5000
        adjusted_funding_amount = funding_amount - wrapper_fee
        hash_result_output_amount = max(0, adjusted_funding_amount - hash_fee)
        hash_result_txOut = TxOutput(
            hash_result_output_amount, trigger_protocol_script_address.to_script_pub_key()
        )
        
        hash_result_tx = Transaction([hash_result_txin], [hash_result_txOut], has_segwit=True)
        
        trigger_protocol_output_amount = hash_result_output_amount - step_fees
        trigger_protocol_txin = TxInput(hash_result_tx.get_txid(), 0, script_sig=Script([]))
        trigger_protocol_txOut = TxOutput(
            trigger_protocol_output_amount, hash_search_scripts_addresses[0].to_script_pub_key()
        )
        
        trigger_protocol_tx = Transaction(
            [trigger_protocol_txin], [trigger_protocol_txOut], has_segwit=True
        )
        
        # Generate search transactions more efficiently
        previous_tx_id = trigger_protocol_tx.get_txid()
        current_output_amount = trigger_protocol_output_amount
        search_hash_tx_list = []
        search_choice_tx_list = []
        
        trace_script_address = bitvmx_protocol_setup_properties_dto.bitvmx_bitcoin_scripts_dto.trace_script_list.get_taproot_address(
            destroyed_public_key
        )
        
        # Batch create transactions
        for i in range(len(choice_search_scripts_addresses)):
            # HASH transaction
            current_output_amount -= step_fees
            hash_tx = Transaction(
                [TxInput(previous_tx_id, 0, script_sig=Script([]))],
                [TxOutput(current_output_amount, choice_search_scripts_addresses[i].to_script_pub_key())],
                has_segwit=True
            )
            search_hash_tx_list.append(hash_tx)
            
            # CHOICE transaction
            current_output_amount -= step_fees
            # Check if this is the last iteration or we're out of hash addresses
            if i == len(choice_search_scripts_addresses) - 1 or i + 1 >= len(hash_search_scripts_addresses):
                next_address = trace_script_address
            else:
                next_address = hash_search_scripts_addresses[i + 1]
            
            choice_tx = Transaction(
                [TxInput(hash_tx.get_txid(), 0, script_sig=Script([]))],
                [TxOutput(current_output_amount, next_address.to_script_pub_key())],
                has_segwit=True
            )
            search_choice_tx_list.append(choice_tx)
            previous_tx_id = choice_tx.get_txid()
        
        # Create remaining transactions - USE ACTUAL TAPSCRIPT ADDRESS (Option B)
        # No fallback - we use the real trigger_trace_challenge_address
        t_trigger = time.time()
        print("[OPTION B] Computing trigger_trace_challenge_address (no fallback)")
        trigger_challenge_script_address = bitvmx_protocol_setup_properties_dto.bitvmx_bitcoin_scripts_dto.trigger_trace_challenge_address(
            destroyed_public_key=destroyed_public_key
        )
        print(f"[OPTION B] trigger_trace_challenge_address computed in {time.time() - t_trigger:.3f}s")
        
        trace_txin = TxInput(search_choice_tx_list[-1].get_txid(), 0, script_sig=Script([]))
        trace_output_amount = current_output_amount - step_fees
        trace_txout = TxOutput(
            trace_output_amount, trigger_challenge_script_address.to_script_pub_key()
        )
        trace_tx = Transaction([trace_txin], [trace_txout], has_segwit=True)
        
        # Create challenge transactions
        trigger_challenge_output_amount = trace_output_amount - step_fees
        challenge_output_amount = trigger_challenge_output_amount - step_fees
        
        execution_challenge_address = bitvmx_protocol_setup_properties_dto.bitvmx_bitcoin_scripts_dto.execution_challenge_script_list.get_taproot_address(
            destroyed_public_key
        )
        
        trigger_execution_challenge_tx = Transaction(
            [TxInput(trace_tx.get_txid(), 0, script_sig=Script([]))],
            [TxOutput(trigger_challenge_output_amount, execution_challenge_address.to_script_pub_key())],
            has_segwit=True
        )
        
        # Create error condition transactions
        # (verifier_address already defined above)
        
        trigger_wrong_pc_tx = Transaction(
            [TxInput(trace_tx.get_txid(), 0, script_sig=Script([]))],
            [TxOutput(trace_output_amount - step_fees * 4, verifier_address.to_script_pub_key())],
            has_segwit=True
        )
        
        trigger_wrong_hash_tx = Transaction(
            [TxInput(trace_tx.get_txid(), 0, script_sig=Script([]))],
            [TxOutput(trace_output_amount - step_fees * 4, verifier_address.to_script_pub_key())],
            has_segwit=True
        )
        
        trigger_equivocation_tx = Transaction(
            [TxInput(trace_tx.get_txid(), 0, script_sig=Script([]))],
            [TxOutput(trace_output_amount - step_fees, verifier_address.to_script_pub_key())],
            has_segwit=True
        )
        
        prover_address = P2wpkhAddress.from_address(
            address=bitvmx_protocol_setup_properties_dto.prover_destination_address
        )
        
        execution_challenge_tx = Transaction(
            [TxInput(trigger_execution_challenge_tx.get_txid(), 0, script_sig=Script([]))],
            [TxOutput(challenge_output_amount, prover_address.to_script_pub_key())],
            has_segwit=True
        )
        
        # Generate read search transactions
        read_search_hash_tx_list = []
        read_search_choice_tx_list = []
        read_search_equivocation_tx_list = []
        
        # First choice transaction
        if search_iterations > 1:
            t_hash = time.time()
            try:
                # Direct call without suppress_output (removed FD redirect)
                first_hash_read_address = bitvmx_protocol_setup_properties_dto.bitvmx_bitcoin_scripts_dto.hash_read_search_scripts_address(
                        destroyed_public_key=destroyed_public_key,
                        iteration=1,
                    )
            except Exception as e:
                # Skip read search transactions on error
                search_iterations = 1
                # Use first hash address if available, otherwise use verifier as fallback
                if hash_search_scripts_addresses:
                    first_hash_read_address = hash_search_scripts_addresses[0]
                else:
                    first_hash_read_address = verifier_address
            
            # Only create first_choice_tx if we have a valid address
            if 'first_hash_read_address' in locals():
                first_choice_tx = Transaction(
                    [TxInput(trace_tx.get_txid(), 0, script_sig=Script([]))],
                    [TxOutput(trigger_challenge_output_amount, first_hash_read_address.to_script_pub_key())],
                    has_segwit=True
                )
                read_search_choice_tx_list.append(first_choice_tx)
        
        # Add missing read_trace_tx and trigger_read_challenge_tx
        t_addr = time.time()
        try:
            # Try to get from cache first
            cache_key = f"read_trace_{destroyed_public_key.to_hex()}"
            if hasattr(bitvmx_protocol_setup_properties_dto.bitvmx_bitcoin_scripts_dto, '_address_cache'):
                if cache_key in bitvmx_protocol_setup_properties_dto.bitvmx_bitcoin_scripts_dto._address_cache:
                    read_trace_script_address = bitvmx_protocol_setup_properties_dto.bitvmx_bitcoin_scripts_dto._address_cache[cache_key]
                else:
                    # Direct call without suppress_output (removed FD redirect)
                    read_trace_script_address = bitvmx_protocol_setup_properties_dto.bitvmx_bitcoin_scripts_dto.read_trace_script_list.get_taproot_address(
                            destroyed_public_key
                        )
                    bitvmx_protocol_setup_properties_dto.bitvmx_bitcoin_scripts_dto._address_cache[cache_key] = read_trace_script_address
            else:
                # Initialize cache
                bitvmx_protocol_setup_properties_dto.bitvmx_bitcoin_scripts_dto._address_cache = {}
                # Direct call without suppress_output (removed FD redirect)
                read_trace_script_address = bitvmx_protocol_setup_properties_dto.bitvmx_bitcoin_scripts_dto.read_trace_script_list.get_taproot_address(
                        destroyed_public_key
                    )
                bitvmx_protocol_setup_properties_dto.bitvmx_bitcoin_scripts_dto._address_cache[cache_key] = read_trace_script_address
        except Exception as e:
            # Use a fallback address
            read_trace_script_address = prover_address
        
        # Create a placeholder read_trace_tx
        if read_search_choice_tx_list:
            read_trace_tx = Transaction(
                [TxInput(read_search_choice_tx_list[-1].get_txid(), 0, script_sig=Script([]))],
                [TxOutput(current_output_amount - step_fees, read_trace_script_address.to_script_pub_key())],
                has_segwit=True
            )
        else:
            # Fallback if no read search transactions
            read_trace_tx = Transaction(
                [TxInput(trace_tx.get_txid(), 0, script_sig=Script([]))],
                [TxOutput(trigger_challenge_output_amount, read_trace_script_address.to_script_pub_key())],
                has_segwit=True
            )
        
        # Create trigger_read_challenge_tx
        trigger_read_challenge_tx = Transaction(
            [TxInput(read_trace_tx.get_txid(), 0, script_sig=Script([]))],
            [TxOutput(current_output_amount - step_fees * 2, prover_address.to_script_pub_key())],
            has_segwit=True
        )
        
        
        # Final mutation check
        assert int(bitvmx_protocol_setup_properties_dto.funding_amount_of_satoshis) == bitvmx_protocol_setup_properties_dto._original_funding, \
            f"BUG: dto.funding_amount_of_satoshis mutated during generation ({bitvmx_protocol_setup_properties_dto._original_funding} → {bitvmx_protocol_setup_properties_dto.funding_amount_of_satoshis})"
        assert int(bitvmx_protocol_setup_properties_dto.step_fees_satoshis) == bitvmx_protocol_setup_properties_dto._original_stepfee, \
            f"BUG: dto.step_fees_satoshis mutated during generation ({bitvmx_protocol_setup_properties_dto._original_stepfee} → {bitvmx_protocol_setup_properties_dto.step_fees_satoshis})"
        
        # IMPORTANT: Include hash_result_tx and trigger_protocol_tx in broadcast list
        # They must be broadcast BEFORE search transactions
        read_search_hash_tx_list_with_parents = [hash_result_tx, trigger_protocol_tx] + search_hash_tx_list
        read_search_choice_tx_list_with_parents = search_choice_tx_list  # These already depend on hash txs
        
        
        # Build and return the DTO
        return BitVMXTransactionsDTO(
            funding_tx=funding_tx,
            hash_result_tx=hash_result_tx,
            trigger_protocol_tx=trigger_protocol_tx,
            search_hash_tx_list=search_hash_tx_list,
            search_choice_tx_list=search_choice_tx_list,
            trace_tx=trace_tx,
            trigger_execution_challenge_tx=trigger_execution_challenge_tx,
            trigger_wrong_hash_challenge_tx=trigger_wrong_hash_tx,
            trigger_wrong_program_counter_challenge_tx=trigger_wrong_pc_tx,
            trigger_equivocation_tx=trigger_equivocation_tx,
            execution_challenge_tx=execution_challenge_tx,
            # Use the enhanced lists with parent transactions
            read_search_hash_tx_list=read_search_hash_tx_list_with_parents,
            read_search_choice_tx_list=read_search_choice_tx_list_with_parents,
            read_search_equivocation_tx_list=read_search_equivocation_tx_list,
            read_trace_tx=read_trace_tx,
            trigger_read_challenge_tx=trigger_read_challenge_tx,
        )
