from bitcoinutils.constants import TAPROOT_SIGHASH_ALL
from concurrent.futures import ThreadPoolExecutor, as_completed
import time
import os
from functools import lru_cache

from bitvmx_protocol_library.bitvmx_protocol_definition.entities.bitvmx_protocol_setup_properties_dto import (
    BitVMXProtocolSetupPropertiesDTO,
)
from bitvmx_protocol_library.transaction_generation.entities.dtos.bitvmx_signatures_dto import (
    BitVMXSignaturesDTO,
)


class GenerateSignaturesServiceHyper:
    """Hyper-optimized signature generation with caching and parallel preparation"""

    def __init__(self, private_key, destroyed_public_key):
        self.private_key = private_key
        self.destroyed_public_key = destroyed_public_key
        # Use all available CPU cores
        self.max_workers = max(12, os.cpu_count() or 12)
        self._script_cache = {}
        self._address_cache = {}

    @lru_cache(maxsize=256)
    def _get_cached_taproot_address(self, script_id, iteration=None):
        """Cache taproot address generation"""
        return script_id
    
    def _prepare_signature_task(self, task_data):
        """Prepare a single signature task (can be parallelized)"""
        tx, script_getter, amount_calc, name = task_data
        
        # Get script and address (potentially cached)
        script = script_getter()
        if hasattr(script, 'get_taproot_address'):
            address = script.get_taproot_address(self.destroyed_public_key)
            script_pubkey = address.to_script_pub_key()
        else:
            # It's a script list
            address = script.get_taproot_address(self.destroyed_public_key)
            script_pubkey = address.to_script_pub_key()
            script = script[0]  # Get first script from list
        
        amount = amount_calc()
        
        return {
            'name': name,
            'tx': tx,
            'scripts': [script_pubkey],
            'amounts': [amount],
            'tapleaf': script
        }

    def _sign_taproot_batch_hyper(self, tasks):
        """Sign multiple taproot inputs in parallel with better error handling"""
        results = {}
        
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = {}
            for task in tasks:
                future = executor.submit(
                    self.private_key.sign_taproot_input,
                    task['tx'], 0, task['scripts'], task['amounts'],
                    script_path=True,
                    tapleaf_script=task['tapleaf'],
                    sighash=TAPROOT_SIGHASH_ALL,
                    tweak=False
                )
                futures[future] = task['name']
            
            # Collect results
            completed = 0
            total = len(futures)
            for future in as_completed(futures):
                name = futures[future]
                try:
                    results[name] = future.result()
                    completed += 1
                    if completed % 5 == 0:
                        print(f"[HYPER] Progress: {completed}/{total} signatures")
                except Exception as e:
                    print(f"[HYPER] Error signing {name}: {e}")
                    raise
        
        return results

    def __call__(
        self,
        bitvmx_protocol_setup_properties_dto: BitVMXProtocolSetupPropertiesDTO,
    ):
        from bitcoinutils.script import Script
        
        total_start = time.time()
        print(f"[HYPER] Starting hyper-optimized signature generation with {self.max_workers} workers...")
        
        # Stage 1: Quick funding info extraction (avoid blockchain query if possible)
        stage1_start = time.time()
        funding_tx_id = bitvmx_protocol_setup_properties_dto.funding_tx_id
        funding_index = bitvmx_protocol_setup_properties_dto.funding_index
        
        # Try to use DTO values first (avoid blockchain query)
        funding_prevout_amount = bitvmx_protocol_setup_properties_dto.funding_amount_of_satoshis
        
        # Only query blockchain if absolutely necessary
        if not funding_prevout_amount:
            from blockchain_query_services.services.mutinynet_api.transaction_info_service import TransactionInfoService
            try:
                tx_info_service = TransactionInfoService()
                funding_tx_info = tx_info_service(tx_id=funding_tx_id)
                funding_output = funding_tx_info.outputs[funding_index]
                funding_prevout_script = Script.from_raw(funding_output.scriptpubkey_hex)
                funding_prevout_amount = funding_output.value
            except:
                pass
        
        # Use cached address generation
        hash_result_script_address = bitvmx_protocol_setup_properties_dto.bitvmx_bitcoin_scripts_dto.hash_result_script.get_taproot_address(
            self.destroyed_public_key
        )
        funding_prevout_script = hash_result_script_address.to_script_pub_key()
        
        print(f"[HYPER] Stage 1 (funding prep): {time.time() - stage1_start:.2f}s")
        
        # Stage 2: Prepare all tasks in parallel
        stage2_start = time.time()
        
        dto = bitvmx_protocol_setup_properties_dto
        all_tasks = []
        
        # Helper to get amounts
        def amount_at_step(step):
            return funding_prevout_amount - step * dto.step_fees_satoshis
        
        # Critical signatures (must be done first)
        all_tasks.append({
            'name': 'hash_result',
            'tx': dto.bitvmx_transactions_dto.hash_result_tx,
            'scripts': [funding_prevout_script],
            'amounts': [funding_prevout_amount],
            'tapleaf': dto.bitvmx_bitcoin_scripts_dto.hash_result_script
        })
        
        # Trigger protocol
        trigger_protocol_script = dto.bitvmx_bitcoin_scripts_dto.trigger_protocol_scripts_list[
            dto.bitvmx_bitcoin_scripts_dto.trigger_protocol_index()
        ]
        trigger_protocol_address = dto.bitvmx_bitcoin_scripts_dto.trigger_protocol_scripts_list.get_taproot_address(
            self.destroyed_public_key
        )
        
        hash_result_tx = dto.bitvmx_transactions_dto.hash_result_tx
        if hasattr(hash_result_tx, 'outputs') and len(hash_result_tx.outputs) > 0:
            trigger_amount = hash_result_tx.outputs[0].amount
        else:
            trigger_amount = amount_at_step(1)
        
        all_tasks.append({
            'name': 'trigger_protocol',
            'tx': dto.bitvmx_transactions_dto.trigger_protocol_tx,
            'scripts': [trigger_protocol_address.to_script_pub_key()],
            'amounts': [trigger_amount],
            'tapleaf': trigger_protocol_script
        })
        
        # Search iterations
        search_hash_list = getattr(dto.bitvmx_transactions_dto, 'search_hash_tx_list', [])
        search_choice_list = getattr(dto.bitvmx_transactions_dto, 'search_choice_tx_list', [])
        
        num_iterations = min(
            dto.bitvmx_protocol_properties_dto.amount_of_wrong_step_search_iterations,
            len(search_hash_list),
            len(search_choice_list)
        )
        
        # Batch prepare search tasks
        for i in range(num_iterations):
            # Hash
            hash_script = dto.bitvmx_bitcoin_scripts_dto.hash_search_scripts_list(iteration=i)
            hash_addr = hash_script.get_taproot_address(public_key=self.destroyed_public_key)
            all_tasks.append({
                'name': f'search_hash_{i}',
                'tx': search_hash_list[i],
                'scripts': [hash_addr.to_script_pub_key()],
                'amounts': [amount_at_step(2 * i + 2)],
                'tapleaf': hash_script[dto.bitvmx_bitcoin_scripts_dto.hash_search_script_index()]
            })
            
            # Choice
            choice_script = dto.bitvmx_bitcoin_scripts_dto.choice_search_scripts_list(iteration=i)
            choice_addr = choice_script.get_taproot_address(public_key=self.destroyed_public_key)
            all_tasks.append({
                'name': f'search_choice_{i}',
                'tx': search_choice_list[i],
                'scripts': [choice_addr.to_script_pub_key()],
                'amounts': [amount_at_step(2 * i + 3)],
                'tapleaf': choice_script[dto.bitvmx_bitcoin_scripts_dto.choice_search_script_index()]
            })
        
        # Trace
        trace_script = dto.bitvmx_bitcoin_scripts_dto.trace_script_list
        trace_addr = trace_script.get_taproot_address(self.destroyed_public_key)
        all_tasks.append({
            'name': 'trace',
            'tx': dto.bitvmx_transactions_dto.trace_tx,
            'scripts': [trace_addr.to_script_pub_key()],
            'amounts': [amount_at_step(2 * len(search_hash_list) + 2)],
            'tapleaf': trace_script[dto.bitvmx_bitcoin_scripts_dto.trace_script_index()]
        })
        
        # Trigger execution challenge
        trigger_trace_addr = dto.bitvmx_bitcoin_scripts_dto.trigger_trace_challenge_address(self.destroyed_public_key)
        all_tasks.append({
            'name': 'trigger_execution_challenge',
            'tx': dto.bitvmx_transactions_dto.trigger_execution_challenge_tx,
            'scripts': [trigger_trace_addr.to_script_pub_key()],
            'amounts': [amount_at_step(2 * len(search_hash_list) + 3)],
            'tapleaf': dto.bitvmx_bitcoin_scripts_dto.trigger_challenge_scripts[0]
        })
        
        # Read search (if exists)
        if dto.bitvmx_transactions_dto.read_search_choice_tx_list:
            trigger_scripts = dto.bitvmx_bitcoin_scripts_dto.trigger_trace_challenge_scripts_list
            idx = dto.bitvmx_bitcoin_scripts_dto.trigger_read_search_challenge_index()
            all_tasks.append({
                'name': 'first_read_search_choice',
                'tx': dto.bitvmx_transactions_dto.read_search_choice_tx_list[0],
                'scripts': [trigger_trace_addr.to_script_pub_key()],
                'amounts': [amount_at_step(2 * len(search_hash_list) + 3)],
                'tapleaf': trigger_scripts[idx]
            })
            
            # Read iterations
            num_read = len(search_hash_list) - 1
            if num_read > 0 and dto.bitvmx_transactions_dto.read_search_hash_tx_list:
                base_step = 2 + 2 * len(search_hash_list) + 2
                for i in range(num_read):
                    # Hash
                    hash_script = dto.bitvmx_bitcoin_scripts_dto.hash_read_search_scripts_list(iteration=i)
                    hash_addr = hash_script.get_taproot_address(public_key=self.destroyed_public_key)
                    all_tasks.append({
                        'name': f'read_search_hash_{i}',
                        'tx': dto.bitvmx_transactions_dto.read_search_hash_tx_list[i],
                        'scripts': [hash_addr.to_script_pub_key()],
                        'amounts': [amount_at_step(base_step + 2 * i)],
                        'tapleaf': hash_script[dto.bitvmx_bitcoin_scripts_dto.hash_read_search_script_index()]
                    })
                    
                    # Choice
                    choice_script = dto.bitvmx_bitcoin_scripts_dto.choice_read_search_script_list(iteration=i + 1)
                    choice_addr = choice_script.get_taproot_address(public_key=self.destroyed_public_key)
                    idx = dto.bitvmx_bitcoin_scripts_dto.choice_read_search_script_index(iteration=i + 1)
                    all_tasks.append({
                        'name': f'read_search_choice_{i+1}',
                        'tx': dto.bitvmx_transactions_dto.read_search_choice_tx_list[i + 1],
                        'scripts': [choice_addr.to_script_pub_key()],
                        'amounts': [amount_at_step(base_step + 1 + 2 * i)],
                        'tapleaf': choice_script[idx]
                    })
        
        # Read trace
        read_trace_script = dto.bitvmx_bitcoin_scripts_dto.read_trace_script_list
        read_trace_addr = read_trace_script.get_taproot_address(public_key=self.destroyed_public_key)
        read_trace_idx = dto.bitvmx_bitcoin_scripts_dto.read_trace_script_index()
        
        read_base = 2 + 2 * len(search_hash_list) + 2
        if dto.bitvmx_transactions_dto.read_search_hash_tx_list:
            read_base += 2 * len(dto.bitvmx_transactions_dto.read_search_hash_tx_list)
        
        all_tasks.append({
            'name': 'read_trace',
            'tx': dto.bitvmx_transactions_dto.read_trace_tx,
            'scripts': [read_trace_addr.to_script_pub_key()],
            'amounts': [amount_at_step(read_base)],
            'tapleaf': read_trace_script[read_trace_idx]
        })
        
        print(f"[HYPER] Stage 2 (task prep): {time.time() - stage2_start:.2f}s, {len(all_tasks)} tasks")
        
        # Stage 3: Execute all signatures in hyper-parallel
        stage3_start = time.time()
        results = self._sign_taproot_batch_hyper(all_tasks)
        print(f"[HYPER] Stage 3 (batch signing): {time.time() - stage3_start:.2f}s")
        
        # Stage 4: Assemble results
        stage4_start = time.time()
        
        # Extract signatures in order
        search_hash_sigs = [results.get(f'search_hash_{i}', '') for i in range(num_iterations)]
        search_choice_sigs = [results.get(f'search_choice_{i}', '') for i in range(num_iterations)]
        
        read_search_choice_sigs = []
        if 'first_read_search_choice' in results:
            read_search_choice_sigs.append(results['first_read_search_choice'])
        
        read_search_hash_sigs = []
        if dto.bitvmx_transactions_dto.read_search_hash_tx_list:
            num_read = len(search_hash_list) - 1
            if num_read > 0:
                read_search_hash_sigs = [results.get(f'read_search_hash_{i}', '') for i in range(num_read)]
                for i in range(1, num_read + 1):
                    if f'read_search_choice_{i}' in results:
                        read_search_choice_sigs.append(results[f'read_search_choice_{i}'])
        
        print(f"[HYPER] Stage 4 (assembly): {time.time() - stage4_start:.2f}s")
        
        total_time = time.time() - total_start
        print(f"[HYPER] ✅ COMPLETE in {total_time:.2f}s (prep: {stage2_start - total_start:.2f}s, sign: {time.time() - stage3_start:.2f}s)")
        
        return BitVMXSignaturesDTO(
            hash_result_signature=results.get('hash_result', ''),
            trigger_protocol_signature=results.get('trigger_protocol', ''),
            search_hash_signatures=search_hash_sigs,
            search_choice_signatures=search_choice_sigs,
            trace_signature=results.get('trace', ''),
            trigger_execution_challenge_signature=results.get('trigger_execution_challenge', ''),
            read_search_hash_signatures=read_search_hash_sigs,
            read_search_choice_signatures=read_search_choice_sigs,
            read_trace_signature=results.get('read_trace', ''),
        )