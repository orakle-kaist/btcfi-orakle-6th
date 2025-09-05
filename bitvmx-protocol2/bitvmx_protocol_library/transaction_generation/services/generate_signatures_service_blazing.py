from bitcoinutils.constants import TAPROOT_SIGHASH_ALL
from concurrent.futures import ThreadPoolExecutor, as_completed
import time
import os

from bitvmx_protocol_library.bitvmx_protocol_definition.entities.bitvmx_protocol_setup_properties_dto import (
    BitVMXProtocolSetupPropertiesDTO,
)
from bitvmx_protocol_library.transaction_generation.entities.dtos.bitvmx_signatures_dto import (
    BitVMXSignaturesDTO,
)


class GenerateSignaturesServiceBlazing:
    """Blazing fast signature generation - addresses the script generation bottleneck"""

    def __init__(self, private_key, destroyed_public_key):
        self.private_key = private_key
        self.destroyed_public_key = destroyed_public_key
        self.max_workers = max(16, os.cpu_count() or 16)

    def _parallel_prepare_addresses(self, dto):
        """Prepare all addresses in parallel to avoid sequential bottleneck"""
        address_tasks = []
        
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # Submit all address generation tasks
            futures = {}
            
            # Hash result
            futures['hash_result'] = executor.submit(
                lambda: dto.bitvmx_bitcoin_scripts_dto.hash_result_script.get_taproot_address(self.destroyed_public_key)
            )
            
            # Trigger protocol
            futures['trigger_protocol'] = executor.submit(
                lambda: dto.bitvmx_bitcoin_scripts_dto.trigger_protocol_scripts_list.get_taproot_address(self.destroyed_public_key)
            )
            
            # Search iterations
            search_hash_list = getattr(dto.bitvmx_transactions_dto, 'search_hash_tx_list', [])
            search_choice_list = getattr(dto.bitvmx_transactions_dto, 'search_choice_tx_list', [])
            
            num_iterations = min(
                dto.bitvmx_protocol_properties_dto.amount_of_wrong_step_search_iterations,
                len(search_hash_list),
                len(search_choice_list)
            )
            
            for i in range(num_iterations):
                futures[f'search_hash_{i}'] = executor.submit(
                    lambda idx=i: dto.bitvmx_bitcoin_scripts_dto.hash_search_scripts_list(iteration=idx).get_taproot_address(self.destroyed_public_key)
                )
                futures[f'search_choice_{i}'] = executor.submit(
                    lambda idx=i: dto.bitvmx_bitcoin_scripts_dto.choice_search_scripts_list(iteration=idx).get_taproot_address(self.destroyed_public_key)
                )
            
            # Trace
            futures['trace'] = executor.submit(
                lambda: dto.bitvmx_bitcoin_scripts_dto.trace_script_list.get_taproot_address(self.destroyed_public_key)
            )
            
            # Trigger trace challenge
            futures['trigger_trace'] = executor.submit(
                lambda: dto.bitvmx_bitcoin_scripts_dto.trigger_trace_challenge_address(self.destroyed_public_key)
            )
            
            # Read search
            if dto.bitvmx_transactions_dto.read_search_hash_tx_list:
                num_read = len(search_hash_list) - 1
                if num_read > 0:
                    for i in range(num_read):
                        futures[f'read_hash_{i}'] = executor.submit(
                            lambda idx=i: dto.bitvmx_bitcoin_scripts_dto.hash_read_search_scripts_list(iteration=idx).get_taproot_address(self.destroyed_public_key)
                        )
                        futures[f'read_choice_{i+1}'] = executor.submit(
                            lambda idx=i: dto.bitvmx_bitcoin_scripts_dto.choice_read_search_script_list(iteration=idx+1).get_taproot_address(self.destroyed_public_key)
                        )
            
            # Read trace
            futures['read_trace'] = executor.submit(
                lambda: dto.bitvmx_bitcoin_scripts_dto.read_trace_script_list.get_taproot_address(self.destroyed_public_key)
            )
            
            # Collect all addresses
            addresses = {}
            for name, future in futures.items():
                try:
                    addresses[name] = future.result()
                except Exception as e:
                    print(f"[BLAZING] Error generating address for {name}: {e}")
                    raise
        
        return addresses

    def __call__(
        self,
        bitvmx_protocol_setup_properties_dto: BitVMXProtocolSetupPropertiesDTO,
    ):
        from bitcoinutils.script import Script
        
        total_start = time.time()
        print(f"[BLAZING] Starting blazing fast signature generation with {self.max_workers} workers...")
        
        dto = bitvmx_protocol_setup_properties_dto
        
        # Stage 1: Get funding info quickly
        stage1_start = time.time()
        funding_prevout_amount = dto.funding_amount_of_satoshis
        
        # Use cached/quick address for funding
        hash_result_script_address = dto.bitvmx_bitcoin_scripts_dto.hash_result_script.get_taproot_address(
            self.destroyed_public_key
        )
        funding_prevout_script = hash_result_script_address.to_script_pub_key()
        
        print(f"[BLAZING] Stage 1 (funding): {time.time() - stage1_start:.2f}s")
        
        # Stage 2: Generate ALL addresses in parallel
        stage2_start = time.time()
        print(f"[BLAZING] Generating all addresses in parallel...")
        addresses = self._parallel_prepare_addresses(dto)
        print(f"[BLAZING] Stage 2 (parallel address gen): {time.time() - stage2_start:.2f}s")
        
        # Stage 3: Prepare signature tasks using pre-generated addresses
        stage3_start = time.time()
        
        all_tasks = []
        
        # Helper for amounts
        def amount_at_step(step):
            return funding_prevout_amount - step * dto.step_fees_satoshis
        
        # Hash result
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
        
        hash_result_tx = dto.bitvmx_transactions_dto.hash_result_tx
        if hasattr(hash_result_tx, 'outputs') and len(hash_result_tx.outputs) > 0:
            trigger_amount = hash_result_tx.outputs[0].amount
        else:
            trigger_amount = amount_at_step(1)
        
        all_tasks.append({
            'name': 'trigger_protocol',
            'tx': dto.bitvmx_transactions_dto.trigger_protocol_tx,
            'scripts': [addresses['trigger_protocol'].to_script_pub_key()],
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
        
        for i in range(num_iterations):
            # Hash
            all_tasks.append({
                'name': f'search_hash_{i}',
                'tx': search_hash_list[i],
                'scripts': [addresses[f'search_hash_{i}'].to_script_pub_key()],
                'amounts': [amount_at_step(2 * i + 2)],
                'tapleaf': dto.bitvmx_bitcoin_scripts_dto.hash_search_scripts_list(iteration=i)[
                    dto.bitvmx_bitcoin_scripts_dto.hash_search_script_index()
                ]
            })
            
            # Choice
            all_tasks.append({
                'name': f'search_choice_{i}',
                'tx': search_choice_list[i],
                'scripts': [addresses[f'search_choice_{i}'].to_script_pub_key()],
                'amounts': [amount_at_step(2 * i + 3)],
                'tapleaf': dto.bitvmx_bitcoin_scripts_dto.choice_search_scripts_list(iteration=i)[
                    dto.bitvmx_bitcoin_scripts_dto.choice_search_script_index()
                ]
            })
        
        # Trace
        all_tasks.append({
            'name': 'trace',
            'tx': dto.bitvmx_transactions_dto.trace_tx,
            'scripts': [addresses['trace'].to_script_pub_key()],
            'amounts': [amount_at_step(2 * len(search_hash_list) + 2)],
            'tapleaf': dto.bitvmx_bitcoin_scripts_dto.trace_script_list[
                dto.bitvmx_bitcoin_scripts_dto.trace_script_index()
            ]
        })
        
        # Trigger execution challenge
        all_tasks.append({
            'name': 'trigger_execution_challenge',
            'tx': dto.bitvmx_transactions_dto.trigger_execution_challenge_tx,
            'scripts': [addresses['trigger_trace'].to_script_pub_key()],
            'amounts': [amount_at_step(2 * len(search_hash_list) + 3)],
            'tapleaf': dto.bitvmx_bitcoin_scripts_dto.trigger_challenge_scripts[0]
        })
        
        # Read search
        if dto.bitvmx_transactions_dto.read_search_choice_tx_list:
            trigger_scripts = dto.bitvmx_bitcoin_scripts_dto.trigger_trace_challenge_scripts_list
            idx = dto.bitvmx_bitcoin_scripts_dto.trigger_read_search_challenge_index()
            all_tasks.append({
                'name': 'first_read_search_choice',
                'tx': dto.bitvmx_transactions_dto.read_search_choice_tx_list[0],
                'scripts': [addresses['trigger_trace'].to_script_pub_key()],
                'amounts': [amount_at_step(2 * len(search_hash_list) + 3)],
                'tapleaf': trigger_scripts[idx]
            })
            
            # Read iterations
            num_read = len(search_hash_list) - 1
            if num_read > 0 and dto.bitvmx_transactions_dto.read_search_hash_tx_list:
                base_step = 2 + 2 * len(search_hash_list) + 2
                for i in range(num_read):
                    # Hash
                    all_tasks.append({
                        'name': f'read_search_hash_{i}',
                        'tx': dto.bitvmx_transactions_dto.read_search_hash_tx_list[i],
                        'scripts': [addresses[f'read_hash_{i}'].to_script_pub_key()],
                        'amounts': [amount_at_step(base_step + 2 * i)],
                        'tapleaf': dto.bitvmx_bitcoin_scripts_dto.hash_read_search_scripts_list(iteration=i)[
                            dto.bitvmx_bitcoin_scripts_dto.hash_read_search_script_index()
                        ]
                    })
                    
                    # Choice
                    choice_script = dto.bitvmx_bitcoin_scripts_dto.choice_read_search_script_list(iteration=i + 1)
                    idx = dto.bitvmx_bitcoin_scripts_dto.choice_read_search_script_index(iteration=i + 1)
                    all_tasks.append({
                        'name': f'read_search_choice_{i+1}',
                        'tx': dto.bitvmx_transactions_dto.read_search_choice_tx_list[i + 1],
                        'scripts': [addresses[f'read_choice_{i+1}'].to_script_pub_key()],
                        'amounts': [amount_at_step(base_step + 1 + 2 * i)],
                        'tapleaf': choice_script[idx]
                    })
        
        # Read trace
        read_trace_idx = dto.bitvmx_bitcoin_scripts_dto.read_trace_script_index()
        read_base = 2 + 2 * len(search_hash_list) + 2
        if dto.bitvmx_transactions_dto.read_search_hash_tx_list:
            read_base += 2 * len(dto.bitvmx_transactions_dto.read_search_hash_tx_list)
        
        all_tasks.append({
            'name': 'read_trace',
            'tx': dto.bitvmx_transactions_dto.read_trace_tx,
            'scripts': [addresses['read_trace'].to_script_pub_key()],
            'amounts': [amount_at_step(read_base)],
            'tapleaf': dto.bitvmx_bitcoin_scripts_dto.read_trace_script_list[read_trace_idx]
        })
        
        print(f"[BLAZING] Stage 3 (task assembly): {time.time() - stage3_start:.2f}s")
        
        # Stage 4: Sign everything in parallel
        stage4_start = time.time()
        print(f"[BLAZING] Signing {len(all_tasks)} signatures in parallel...")
        
        results = {}
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = {}
            for task in all_tasks:
                future = executor.submit(
                    self.private_key.sign_taproot_input,
                    task['tx'], 0, task['scripts'], task['amounts'],
                    script_path=True,
                    tapleaf_script=task['tapleaf'],
                    sighash=TAPROOT_SIGHASH_ALL,
                    tweak=False
                )
                futures[future] = task['name']
            
            completed = 0
            for future in as_completed(futures):
                name = futures[future]
                results[name] = future.result()
                completed += 1
                if completed % 5 == 0:
                    print(f"[BLAZING] Signed {completed}/{len(all_tasks)}")
        
        print(f"[BLAZING] Stage 4 (parallel signing): {time.time() - stage4_start:.2f}s")
        
        # Stage 5: Assemble final DTO
        stage5_start = time.time()
        
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
        
        print(f"[BLAZING] Stage 5 (final assembly): {time.time() - stage5_start:.2f}s")
        
        total_time = time.time() - total_start
        print(f"[BLAZING] ✅ COMPLETE in {total_time:.2f}s")
        print(f"[BLAZING] Breakdown: address gen={time.time() - stage2_start - (time.time() - stage3_start) - (time.time() - stage4_start) - (time.time() - stage5_start):.2f}s, signing={time.time() - stage4_start - (time.time() - stage5_start):.2f}s")
        
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