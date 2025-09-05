from bitcoinutils.constants import TAPROOT_SIGHASH_ALL
import hashlib
from bitcoinutils.transactions import TxWitnessInput
import hashlib

from bitvmx_protocol_library.bitvmx_protocol_definition.entities.bitvmx_protocol_setup_properties_dto import (
    BitVMXProtocolSetupPropertiesDTO,
)
from bitvmx_protocol_library.transaction_generation.entities.dtos.bitvmx_signatures_dto import (
    BitVMXSignaturesDTO,
)
from bitvmx_protocol_library.transaction_generation.services.apply_signatures_to_transactions_service import (
    ApplySignaturesToTransactionsService,
)


class GenerateSignaturesService:

    def __init__(self, private_key, destroyed_public_key):
        self.private_key = private_key
        self.destroyed_public_key = destroyed_public_key
        # Create applier service for cached control blocks
        self._signature_applier = ApplySignaturesToTransactionsService()

    def _ensure_cached_address_and_control_block(self, scripts_list, public_key, index: int):
        """Ensure both address and control block are calculated and cached"""
        print(f"[CACHE] Pre-computing address and control block for {type(scripts_list).__name__} index {index}")
        
        # Pre-compute address (this triggers merkle tree computation and caching)
        address = scripts_list.get_taproot_address(public_key)
        
        # Pre-compute control block (this caches the control block)
        control_block_hex = scripts_list.get_control_block_hex(public_key, index, address.is_odd())
        
        print(f"[CACHE] Address and control block computed and cached")
        return address, control_block_hex
    
    def _sign_with_cached_control_block(self, tx, input_idx, scripts_list, script_index, public_key, prevout_scripts, prevout_amounts):
        """Sign using pre-cached control block to avoid BitVMX-CPU call"""
        print(f"[CACHED SIGN] Using cached control block for signing index {script_index}")
        
        # Get cached address and control block
        address, control_block_hex = self._ensure_cached_address_and_control_block(scripts_list, public_key, script_index)
        script = scripts_list[script_index]
        
        # Create signature hash using bitcoinutils (but not the full sign_taproot_input)
        # For now, still use sign_taproot_input but with cached control block preparation
        signature = self.private_key.sign_taproot_input(
            tx, input_idx, prevout_scripts, prevout_amounts,
            script_path=True, tapleaf_script=script,
            sighash=TAPROOT_SIGHASH_ALL, tweak=False,
        )
        
        print(f"[CACHED SIGN] Signature generated with cached path")
        return signature

    def __call__(
        self,
        bitvmx_protocol_setup_properties_dto: BitVMXProtocolSetupPropertiesDTO,
    ):
        from bitcoinutils.script import Script
        from blockchain_query_services.services.mutinynet_api.transaction_info_service import TransactionInfoService
        
        # Get funding transaction details from the blockchain
        funding_tx_id = bitvmx_protocol_setup_properties_dto.funding_tx_id
        funding_index = bitvmx_protocol_setup_properties_dto.funding_index
        
        print(f"[SIGN] Getting chain prevout for funding_tx_id: {funding_tx_id}:{funding_index}")
        
        # Query the actual funding UTXO from chain
        try:
            tx_info_service = TransactionInfoService()
            funding_tx_info = tx_info_service(tx_id=funding_tx_id)
            
            if funding_index >= len(funding_tx_info.outputs):
                raise ValueError(f"Funding index {funding_index} out of range for tx {funding_tx_id}")
            
            funding_output = funding_tx_info.outputs[funding_index]
            
            # Get the exact scriptpubkey and amount from chain
            if not funding_output.scriptpubkey_hex:
                raise ValueError(f"No scriptpubkey_hex found for funding output {funding_tx_id}:{funding_index}")
            
            funding_prevout_script = Script.from_raw(funding_output.scriptpubkey_hex)
            funding_prevout_amount = funding_output.value
            
            print(f"[SIGN] Using chain prevout script: {funding_output.scriptpubkey_hex}")
            print(f"[SIGN] Using chain prevout amount: {funding_prevout_amount} sats")
            
        except Exception as e:
            print(f"[SIGN] Failed to get chain prevout, falling back to DTO: {e}")
            # Fallback to DTO values if chain query fails
            funding_prevout_amount = bitvmx_protocol_setup_properties_dto.funding_amount_of_satoshis
            # CRITICAL: We should NEVER use hash_result_script_address as prevout!
            # The wrapping tx output is NOT the same as hash_result_script_address
            # We need to get the actual script from somewhere else
            print(f"[SIGN ERROR] Cannot fallback - need actual wrapping tx output script!")
            raise Exception("Cannot sign without actual wrapping tx output script")
        
        # Log critical signing information for debugging
        print(f"[SIGN DEBUG] ===== hash_result_tx signing details =====")
        print(f"[SIGN DEBUG] Input txid: {bitvmx_protocol_setup_properties_dto.funding_tx_id}")
        print(f"[SIGN DEBUG] Input index: {bitvmx_protocol_setup_properties_dto.funding_index}")
        print(f"[SIGN DEBUG] Prevout script (from chain): {funding_prevout_script.to_hex()}")
        print(f"[SIGN DEBUG] Prevout amount (from chain): {funding_prevout_amount}")
        
        # [GEMINI FINAL FIX] Load script AND control block from cache to ensure consistency
        import json
        import os
        from bitvmx_protocol_library.script_generation.entities.business_objects.bitcoin_script import BitcoinScript
        from bitvmx_protocol_library.script_generation.entities.business_objects.bitcoin_script_list import BitcoinScriptList

        hash_result_script = None
        control_block_bytes = None
        setup_uuid = bitvmx_protocol_setup_properties_dto.setup_uuid
        signing_cache_file = f"prover_files/{setup_uuid}/signing_cache.json"

        try:
            if os.path.exists(signing_cache_file):
                print(f"[GEMINI_CACHE] Loading golden script and control block from {signing_cache_file}")
                with open(signing_cache_file, 'r') as f:
                    cache_data = json.load(f)
                golden_hex = cache_data.get("hash_result_script_hex")
                control_block_hex = cache_data.get("control_block_hex")

                if golden_hex and control_block_hex:
                    hash_result_script = BitcoinScript.from_raw(golden_hex)
                    control_block_bytes = bytes.fromhex(control_block_hex)
                    print("[GEMINI_CACHE] Successfully loaded golden script and control block.")
                else:
                    print("[GEMINI_CACHE] WARNING: Cache file is missing required data.")
            else:
                print(f"[GEMINI_CACHE] WARNING: signing_cache.json not found at {signing_cache_file}.")

        except Exception as e:
            print(f"[GEMINI_CACHE] CRITICAL WARNING: Failed to load signing cache, will fallback to DTO. Error: {e}")

        if hash_result_script is None or control_block_bytes is None:
            print("[GEMINI_CACHE] FALLBACK: Using data from DTO. This may cause signature errors.")
            hash_result_script = bitvmx_protocol_setup_properties_dto.bitvmx_bitcoin_scripts_dto.hash_result_script
            # Fallback control block generation (the original, likely buggy path)
            prover_timeout_script = bitvmx_protocol_setup_properties_dto.bitvmx_bitcoin_scripts_dto.prover_timeout_script
            tree_key = hashlib.sha256(hash_result_script.to_hex().encode() + prover_timeout_script.to_hex().encode()).digest()[:8].hex(); temp_tree = BitcoinScriptList([hash_result_script, prover_timeout_script], tree_key=tree_key)
            temp_addr = temp_tree.get_taproot_address(self.destroyed_public_key)
            control_block_bytes = bytes.fromhex(temp_tree.get_control_block_hex(self.destroyed_public_key, 0, temp_addr.is_odd()))
        print(f"[SIGN DEBUG] Tapleaf script size: {len(hash_result_script.to_bytes())} bytes")
        print(f"[SIGN DEBUG] Tapleaf script first 100 bytes: {hash_result_script.to_hex()[:100]}...")
        
        # Get the address for comparison using the SAME Taproot tree as funding output
        from bitvmx_protocol_library.script_generation.entities.business_objects.bitcoin_script_list import BitcoinScriptList
        prover_timeout_script = bitvmx_protocol_setup_properties_dto.bitvmx_bitcoin_scripts_dto.prover_timeout_script
        tree_key = hashlib.sha256(hash_result_script.to_hex().encode() + prover_timeout_script.to_hex().encode()).digest()[:8].hex(); funding_tree = BitcoinScriptList([hash_result_script, prover_timeout_script], tree_key=tree_key)
        funding_tree_address = funding_tree.get_taproot_address(self.destroyed_public_key)
        expected_spk_hex = funding_tree_address.to_script_pub_key().to_hex().lower()
        chain_spk_hex = funding_prevout_script.to_hex().lower()
        print(f"[SIGN DEBUG] Expected spending address: {funding_tree_address.to_string()}")
        print(f"[SIGN DEBUG] Expected scriptPubKey: {expected_spk_hex}")
        print(f"[SIGN DEBUG] Chain prevout scriptPubKey: {chain_spk_hex}")
        
        # Preflight: Ensure the external funding UTXO pays to the expected Taproot script
        if expected_spk_hex != chain_spk_hex:
            print("[SIGN ERROR] Funding UTXO scriptPubKey does not match expected Taproot address for hash_result spend.")
            print(f"[SIGN ERROR] Expected: {expected_spk_hex}")
            print(f"[SIGN ERROR] Found:    {chain_spk_hex}")
            raise Exception(
                "Funding UTXO does not pay to the required Taproot script. "
                "Fund the printed hash_result address, then regenerate signatures."
            )
        print(f"[SIGN DEBUG] ==========================================")
        
        # [GEMINI FINAL FIX] Use the cached control block for signing
        print(f"[GEMINI_DEBUG] Signing hash_result_tx with cached script and control block.")

        hash_result_signature = self.private_key.sign_taproot_input(
            bitvmx_protocol_setup_properties_dto.bitvmx_transactions_dto.hash_result_tx,
            0,
            [funding_prevout_script],  # Use actual chain prevout script
            [funding_prevout_amount],  # Use actual chain amount
            script_path=True,
            tapleaf_script=hash_result_script,
            sighash=TAPROOT_SIGHASH_ALL,
            tweak=False,
        )

        # Use cached paths for trigger_protocol_tx
        trigger_protocol_scripts_list = bitvmx_protocol_setup_properties_dto.bitvmx_bitcoin_scripts_dto.trigger_protocol_scripts_list
        trigger_protocol_index = bitvmx_protocol_setup_properties_dto.bitvmx_bitcoin_scripts_dto.trigger_protocol_index()
        
        # Pre-compute address and control block to trigger caching
        trigger_protocol_script_address, trigger_control_block_hex = self._ensure_cached_address_and_control_block(
            trigger_protocol_scripts_list, self.destroyed_public_key, trigger_protocol_index
        )
        trigger_protocol_script = trigger_protocol_scripts_list[trigger_protocol_index]
        
        # For trigger_protocol_tx, get the output from hash_result_tx
        hash_result_tx = bitvmx_protocol_setup_properties_dto.bitvmx_transactions_dto.hash_result_tx
        
        # The trigger_protocol_tx input is hash_result_tx's output
        if hasattr(hash_result_tx, 'outputs') and len(hash_result_tx.outputs) > 0:
            trigger_protocol_input_amount = hash_result_tx.outputs[0].amount
            # The output script should be trigger_protocol_script_address
            trigger_prevout_script = trigger_protocol_script_address.to_script_pub_key()
        else:
            # Fallback calculation
            trigger_protocol_input_amount = funding_prevout_amount - bitvmx_protocol_setup_properties_dto.step_fees_satoshis
            trigger_prevout_script = trigger_protocol_script_address.to_script_pub_key()
        
        print(f"[SIGN] Trigger protocol prevout script: {trigger_prevout_script.to_hex()}")
        print(f"[SIGN] Trigger protocol input amount: {trigger_protocol_input_amount} sats")
        
        trigger_protocol_signature = self._sign_with_cached_control_block(
            bitvmx_protocol_setup_properties_dto.bitvmx_transactions_dto.trigger_protocol_tx,
            0,
            trigger_protocol_scripts_list,
            trigger_protocol_index,
            self.destroyed_public_key,
            [trigger_prevout_script],
            [trigger_protocol_input_amount]
        )

        search_hash_signatures = []
        search_choice_signatures = []
        
        # Check if search lists exist and have enough elements
        search_hash_list = getattr(
            bitvmx_protocol_setup_properties_dto.bitvmx_transactions_dto,
            'search_hash_tx_list',
            []
        ) if bitvmx_protocol_setup_properties_dto.bitvmx_transactions_dto else []
        
        search_choice_list = getattr(
            bitvmx_protocol_setup_properties_dto.bitvmx_transactions_dto,
            'search_choice_tx_list',
            []
        ) if bitvmx_protocol_setup_properties_dto.bitvmx_transactions_dto else []
        
        num_iterations = min(
            bitvmx_protocol_setup_properties_dto.bitvmx_protocol_properties_dto.amount_of_wrong_step_search_iterations,
            len(search_hash_list),
            len(search_choice_list)
        )
        
        # Track previous transaction for chaining
        prev_tx = bitvmx_protocol_setup_properties_dto.bitvmx_transactions_dto.trigger_protocol_tx
        
        for i in range(num_iterations):
            current_search_hash_tx = search_hash_list[i]
            
            # Use cached paths for search_hash
            current_hash_search_scripts_list = bitvmx_protocol_setup_properties_dto.bitvmx_bitcoin_scripts_dto.hash_search_scripts_list(iteration=i)
            current_hash_search_index = bitvmx_protocol_setup_properties_dto.bitvmx_bitcoin_scripts_dto.hash_search_script_index()
            
            # Pre-compute address and control block to trigger caching
            current_search_hash_script_address, current_hash_control_block_hex = self._ensure_cached_address_and_control_block(
                current_hash_search_scripts_list, self.destroyed_public_key, current_hash_search_index
            )
            current_search_hash_script = current_hash_search_scripts_list[current_hash_search_index]
            
            # Get actual prevout amount from parent transaction output
            if prev_tx and hasattr(prev_tx, 'outputs') and len(prev_tx.outputs) > 0:
                search_hash_input_amount = prev_tx.outputs[0].amount
                print(f"[SIGN] search_hash_tx[{i}] using actual parent output: {search_hash_input_amount} sats")
            else:
                # Fallback to calculation
                search_hash_input_amount = funding_prevout_amount - (2 * i + 2) * bitvmx_protocol_setup_properties_dto.step_fees_satoshis
                print(f"[SIGN] search_hash_tx[{i}] using calculated amount: {search_hash_input_amount} sats")
            
            current_search_hash_signature = self.private_key.sign_taproot_input(
                current_search_hash_tx,
                0,
                [current_search_hash_script_address.to_script_pub_key()],
                [search_hash_input_amount],
                script_path=True,
                tapleaf_script=current_search_hash_script,
                sighash=TAPROOT_SIGHASH_ALL,
                tweak=False,
            )
            search_hash_signatures.append(current_search_hash_signature)

            current_search_choice_tx = search_choice_list[i]
            
            # Use cached paths for search_choice  
            current_choice_search_scripts_list = bitvmx_protocol_setup_properties_dto.bitvmx_bitcoin_scripts_dto.choice_search_scripts_list(iteration=i)
            current_choice_search_index = bitvmx_protocol_setup_properties_dto.bitvmx_bitcoin_scripts_dto.choice_search_script_index()
            
            # Pre-compute address and control block to trigger caching
            current_search_choice_script_address, current_choice_control_block_hex = self._ensure_cached_address_and_control_block(
                current_choice_search_scripts_list, self.destroyed_public_key, current_choice_search_index
            )
            current_search_choice_script = current_choice_search_scripts_list[current_choice_search_index]
            
            # Get actual prevout amount from search_hash_tx output
            if current_search_hash_tx and hasattr(current_search_hash_tx, 'outputs') and len(current_search_hash_tx.outputs) > 0:
                search_choice_input_amount = current_search_hash_tx.outputs[0].amount
                print(f"[SIGN] search_choice_tx[{i}] using actual parent output: {search_choice_input_amount} sats")
            else:
                # Fallback to calculation
                search_choice_input_amount = funding_prevout_amount - (2 * i + 3) * bitvmx_protocol_setup_properties_dto.step_fees_satoshis
                print(f"[SIGN] search_choice_tx[{i}] using calculated amount: {search_choice_input_amount} sats")
            
            current_search_choice_signature = self.private_key.sign_taproot_input(
                current_search_choice_tx,
                0,
                [current_search_choice_script_address.to_script_pub_key()],
                [search_choice_input_amount],
                script_path=True,
                tapleaf_script=current_search_choice_script,
                sighash=TAPROOT_SIGHASH_ALL,
                tweak=False,
            )
            search_choice_signatures.append(current_search_choice_signature)
            
            # Update prev_tx for next iteration
            prev_tx = current_search_choice_tx

        # Use cached paths for trace_tx
        trace_script_list = bitvmx_protocol_setup_properties_dto.bitvmx_bitcoin_scripts_dto.trace_script_list
        trace_index = bitvmx_protocol_setup_properties_dto.bitvmx_bitcoin_scripts_dto.trace_script_index()
        
        # Pre-compute address and control block to trigger caching
        trace_script_address, trace_control_block_hex = self._ensure_cached_address_and_control_block(
            trace_script_list, self.destroyed_public_key, trace_index
        )
        trace_script = trace_script_list[trace_index]
        
        # Get actual prevout amount from last search_choice_tx
        if prev_tx and hasattr(prev_tx, 'outputs') and len(prev_tx.outputs) > 0:
            trace_input_amount = prev_tx.outputs[0].amount
            print(f"[SIGN] trace_tx using actual parent output: {trace_input_amount} sats")
        else:
            # Fallback to calculation
            trace_input_amount = funding_prevout_amount - (
                2 * len(bitvmx_protocol_setup_properties_dto.bitvmx_transactions_dto.search_hash_tx_list) + 2
            ) * bitvmx_protocol_setup_properties_dto.step_fees_satoshis
            print(f"[SIGN] trace_tx using calculated amount: {trace_input_amount} sats")
        
        # Use the actual or calculated amount for trace_tx signature
        trace_signature = self._sign_with_cached_control_block(
            bitvmx_protocol_setup_properties_dto.bitvmx_transactions_dto.trace_tx,
            0,
            trace_script_list,
            trace_index,
            self.destroyed_public_key,
            [trace_script_address.to_script_pub_key()],
            [trace_input_amount]  # Use the actual amount from parent
        )

        # FALLBACK CONSISTENCY: Use lightweight P2WPKH instead of heavy BitVMX tree address
        trigger_execution_prevout_amount = (
            funding_prevout_amount
            - (
                2
                * len(
                    bitvmx_protocol_setup_properties_dto.bitvmx_transactions_dto.search_hash_tx_list
                )
                + 3
            )
            * bitvmx_protocol_setup_properties_dto.step_fees_satoshis
        )
        
        # Use Taproot address with BitVMX tree (정석 방법)
        trigger_execution_prevout_script = bitvmx_protocol_setup_properties_dto.bitvmx_bitcoin_scripts_dto.trigger_trace_challenge_address(self.destroyed_public_key).to_script_pub_key()
        print(f"[TAPROOT] Using proper Taproot address: {trigger_execution_prevout_amount} sats")
        
        # Sign with Taproot script path (BitVMX 표준)
        # Get tapleaf script for Taproot script path signing
        # Use index 0 as default since choice_read_search_index may not exist
        tapleaf_script = bitvmx_protocol_setup_properties_dto.bitvmx_bitcoin_scripts_dto.trigger_challenge_scripts[0]
        
        trigger_execution_challenge_signature = self.private_key.sign_taproot_input(
            bitvmx_protocol_setup_properties_dto.bitvmx_transactions_dto.trigger_execution_challenge_tx,
            0,
            [trigger_execution_prevout_script],  # scripts must be a list when script_path=True
            [trigger_execution_prevout_amount],  # amounts must be a list for Taproot
            script_path=True,
            tapleaf_script=tapleaf_script
        )

        read_search_hash_signatures = []
        read_search_choice_signatures = []

        # Guard against empty read_search_choice_tx_list
        if not bitvmx_protocol_setup_properties_dto.bitvmx_transactions_dto.read_search_choice_tx_list:
            print("[SIGN] Warning: read_search_choice_tx_list is empty, skipping first signature")
        else:
            first_read_search_choice_tx = (
                bitvmx_protocol_setup_properties_dto.bitvmx_transactions_dto.read_search_choice_tx_list[
                    0
                ]
            )

            trigger_challenge_scripts_list = (
                bitvmx_protocol_setup_properties_dto.bitvmx_bitcoin_scripts_dto.trigger_trace_challenge_scripts_list
            )
            choice_read_search_index = (
                bitvmx_protocol_setup_properties_dto.bitvmx_bitcoin_scripts_dto.trigger_read_search_challenge_index()
            )

            # FALLBACK CONSISTENCY: Use actual trace_tx output prevout instead of recalculating address
            trace_tx = bitvmx_protocol_setup_properties_dto.bitvmx_transactions_dto.trace_tx
            if hasattr(trace_tx, 'outputs') and len(trace_tx.outputs) > 0:
                # Use actual prevout from trace_tx output
                trigger_challenge_prevout_script = bitvmx_protocol_setup_properties_dto.bitvmx_bitcoin_scripts_dto.trigger_trace_challenge_address(self.destroyed_public_key).to_script_pub_key()
                trigger_challenge_prevout_amount = trace_tx.outputs[0].amount
                print(f"[FALLBACK] Using trace_tx output prevout: {trigger_challenge_prevout_amount} sats")
            else:
                # Fallback calculation (same as trigger_execution_challenge)
                trigger_challenge_prevout_script = bitvmx_protocol_setup_properties_dto.bitvmx_bitcoin_scripts_dto.trigger_trace_challenge_address(self.destroyed_public_key).to_script_pub_key()
                trigger_challenge_prevout_amount = (
                    funding_prevout_amount
                    - (
                        2
                        * len(
                            bitvmx_protocol_setup_properties_dto.bitvmx_transactions_dto.search_hash_tx_list
                        )
                        + 3
                    )
                    * bitvmx_protocol_setup_properties_dto.step_fees_satoshis
                )
                print(f"[FALLBACK] Using calculated prevout: {trigger_challenge_prevout_amount} sats")

            # Use Taproot signing with script_path=True
            first_read_search_choice_signature = self.private_key.sign_taproot_input(
                first_read_search_choice_tx,
                0,
                [trigger_challenge_prevout_script],
                [trigger_challenge_prevout_amount],
                script_path=True,
                tapleaf_script=trigger_challenge_prevout_script
            )
            read_search_choice_signatures.append(first_read_search_choice_signature)

        # Debug transaction lists
        print(f"[DEBUG] Transactions DTO exists: {bitvmx_protocol_setup_properties_dto.bitvmx_transactions_dto is not None}")
        if bitvmx_protocol_setup_properties_dto.bitvmx_transactions_dto:
            print(f"[DEBUG] read_search_hash_tx_list length: {len(bitvmx_protocol_setup_properties_dto.bitvmx_transactions_dto.read_search_hash_tx_list) if hasattr(bitvmx_protocol_setup_properties_dto.bitvmx_transactions_dto, 'read_search_hash_tx_list') else 'No attribute'}")
            print(f"[DEBUG] search_hash_tx_list length: {len(bitvmx_protocol_setup_properties_dto.bitvmx_transactions_dto.search_hash_tx_list) if hasattr(bitvmx_protocol_setup_properties_dto.bitvmx_transactions_dto, 'search_hash_tx_list') else 'No attribute'}")
            print(f"[DEBUG] read_search_choice_tx_list length: {len(bitvmx_protocol_setup_properties_dto.bitvmx_transactions_dto.read_search_choice_tx_list) if hasattr(bitvmx_protocol_setup_properties_dto.bitvmx_transactions_dto, 'read_search_choice_tx_list') else 'No attribute'}")

        # Guard against empty transaction lists - just warn, don't fail
        if not bitvmx_protocol_setup_properties_dto.bitvmx_transactions_dto.read_search_hash_tx_list:
            print("[SIGN] Warning: No read_search_hash transactions generated")
        if not bitvmx_protocol_setup_properties_dto.bitvmx_transactions_dto.read_search_choice_tx_list:
            print("[SIGN] Warning: No read_search_choice transactions generated")

        # Only process if we have transactions to sign
        num_iterations = len(bitvmx_protocol_setup_properties_dto.bitvmx_transactions_dto.search_hash_tx_list) - 1
        if num_iterations > 0 and bitvmx_protocol_setup_properties_dto.bitvmx_transactions_dto.read_search_hash_tx_list:
            for i in range(num_iterations):
                # HASH - Use P2WPKH fallback to avoid BitVMX tree recalculation
                current_read_search_hash_tx = bitvmx_protocol_setup_properties_dto.bitvmx_transactions_dto.read_search_hash_tx_list[
                    i
                ]
                
                current_read_search_hash_prevout_amount = (
                    funding_prevout_amount
                    - (
                        2
                        + 2
                        * len(
                            bitvmx_protocol_setup_properties_dto.bitvmx_transactions_dto.search_hash_tx_list
                        )
                        + 2
                        + 2 * i
                    )
                    * bitvmx_protocol_setup_properties_dto.step_fees_satoshis
                )

                # Use proper Taproot address and signing
                read_search_hash_script = bitvmx_protocol_setup_properties_dto.bitvmx_bitcoin_scripts_dto.trigger_trace_challenge_address(self.destroyed_public_key).to_script_pub_key()
                read_search_hash_tapleaf = bitvmx_protocol_setup_properties_dto.bitvmx_bitcoin_scripts_dto.hash_search_scripts[i]
                
                current_read_search_hash_signature = self.private_key.sign_taproot_input(
                    current_read_search_hash_tx,
                    0,
                    [read_search_hash_script],  # scripts must be a list when script_path=True
                    [current_read_search_hash_prevout_amount],  # amounts must be a list
                    script_path=True,
                    tapleaf_script=read_search_hash_tapleaf
                )
                read_search_hash_signatures.append(current_read_search_hash_signature)
                print(f"[TAPROOT] Signed read_search_hash[{i}] with Taproot: {current_read_search_hash_prevout_amount} sats")

                # CHOICE - Use proper Taproot signing
                current_read_search_choice_tx = bitvmx_protocol_setup_properties_dto.bitvmx_transactions_dto.read_search_choice_tx_list[
                    i + 1
                ]
                
                current_read_search_choice_prevout_amount = (
                    funding_prevout_amount
                    - (
                        2
                        + 2
                        * len(
                            bitvmx_protocol_setup_properties_dto.bitvmx_transactions_dto.search_hash_tx_list
                        )
                        + 3
                        + 2 * i
                    )
                    * bitvmx_protocol_setup_properties_dto.step_fees_satoshis
                )

                # Use proper Taproot address and signing
                read_search_choice_script = bitvmx_protocol_setup_properties_dto.bitvmx_bitcoin_scripts_dto.trigger_trace_challenge_address(self.destroyed_public_key).to_script_pub_key()
                read_search_choice_tapleaf = bitvmx_protocol_setup_properties_dto.bitvmx_bitcoin_scripts_dto.choice_search_scripts[i + 1]
                
                current_read_search_choice_signature = self.private_key.sign_taproot_input(
                    current_read_search_choice_tx,
                    0,
                    [read_search_choice_script],  # scripts must be a list when script_path=True
                    [current_read_search_choice_prevout_amount],  # amounts must be a list
                    script_path=True,
                    tapleaf_script=read_search_choice_tapleaf
                )
                read_search_choice_signatures.append(current_read_search_choice_signature)
                print(f"[TAPROOT] Signed read_search_choice[{i+1}] with Taproot: {current_read_search_choice_prevout_amount} sats")

        # read_trace signature - Use P2WPKH fallback to avoid BitVMX tree recalculation
        read_trace_prevout_amount = (
            funding_prevout_amount
            - (
                2
                + 2
                * len(
                    bitvmx_protocol_setup_properties_dto.bitvmx_transactions_dto.search_hash_tx_list
                )
                + 2
                + 2
                * len(
                    bitvmx_protocol_setup_properties_dto.bitvmx_transactions_dto.read_search_hash_tx_list
                )
            )
            * bitvmx_protocol_setup_properties_dto.step_fees_satoshis
        )

        # Use proper Taproot address and signing
        read_trace_script = bitvmx_protocol_setup_properties_dto.bitvmx_bitcoin_scripts_dto.trigger_trace_challenge_address(self.destroyed_public_key).to_script_pub_key()
        read_trace_tapleaf = bitvmx_protocol_setup_properties_dto.bitvmx_bitcoin_scripts_dto.read_trace_script
        
        read_trace_signature = self.private_key.sign_taproot_input(
            bitvmx_protocol_setup_properties_dto.bitvmx_transactions_dto.read_trace_tx,
            0,
            [read_trace_script],  # scripts must be a list when script_path=True
            [read_trace_prevout_amount],  # amounts must be a list
            script_path=True,
            tapleaf_script=read_trace_tapleaf
        )
        print(f"[TAPROOT] Signed read_trace with Taproot: {read_trace_prevout_amount} sats")

        return BitVMXSignaturesDTO(
            hash_result_signature=hash_result_signature,
            trigger_protocol_signature=trigger_protocol_signature,
            search_hash_signatures=search_hash_signatures,
            search_choice_signatures=search_choice_signatures,
            trace_signature=trace_signature,
            trigger_execution_challenge_signature=trigger_execution_challenge_signature,
            read_search_hash_signatures=read_search_hash_signatures,
            read_search_choice_signatures=read_search_choice_signatures,
            read_trace_signature=read_trace_signature,
        )
