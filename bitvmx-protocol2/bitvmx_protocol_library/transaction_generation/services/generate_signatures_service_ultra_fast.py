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


class GenerateSignaturesServiceUltraFast:
    """Ultra-fast parallel signature generation using all available CPU cores"""

    def __init__(self, private_key, destroyed_public_key):
        self.private_key = private_key
        self.destroyed_public_key = destroyed_public_key
        # Use all available CPU cores (or at least 8)
        self.max_workers = max(8, os.cpu_count() or 8)

    def _sign_taproot_batch(self, tasks):
        """Sign multiple taproot inputs in parallel"""
        results = [None] * len(tasks)
        
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = {}
            for idx, (tx, scripts, amounts, tapleaf) in enumerate(tasks):
                future = executor.submit(
                    self.private_key.sign_taproot_input,
                    tx, 0, scripts, amounts,
                    script_path=True,
                    tapleaf_script=tapleaf,
                    sighash=TAPROOT_SIGHASH_ALL,
                    tweak=False
                )
                futures[future] = idx
            
            # Collect results
            for future in as_completed(futures):
                idx = futures[future]
                results[idx] = future.result()
        
        return results

    def __call__(
        self,
        bitvmx_protocol_setup_properties_dto: BitVMXProtocolSetupPropertiesDTO,
    ):
        from bitcoinutils.script import Script
        from blockchain_query_services.services.mutinynet_api.transaction_info_service import TransactionInfoService
        
        start_time = time.time()
        print(f"[ULTRA FAST] Starting ultra-fast signature generation with {self.max_workers} workers...")
        
        # Get funding transaction details
        funding_tx_id = bitvmx_protocol_setup_properties_dto.funding_tx_id
        funding_index = bitvmx_protocol_setup_properties_dto.funding_index
        
        # Query the actual funding UTXO from chain
        try:
            tx_info_service = TransactionInfoService()
            funding_tx_info = tx_info_service(tx_id=funding_tx_id)
            
            if funding_index >= len(funding_tx_info.outputs):
                raise ValueError(f"Funding index {funding_index} out of range for tx {funding_tx_id}")
            
            funding_output = funding_tx_info.outputs[funding_index]
            
            if not funding_output.scriptpubkey_hex:
                raise ValueError(f"No scriptpubkey_hex found for funding output {funding_tx_id}:{funding_index}")
            
            funding_prevout_script = Script.from_raw(funding_output.scriptpubkey_hex)
            funding_prevout_amount = funding_output.value
            
        except Exception as e:
            funding_prevout_amount = bitvmx_protocol_setup_properties_dto.funding_amount_of_satoshis
            hash_result_script_address = bitvmx_protocol_setup_properties_dto.bitvmx_bitcoin_scripts_dto.hash_result_script.get_taproot_address(
                self.destroyed_public_key
            )
            funding_prevout_script = hash_result_script_address.to_script_pub_key()
        
        # Prepare ALL signature tasks at once
        all_tasks = []
        task_names = []
        
        # Task 1: hash_result_signature
        hash_result_script_address = bitvmx_protocol_setup_properties_dto.bitvmx_bitcoin_scripts_dto.hash_result_script.get_taproot_address(
            self.destroyed_public_key
        )
        all_tasks.append((
            bitvmx_protocol_setup_properties_dto.bitvmx_transactions_dto.hash_result_tx,
            [funding_prevout_script],
            [funding_prevout_amount],
            bitvmx_protocol_setup_properties_dto.bitvmx_bitcoin_scripts_dto.hash_result_script
        ))
        task_names.append('hash_result')
        
        # Task 2: trigger_protocol_signature
        trigger_protocol_script_address = bitvmx_protocol_setup_properties_dto.bitvmx_bitcoin_scripts_dto.trigger_protocol_scripts_list.get_taproot_address(
            self.destroyed_public_key
        )
        trigger_protocol_script = bitvmx_protocol_setup_properties_dto.bitvmx_bitcoin_scripts_dto.trigger_protocol_scripts_list[
            bitvmx_protocol_setup_properties_dto.bitvmx_bitcoin_scripts_dto.trigger_protocol_index()
        ]
        
        hash_result_tx = bitvmx_protocol_setup_properties_dto.bitvmx_transactions_dto.hash_result_tx
        if hasattr(hash_result_tx, 'outputs') and len(hash_result_tx.outputs) > 0:
            trigger_protocol_input_amount = hash_result_tx.outputs[0].amount
            trigger_prevout_script = trigger_protocol_script_address.to_script_pub_key()
        else:
            trigger_protocol_input_amount = funding_prevout_amount - bitvmx_protocol_setup_properties_dto.step_fees_satoshis
            trigger_prevout_script = trigger_protocol_script_address.to_script_pub_key()
        
        all_tasks.append((
            bitvmx_protocol_setup_properties_dto.bitvmx_transactions_dto.trigger_protocol_tx,
            [trigger_prevout_script],
            [trigger_protocol_input_amount],
            trigger_protocol_script
        ))
        task_names.append('trigger_protocol')
        
        # Search signatures
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
        
        search_hash_indices = []
        search_choice_indices = []
        
        for i in range(num_iterations):
            # Search hash
            hash_script_address = bitvmx_protocol_setup_properties_dto.bitvmx_bitcoin_scripts_dto.hash_search_scripts_list(
                iteration=i
            ).get_taproot_address(public_key=self.destroyed_public_key)
            hash_script = bitvmx_protocol_setup_properties_dto.bitvmx_bitcoin_scripts_dto.hash_search_scripts_list(
                iteration=i
            )[bitvmx_protocol_setup_properties_dto.bitvmx_bitcoin_scripts_dto.hash_search_script_index()]
            
            all_tasks.append((
                search_hash_list[i],
                [hash_script_address.to_script_pub_key()],
                [funding_prevout_amount - (2 * i + 2) * bitvmx_protocol_setup_properties_dto.step_fees_satoshis],
                hash_script
            ))
            task_names.append(f'search_hash_{i}')
            search_hash_indices.append(len(all_tasks) - 1)
            
            # Search choice
            choice_script_address = bitvmx_protocol_setup_properties_dto.bitvmx_bitcoin_scripts_dto.choice_search_scripts_list(
                iteration=i
            ).get_taproot_address(public_key=self.destroyed_public_key)
            choice_script = bitvmx_protocol_setup_properties_dto.bitvmx_bitcoin_scripts_dto.choice_search_scripts_list(
                iteration=i
            )[bitvmx_protocol_setup_properties_dto.bitvmx_bitcoin_scripts_dto.choice_search_script_index()]
            
            all_tasks.append((
                search_choice_list[i],
                [choice_script_address.to_script_pub_key()],
                [funding_prevout_amount - (2 * i + 3) * bitvmx_protocol_setup_properties_dto.step_fees_satoshis],
                choice_script
            ))
            task_names.append(f'search_choice_{i}')
            search_choice_indices.append(len(all_tasks) - 1)
        
        # Trace signature
        trace_script_address = bitvmx_protocol_setup_properties_dto.bitvmx_bitcoin_scripts_dto.trace_script_list.get_taproot_address(
            self.destroyed_public_key
        )
        trace_script = bitvmx_protocol_setup_properties_dto.bitvmx_bitcoin_scripts_dto.trace_script_list[
            bitvmx_protocol_setup_properties_dto.bitvmx_bitcoin_scripts_dto.trace_script_index()
        ]
        
        all_tasks.append((
            bitvmx_protocol_setup_properties_dto.bitvmx_transactions_dto.trace_tx,
            [trace_script_address.to_script_pub_key()],
            [funding_prevout_amount - (2 * len(search_hash_list) + 2) * bitvmx_protocol_setup_properties_dto.step_fees_satoshis],
            trace_script
        ))
        task_names.append('trace')
        
        # Trigger execution challenge
        trigger_trace_challenge_address = bitvmx_protocol_setup_properties_dto.bitvmx_bitcoin_scripts_dto.trigger_trace_challenge_address(
            self.destroyed_public_key
        )
        
        all_tasks.append((
            bitvmx_protocol_setup_properties_dto.bitvmx_transactions_dto.trigger_execution_challenge_tx,
            [trigger_trace_challenge_address.to_script_pub_key()],
            [funding_prevout_amount - (2 * len(search_hash_list) + 3) * bitvmx_protocol_setup_properties_dto.step_fees_satoshis],
            bitvmx_protocol_setup_properties_dto.bitvmx_bitcoin_scripts_dto.trigger_challenge_scripts[0]
        ))
        task_names.append('trigger_execution_challenge')
        
        # Read search signatures
        read_search_choice_indices = []
        read_search_hash_indices = []
        
        if bitvmx_protocol_setup_properties_dto.bitvmx_transactions_dto.read_search_choice_tx_list:
            first_read_search_choice_tx = bitvmx_protocol_setup_properties_dto.bitvmx_transactions_dto.read_search_choice_tx_list[0]
            trigger_challenge_scripts_list = bitvmx_protocol_setup_properties_dto.bitvmx_bitcoin_scripts_dto.trigger_trace_challenge_scripts_list
            choice_read_search_index = bitvmx_protocol_setup_properties_dto.bitvmx_bitcoin_scripts_dto.trigger_read_search_challenge_index()
            
            all_tasks.append((
                first_read_search_choice_tx,
                [trigger_trace_challenge_address.to_script_pub_key()],
                [funding_prevout_amount - (2 * len(search_hash_list) + 3) * bitvmx_protocol_setup_properties_dto.step_fees_satoshis],
                trigger_challenge_scripts_list[choice_read_search_index]
            ))
            task_names.append('first_read_search_choice')
            read_search_choice_indices.append(len(all_tasks) - 1)
        
        # Read search iterations
        num_read_iterations = len(search_hash_list) - 1
        if num_read_iterations > 0 and bitvmx_protocol_setup_properties_dto.bitvmx_transactions_dto.read_search_hash_tx_list:
            for i in range(num_read_iterations):
                # Read search hash
                hash_script_address = bitvmx_protocol_setup_properties_dto.bitvmx_bitcoin_scripts_dto.hash_read_search_scripts_list(
                    iteration=i
                ).get_taproot_address(public_key=self.destroyed_public_key)
                
                all_tasks.append((
                    bitvmx_protocol_setup_properties_dto.bitvmx_transactions_dto.read_search_hash_tx_list[i],
                    [hash_script_address.to_script_pub_key()],
                    [funding_prevout_amount - (2 + 2 * len(search_hash_list) + 2 + 2 * i) * bitvmx_protocol_setup_properties_dto.step_fees_satoshis],
                    bitvmx_protocol_setup_properties_dto.bitvmx_bitcoin_scripts_dto.hash_read_search_scripts_list(iteration=i)[
                        bitvmx_protocol_setup_properties_dto.bitvmx_bitcoin_scripts_dto.hash_read_search_script_index()
                    ]
                ))
                task_names.append(f'read_search_hash_{i}')
                read_search_hash_indices.append(len(all_tasks) - 1)
                
                # Read search choice
                choice_script_list = bitvmx_protocol_setup_properties_dto.bitvmx_bitcoin_scripts_dto.choice_read_search_script_list(iteration=i + 1)
                choice_script_address = choice_script_list.get_taproot_address(public_key=self.destroyed_public_key)
                choice_index = bitvmx_protocol_setup_properties_dto.bitvmx_bitcoin_scripts_dto.choice_read_search_script_index(iteration=i + 1)
                
                all_tasks.append((
                    bitvmx_protocol_setup_properties_dto.bitvmx_transactions_dto.read_search_choice_tx_list[i + 1],
                    [choice_script_address.to_script_pub_key()],
                    [funding_prevout_amount - (2 + 2 * len(search_hash_list) + 3 + 2 * i) * bitvmx_protocol_setup_properties_dto.step_fees_satoshis],
                    choice_script_list[choice_index]
                ))
                task_names.append(f'read_search_choice_{i+1}')
                read_search_choice_indices.append(len(all_tasks) - 1)
        
        # Read trace
        read_trace_script_address = bitvmx_protocol_setup_properties_dto.bitvmx_bitcoin_scripts_dto.read_trace_script_list.get_taproot_address(
            public_key=self.destroyed_public_key
        )
        read_trace_index = bitvmx_protocol_setup_properties_dto.bitvmx_bitcoin_scripts_dto.read_trace_script_index()
        
        all_tasks.append((
            bitvmx_protocol_setup_properties_dto.bitvmx_transactions_dto.read_trace_tx,
            [read_trace_script_address.to_script_pub_key()],
            [funding_prevout_amount - (2 + 2 * len(search_hash_list) + 2 + 2 * len(bitvmx_protocol_setup_properties_dto.bitvmx_transactions_dto.read_search_hash_tx_list)) * bitvmx_protocol_setup_properties_dto.step_fees_satoshis],
            bitvmx_protocol_setup_properties_dto.bitvmx_bitcoin_scripts_dto.read_trace_script_list[read_trace_index]
        ))
        task_names.append('read_trace')
        
        # Execute ALL signatures in parallel
        print(f"[ULTRA FAST] Generating {len(all_tasks)} signatures in parallel...")
        batch_start = time.time()
        all_results = self._sign_taproot_batch(all_tasks)
        batch_time = time.time() - batch_start
        print(f"[ULTRA FAST] All signatures generated in {batch_time:.2f}s")
        
        # Map results back to correct variables
        result_map = dict(zip(task_names, all_results))
        
        # Extract individual signatures
        hash_result_signature = result_map['hash_result']
        trigger_protocol_signature = result_map.get('trigger_protocol', '')
        trace_signature = result_map.get('trace', '')
        trigger_execution_challenge_signature = result_map.get('trigger_execution_challenge', '')
        read_trace_signature = result_map.get('read_trace', '')
        
        # Extract search signatures
        search_hash_signatures = [result_map[f'search_hash_{i}'] for i in range(num_iterations)]
        search_choice_signatures = [result_map[f'search_choice_{i}'] for i in range(num_iterations)]
        
        # Extract read search signatures
        read_search_choice_signatures = []
        if 'first_read_search_choice' in result_map:
            read_search_choice_signatures.append(result_map['first_read_search_choice'])
        
        read_search_hash_signatures = []
        if num_read_iterations > 0 and bitvmx_protocol_setup_properties_dto.bitvmx_transactions_dto.read_search_hash_tx_list:
            read_search_hash_signatures = [result_map[f'read_search_hash_{i}'] for i in range(num_read_iterations)]
            for i in range(1, num_read_iterations + 1):
                if f'read_search_choice_{i}' in result_map:
                    read_search_choice_signatures.append(result_map[f'read_search_choice_{i}'])
        
        elapsed = time.time() - start_time
        print(f"[ULTRA FAST] ✅ Total time: {elapsed:.2f} seconds (batch signing: {batch_time:.2f}s)")
        
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