from bitcoinutils.constants import TAPROOT_SIGHASH_ALL
from concurrent.futures import ThreadPoolExecutor, as_completed
import time

from bitvmx_protocol_library.bitvmx_protocol_definition.entities.bitvmx_protocol_setup_properties_dto import (
    BitVMXProtocolSetupPropertiesDTO,
)
from bitvmx_protocol_library.transaction_generation.entities.dtos.bitvmx_signatures_dto import (
    BitVMXSignaturesDTO,
)


class GenerateSignaturesServiceParallel:
    """Parallel version of GenerateSignaturesService that uses thread pool for signature generation"""

    def __init__(self, private_key, destroyed_public_key):
        self.private_key = private_key
        self.destroyed_public_key = destroyed_public_key

    def _sign_taproot(self, tx, input_index, prevout_scripts, prevout_amounts, tapleaf_script):
        """Helper method to sign a single taproot input"""
        return self.private_key.sign_taproot_input(
            tx,
            input_index,
            prevout_scripts,
            prevout_amounts,
            script_path=True,
            tapleaf_script=tapleaf_script,
            sighash=TAPROOT_SIGHASH_ALL,
            tweak=False,
        )

    def __call__(
        self,
        bitvmx_protocol_setup_properties_dto: BitVMXProtocolSetupPropertiesDTO,
    ):
        from bitcoinutils.script import Script
        from blockchain_query_services.services.mutinynet_api.transaction_info_service import TransactionInfoService
        
        start_time = time.time()
        print(f"[PARALLEL SIGN] Starting parallel signature generation...")
        
        # Get funding transaction details from the blockchain
        funding_tx_id = bitvmx_protocol_setup_properties_dto.funding_tx_id
        funding_index = bitvmx_protocol_setup_properties_dto.funding_index
        
        print(f"[PARALLEL SIGN] Getting chain prevout for funding_tx_id: {funding_tx_id}:{funding_index}")
        
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
            
            print(f"[PARALLEL SIGN] Using chain prevout script: {funding_output.scriptpubkey_hex}")
            print(f"[PARALLEL SIGN] Using chain prevout amount: {funding_prevout_amount} sats")
            
        except Exception as e:
            print(f"[PARALLEL SIGN] Failed to get chain prevout, falling back to DTO: {e}")
            # Fallback to DTO values if chain query fails
            funding_prevout_amount = bitvmx_protocol_setup_properties_dto.funding_amount_of_satoshis
            hash_result_script_address = bitvmx_protocol_setup_properties_dto.bitvmx_bitcoin_scripts_dto.hash_result_script.get_taproot_address(
                self.destroyed_public_key
            )
            funding_prevout_script = hash_result_script_address.to_script_pub_key()
            print(f"[PARALLEL SIGN] Fallback prevout script: {funding_prevout_script.to_hex()}")
            print(f"[PARALLEL SIGN] Fallback prevout amount: {funding_prevout_amount} sats")
        
        # Prepare all signature tasks
        signature_tasks = []
        
        # Task 1: hash_result_signature
        hash_result_script_address = bitvmx_protocol_setup_properties_dto.bitvmx_bitcoin_scripts_dto.hash_result_script.get_taproot_address(
            self.destroyed_public_key
        )
        signature_tasks.append({
            'name': 'hash_result_signature',
            'tx': bitvmx_protocol_setup_properties_dto.bitvmx_transactions_dto.hash_result_tx,
            'prevout_scripts': [funding_prevout_script],
            'prevout_amounts': [funding_prevout_amount],
            'tapleaf_script': bitvmx_protocol_setup_properties_dto.bitvmx_bitcoin_scripts_dto.hash_result_script,
        })
        
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
        
        signature_tasks.append({
            'name': 'trigger_protocol_signature',
            'tx': bitvmx_protocol_setup_properties_dto.bitvmx_transactions_dto.trigger_protocol_tx,
            'prevout_scripts': [trigger_prevout_script],
            'prevout_amounts': [trigger_protocol_input_amount],
            'tapleaf_script': trigger_protocol_script,
        })
        
        # Tasks 3-N: search_hash_signatures and search_choice_signatures
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
        
        for i in range(num_iterations):
            # Search hash signature
            current_search_hash_tx = search_hash_list[i]
            current_search_hash_script_address = bitvmx_protocol_setup_properties_dto.bitvmx_bitcoin_scripts_dto.hash_search_scripts_list(
                iteration=i
            ).get_taproot_address(
                public_key=self.destroyed_public_key
            )
            current_search_hash_script = bitvmx_protocol_setup_properties_dto.bitvmx_bitcoin_scripts_dto.hash_search_scripts_list(
                iteration=i
            )[
                bitvmx_protocol_setup_properties_dto.bitvmx_bitcoin_scripts_dto.hash_search_script_index()
            ]
            
            signature_tasks.append({
                'name': f'search_hash_{i}',
                'tx': current_search_hash_tx,
                'prevout_scripts': [current_search_hash_script_address.to_script_pub_key()],
                'prevout_amounts': [funding_prevout_amount - (2 * i + 2) * bitvmx_protocol_setup_properties_dto.step_fees_satoshis],
                'tapleaf_script': current_search_hash_script,
                'index': i,
                'type': 'search_hash'
            })
            
            # Search choice signature
            current_search_choice_tx = search_choice_list[i]
            current_search_choice_script_address = bitvmx_protocol_setup_properties_dto.bitvmx_bitcoin_scripts_dto.choice_search_scripts_list(
                iteration=i
            ).get_taproot_address(
                public_key=self.destroyed_public_key
            )
            current_search_choice_script = bitvmx_protocol_setup_properties_dto.bitvmx_bitcoin_scripts_dto.choice_search_scripts_list(
                iteration=i
            )[
                bitvmx_protocol_setup_properties_dto.bitvmx_bitcoin_scripts_dto.choice_search_script_index()
            ]
            
            signature_tasks.append({
                'name': f'search_choice_{i}',
                'tx': current_search_choice_tx,
                'prevout_scripts': [current_search_choice_script_address.to_script_pub_key()],
                'prevout_amounts': [funding_prevout_amount - (2 * i + 3) * bitvmx_protocol_setup_properties_dto.step_fees_satoshis],
                'tapleaf_script': current_search_choice_script,
                'index': i,
                'type': 'search_choice'
            })
        
        # Task: trace_signature
        trace_script_address = bitvmx_protocol_setup_properties_dto.bitvmx_bitcoin_scripts_dto.trace_script_list.get_taproot_address(
            self.destroyed_public_key
        )
        trace_script = (
            bitvmx_protocol_setup_properties_dto.bitvmx_bitcoin_scripts_dto.trace_script_list[
                bitvmx_protocol_setup_properties_dto.bitvmx_bitcoin_scripts_dto.trace_script_index()
            ]
        )
        
        signature_tasks.append({
            'name': 'trace_signature',
            'tx': bitvmx_protocol_setup_properties_dto.bitvmx_transactions_dto.trace_tx,
            'prevout_scripts': [trace_script_address.to_script_pub_key()],
            'prevout_amounts': [
                funding_prevout_amount
                - (2 * len(bitvmx_protocol_setup_properties_dto.bitvmx_transactions_dto.search_hash_tx_list) + 2)
                * bitvmx_protocol_setup_properties_dto.step_fees_satoshis
            ],
            'tapleaf_script': trace_script,
        })
        
        # Task: trigger_execution_challenge_signature
        trigger_trace_challenge_address = bitvmx_protocol_setup_properties_dto.bitvmx_bitcoin_scripts_dto.trigger_trace_challenge_address(
            self.destroyed_public_key
        )
        
        signature_tasks.append({
            'name': 'trigger_execution_challenge_signature',
            'tx': bitvmx_protocol_setup_properties_dto.bitvmx_transactions_dto.trigger_execution_challenge_tx,
            'prevout_scripts': [trigger_trace_challenge_address.to_script_pub_key()],
            'prevout_amounts': [
                funding_prevout_amount
                - (2 * len(bitvmx_protocol_setup_properties_dto.bitvmx_transactions_dto.search_hash_tx_list) + 3)
                * bitvmx_protocol_setup_properties_dto.step_fees_satoshis
            ],
            'tapleaf_script': bitvmx_protocol_setup_properties_dto.bitvmx_bitcoin_scripts_dto.trigger_challenge_scripts[0],
        })
        
        # Read search signatures
        if bitvmx_protocol_setup_properties_dto.bitvmx_transactions_dto.read_search_choice_tx_list:
            first_read_search_choice_tx = (
                bitvmx_protocol_setup_properties_dto.bitvmx_transactions_dto.read_search_choice_tx_list[0]
            )
            
            trigger_challenge_scripts_list = (
                bitvmx_protocol_setup_properties_dto.bitvmx_bitcoin_scripts_dto.trigger_trace_challenge_scripts_list
            )
            choice_read_search_index = (
                bitvmx_protocol_setup_properties_dto.bitvmx_bitcoin_scripts_dto.trigger_read_search_challenge_index()
            )
            
            signature_tasks.append({
                'name': 'first_read_search_choice',
                'tx': first_read_search_choice_tx,
                'prevout_scripts': [trigger_trace_challenge_address.to_script_pub_key()],
                'prevout_amounts': [
                    funding_prevout_amount
                    - (2 * len(bitvmx_protocol_setup_properties_dto.bitvmx_transactions_dto.search_hash_tx_list) + 3)
                    * bitvmx_protocol_setup_properties_dto.step_fees_satoshis
                ],
                'tapleaf_script': trigger_challenge_scripts_list[choice_read_search_index],
                'type': 'first_read_search_choice'
            })
        
        # Read search hash and choice iterations
        num_iterations = len(bitvmx_protocol_setup_properties_dto.bitvmx_transactions_dto.search_hash_tx_list) - 1
        if num_iterations > 0 and bitvmx_protocol_setup_properties_dto.bitvmx_transactions_dto.read_search_hash_tx_list:
            for i in range(num_iterations):
                # Read search hash
                current_read_search_hash_tx = bitvmx_protocol_setup_properties_dto.bitvmx_transactions_dto.read_search_hash_tx_list[i]
                current_read_search_hash_script_address = bitvmx_protocol_setup_properties_dto.bitvmx_bitcoin_scripts_dto.hash_read_search_scripts_list(
                    iteration=i
                ).get_taproot_address(
                    public_key=self.destroyed_public_key
                )
                
                signature_tasks.append({
                    'name': f'read_search_hash_{i}',
                    'tx': current_read_search_hash_tx,
                    'prevout_scripts': [current_read_search_hash_script_address.to_script_pub_key()],
                    'prevout_amounts': [
                        funding_prevout_amount
                        - (2 + 2 * len(bitvmx_protocol_setup_properties_dto.bitvmx_transactions_dto.search_hash_tx_list) + 2 + 2 * i)
                        * bitvmx_protocol_setup_properties_dto.step_fees_satoshis
                    ],
                    'tapleaf_script': bitvmx_protocol_setup_properties_dto.bitvmx_bitcoin_scripts_dto.hash_read_search_scripts_list(
                        iteration=i
                    )[
                        bitvmx_protocol_setup_properties_dto.bitvmx_bitcoin_scripts_dto.hash_read_search_script_index()
                    ],
                    'index': i,
                    'type': 'read_search_hash'
                })
                
                # Read search choice
                current_read_search_choice_tx = bitvmx_protocol_setup_properties_dto.bitvmx_transactions_dto.read_search_choice_tx_list[i + 1]
                current_read_search_choice_script_list = bitvmx_protocol_setup_properties_dto.bitvmx_bitcoin_scripts_dto.choice_read_search_script_list(
                    iteration=i + 1
                )
                current_read_search_choice_script_address = (
                    current_read_search_choice_script_list.get_taproot_address(
                        public_key=self.destroyed_public_key
                    )
                )
                current_read_search_choice_index = bitvmx_protocol_setup_properties_dto.bitvmx_bitcoin_scripts_dto.choice_read_search_script_index(
                    iteration=i + 1
                )
                current_read_search_choice_script = current_read_search_choice_script_list[
                    current_read_search_choice_index
                ]
                
                signature_tasks.append({
                    'name': f'read_search_choice_{i+1}',
                    'tx': current_read_search_choice_tx,
                    'prevout_scripts': [current_read_search_choice_script_address.to_script_pub_key()],
                    'prevout_amounts': [
                        funding_prevout_amount
                        - (2 + 2 * len(bitvmx_protocol_setup_properties_dto.bitvmx_transactions_dto.search_hash_tx_list) + 3 + 2 * i)
                        * bitvmx_protocol_setup_properties_dto.step_fees_satoshis
                    ],
                    'tapleaf_script': current_read_search_choice_script,
                    'index': i + 1,
                    'type': 'read_search_choice'
                })
        
        # Task: read_trace_signature
        read_trace_script_address = bitvmx_protocol_setup_properties_dto.bitvmx_bitcoin_scripts_dto.read_trace_script_list.get_taproot_address(
            public_key=self.destroyed_public_key
        )
        read_trace_index = (
            bitvmx_protocol_setup_properties_dto.bitvmx_bitcoin_scripts_dto.read_trace_script_index()
        )
        
        signature_tasks.append({
            'name': 'read_trace_signature',
            'tx': bitvmx_protocol_setup_properties_dto.bitvmx_transactions_dto.read_trace_tx,
            'prevout_scripts': [read_trace_script_address.to_script_pub_key()],
            'prevout_amounts': [
                funding_prevout_amount
                - (
                    2
                    + 2 * len(bitvmx_protocol_setup_properties_dto.bitvmx_transactions_dto.search_hash_tx_list)
                    + 2
                    + 2 * len(bitvmx_protocol_setup_properties_dto.bitvmx_transactions_dto.read_search_hash_tx_list)
                )
                * bitvmx_protocol_setup_properties_dto.step_fees_satoshis
            ],
            'tapleaf_script': bitvmx_protocol_setup_properties_dto.bitvmx_bitcoin_scripts_dto.read_trace_script_list[
                read_trace_index
            ],
        })
        
        # Execute all signatures in parallel
        print(f"[PARALLEL SIGN] Executing {len(signature_tasks)} signatures in parallel...")
        
        # Use optimal number of workers (not too many to avoid overhead)
        max_workers = min(8, len(signature_tasks))
        
        results = {}
        search_hash_signatures = [None] * num_iterations
        search_choice_signatures = [None] * num_iterations
        read_search_hash_signatures = []
        read_search_choice_signatures = []
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Submit all tasks
            future_to_task = {}
            for task in signature_tasks:
                future = executor.submit(
                    self._sign_taproot,
                    task['tx'],
                    0,
                    task['prevout_scripts'],
                    task['prevout_amounts'],
                    task['tapleaf_script']
                )
                future_to_task[future] = task
            
            # Collect results as they complete
            completed = 0
            for future in as_completed(future_to_task):
                task = future_to_task[future]
                try:
                    signature = future.result()
                    completed += 1
                    
                    # Store signature in appropriate place
                    if task['name'] == 'hash_result_signature':
                        hash_result_signature = signature
                    elif task['name'] == 'trigger_protocol_signature':
                        trigger_protocol_signature = signature
                    elif task['name'] == 'trace_signature':
                        trace_signature = signature
                    elif task['name'] == 'trigger_execution_challenge_signature':
                        trigger_execution_challenge_signature = signature
                    elif task['name'] == 'read_trace_signature':
                        read_trace_signature = signature
                    elif task['name'] == 'first_read_search_choice':
                        read_search_choice_signatures = [signature]
                    elif 'search_hash_' in task['name'] and task.get('type') == 'search_hash':
                        search_hash_signatures[task['index']] = signature
                    elif 'search_choice_' in task['name'] and task.get('type') == 'search_choice':
                        search_choice_signatures[task['index']] = signature
                    elif 'read_search_hash_' in task['name']:
                        if task['index'] >= len(read_search_hash_signatures):
                            read_search_hash_signatures.extend([None] * (task['index'] - len(read_search_hash_signatures) + 1))
                        read_search_hash_signatures[task['index']] = signature
                    elif 'read_search_choice_' in task['name'] and task['index'] > 0:
                        if task['index'] >= len(read_search_choice_signatures):
                            read_search_choice_signatures.extend([None] * (task['index'] - len(read_search_choice_signatures) + 1))
                        read_search_choice_signatures[task['index']] = signature
                    
                    if completed % 10 == 0:
                        print(f"[PARALLEL SIGN] Progress: {completed}/{len(signature_tasks)} signatures completed")
                        
                except Exception as e:
                    print(f"[PARALLEL SIGN] Error generating signature for {task['name']}: {e}")
                    raise
        
        # Clean up None values from lists
        search_hash_signatures = [s for s in search_hash_signatures if s is not None]
        search_choice_signatures = [s for s in search_choice_signatures if s is not None]
        read_search_hash_signatures = [s for s in read_search_hash_signatures if s is not None]
        read_search_choice_signatures = [s for s in read_search_choice_signatures if s is not None]
        
        elapsed = time.time() - start_time
        print(f"[PARALLEL SIGN] ✅ All signatures generated in {elapsed:.2f} seconds")
        
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