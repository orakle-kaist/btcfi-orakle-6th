from bitcoinutils.constants import TAPROOT_SIGHASH_ALL
from concurrent.futures import ThreadPoolExecutor
import time

from bitvmx_protocol_library.bitvmx_protocol_definition.entities.bitvmx_protocol_setup_properties_dto import (
    BitVMXProtocolSetupPropertiesDTO,
)
from bitvmx_protocol_library.transaction_generation.entities.dtos.bitvmx_signatures_dto import (
    BitVMXSignaturesDTO,
)
from bitvmx_protocol_library.transaction_generation.services.generate_signatures_service import (
    GenerateSignaturesService,
)


class GenerateSignaturesServiceBatched(GenerateSignaturesService):
    """Batched parallel version - safer than full parallel, groups independent signatures"""

    def __init__(self, private_key, destroyed_public_key):
        super().__init__(private_key, destroyed_public_key)

    def _batch_sign_search_signatures(self, dto, funding_prevout_amount, num_iterations):
        """Generate search signatures in parallel batches"""
        search_hash_signatures = []
        search_choice_signatures = []
        
        search_hash_list = dto.bitvmx_transactions_dto.search_hash_tx_list
        search_choice_list = dto.bitvmx_transactions_dto.search_choice_tx_list
        
        # Process search signatures in batches
        with ThreadPoolExecutor(max_workers=4) as executor:
            # Prepare tasks
            hash_tasks = []
            choice_tasks = []
            
            for i in range(num_iterations):
                # Search hash task
                hash_tx = search_hash_list[i]
                hash_script_address = dto.bitvmx_bitcoin_scripts_dto.hash_search_scripts_list(
                    iteration=i
                ).get_taproot_address(public_key=self.destroyed_public_key)
                hash_script = dto.bitvmx_bitcoin_scripts_dto.hash_search_scripts_list(
                    iteration=i
                )[dto.bitvmx_bitcoin_scripts_dto.hash_search_script_index()]
                
                hash_tasks.append((
                    i,
                    hash_tx,
                    [hash_script_address.to_script_pub_key()],
                    [funding_prevout_amount - (2 * i + 2) * dto.step_fees_satoshis],
                    hash_script
                ))
                
                # Search choice task
                choice_tx = search_choice_list[i]
                choice_script_address = dto.bitvmx_bitcoin_scripts_dto.choice_search_scripts_list(
                    iteration=i
                ).get_taproot_address(public_key=self.destroyed_public_key)
                choice_script = dto.bitvmx_bitcoin_scripts_dto.choice_search_scripts_list(
                    iteration=i
                )[dto.bitvmx_bitcoin_scripts_dto.choice_search_script_index()]
                
                choice_tasks.append((
                    i,
                    choice_tx,
                    [choice_script_address.to_script_pub_key()],
                    [funding_prevout_amount - (2 * i + 3) * dto.step_fees_satoshis],
                    choice_script
                ))
            
            # Submit hash signatures
            hash_futures = []
            for i, tx, scripts, amounts, tapleaf in hash_tasks:
                future = executor.submit(
                    self.private_key.sign_taproot_input,
                    tx, 0, scripts, amounts,
                    script_path=True,
                    tapleaf_script=tapleaf,
                    sighash=TAPROOT_SIGHASH_ALL,
                    tweak=False
                )
                hash_futures.append((i, future))
            
            # Submit choice signatures
            choice_futures = []
            for i, tx, scripts, amounts, tapleaf in choice_tasks:
                future = executor.submit(
                    self.private_key.sign_taproot_input,
                    tx, 0, scripts, amounts,
                    script_path=True,
                    tapleaf_script=tapleaf,
                    sighash=TAPROOT_SIGHASH_ALL,
                    tweak=False
                )
                choice_futures.append((i, future))
            
            # Collect results IN ORDER
            hash_results = [None] * num_iterations
            for i, future in hash_futures:
                hash_results[i] = future.result()
            
            choice_results = [None] * num_iterations
            for i, future in choice_futures:
                choice_results[i] = future.result()
            
            search_hash_signatures = hash_results
            search_choice_signatures = choice_results
        
        return search_hash_signatures, search_choice_signatures

    def _batch_sign_read_search_signatures(self, dto, funding_prevout_amount, num_iterations):
        """Generate read search signatures in parallel batches"""
        read_search_hash_signatures = []
        read_search_choice_signatures = []
        
        if num_iterations <= 0 or not dto.bitvmx_transactions_dto.read_search_hash_tx_list:
            return [], []
        
        with ThreadPoolExecutor(max_workers=4) as executor:
            # Prepare tasks
            hash_tasks = []
            choice_tasks = []
            
            for i in range(num_iterations):
                # Read search hash
                hash_tx = dto.bitvmx_transactions_dto.read_search_hash_tx_list[i]
                hash_script_address = dto.bitvmx_bitcoin_scripts_dto.hash_read_search_scripts_list(
                    iteration=i
                ).get_taproot_address(public_key=self.destroyed_public_key)
                
                hash_tasks.append((
                    i,
                    hash_tx,
                    [hash_script_address.to_script_pub_key()],
                    [
                        funding_prevout_amount
                        - (2 + 2 * len(dto.bitvmx_transactions_dto.search_hash_tx_list) + 2 + 2 * i)
                        * dto.step_fees_satoshis
                    ],
                    dto.bitvmx_bitcoin_scripts_dto.hash_read_search_scripts_list(iteration=i)[
                        dto.bitvmx_bitcoin_scripts_dto.hash_read_search_script_index()
                    ]
                ))
                
                # Read search choice
                choice_tx = dto.bitvmx_transactions_dto.read_search_choice_tx_list[i + 1]
                choice_script_list = dto.bitvmx_bitcoin_scripts_dto.choice_read_search_script_list(
                    iteration=i + 1
                )
                choice_script_address = choice_script_list.get_taproot_address(
                    public_key=self.destroyed_public_key
                )
                choice_index = dto.bitvmx_bitcoin_scripts_dto.choice_read_search_script_index(
                    iteration=i + 1
                )
                choice_script = choice_script_list[choice_index]
                
                choice_tasks.append((
                    i,
                    choice_tx,
                    [choice_script_address.to_script_pub_key()],
                    [
                        funding_prevout_amount
                        - (2 + 2 * len(dto.bitvmx_transactions_dto.search_hash_tx_list) + 3 + 2 * i)
                        * dto.step_fees_satoshis
                    ],
                    choice_script
                ))
            
            # Submit all tasks
            hash_futures = []
            for i, tx, scripts, amounts, tapleaf in hash_tasks:
                future = executor.submit(
                    self.private_key.sign_taproot_input,
                    tx, 0, scripts, amounts,
                    script_path=True,
                    tapleaf_script=tapleaf,
                    sighash=TAPROOT_SIGHASH_ALL,
                    tweak=False
                )
                hash_futures.append((i, future))
            
            choice_futures = []
            for i, tx, scripts, amounts, tapleaf in choice_tasks:
                future = executor.submit(
                    self.private_key.sign_taproot_input,
                    tx, 0, scripts, amounts,
                    script_path=True,
                    tapleaf_script=tapleaf,
                    sighash=TAPROOT_SIGHASH_ALL,
                    tweak=False
                )
                choice_futures.append((i, future))
            
            # Collect results IN ORDER
            hash_results = [None] * num_iterations
            for i, future in hash_futures:
                hash_results[i] = future.result()
            
            choice_results = [None] * num_iterations
            for i, future in choice_futures:
                choice_results[i] = future.result()
            
            read_search_hash_signatures = hash_results
            read_search_choice_signatures = [None] + choice_results  # Index offset
        
        return read_search_hash_signatures, read_search_choice_signatures[1:]

    def __call__(
        self,
        bitvmx_protocol_setup_properties_dto: BitVMXProtocolSetupPropertiesDTO,
    ):
        from bitcoinutils.script import Script
        from blockchain_query_services.services.mutinynet_api.transaction_info_service import TransactionInfoService
        
        start_time = time.time()
        print(f"[BATCHED SIGN] Starting batched parallel signature generation...")
        
        # Get funding transaction details (same as parent)
        funding_tx_id = bitvmx_protocol_setup_properties_dto.funding_tx_id
        funding_index = bitvmx_protocol_setup_properties_dto.funding_index
        
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
        
        # Preflight: ensure external funding UTXO pays to expected Taproot script
        try:
            expected_spk_hex = bitvmx_protocol_setup_properties_dto.bitvmx_bitcoin_scripts_dto.hash_result_script.get_taproot_address(
                self.destroyed_public_key
            ).to_script_pub_key().to_hex().lower()
            chain_spk_hex = funding_prevout_script.to_hex().lower()
            if expected_spk_hex != chain_spk_hex:
                print("[BATCHED SIGN ERROR] Funding UTXO scriptPubKey does not match expected Taproot script.")
                print(f"[BATCHED SIGN ERROR] Expected: {expected_spk_hex}")
                print(f"[BATCHED SIGN ERROR] Found:    {chain_spk_hex}")
                raise Exception(
                    "Funding UTXO does not pay to the required Taproot script. "
                    "Fund the printed hash_result address and re-run setup/signing."
                )
        except Exception as e:
            # Surface the error early
            raise
        
        # Generate critical signatures sequentially (these must be correct)
        print("[BATCHED SIGN] Generating critical signatures sequentially...")
        
        # Hash result signature
        hash_result_script_address = bitvmx_protocol_setup_properties_dto.bitvmx_bitcoin_scripts_dto.hash_result_script.get_taproot_address(
            self.destroyed_public_key
        )
        hash_result_signature = self.private_key.sign_taproot_input(
            bitvmx_protocol_setup_properties_dto.bitvmx_transactions_dto.hash_result_tx,
            0,
            [funding_prevout_script],
            [funding_prevout_amount],
            script_path=True,
            tapleaf_script=bitvmx_protocol_setup_properties_dto.bitvmx_bitcoin_scripts_dto.hash_result_script,
            sighash=TAPROOT_SIGHASH_ALL,
            tweak=False,
        )
        
        # Trigger protocol signature
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
        
        trigger_protocol_signature = self.private_key.sign_taproot_input(
            bitvmx_protocol_setup_properties_dto.bitvmx_transactions_dto.trigger_protocol_tx,
            0,
            [trigger_prevout_script],
            [trigger_protocol_input_amount],
            script_path=True,
            tapleaf_script=trigger_protocol_script,
            sighash=TAPROOT_SIGHASH_ALL,
            tweak=False,
        )
        
        # Calculate iterations
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
        
        # Batch process search signatures
        print(f"[BATCHED SIGN] Processing {num_iterations} search iterations in parallel...")
        batch_start = time.time()
        search_hash_signatures, search_choice_signatures = self._batch_sign_search_signatures(
            bitvmx_protocol_setup_properties_dto,
            funding_prevout_amount,
            num_iterations
        )
        print(f"[BATCHED SIGN] Search signatures completed in {time.time() - batch_start:.2f}s")
        
        # Trace signature (sequential)
        trace_script_address = bitvmx_protocol_setup_properties_dto.bitvmx_bitcoin_scripts_dto.trace_script_list.get_taproot_address(
            self.destroyed_public_key
        )
        trace_script = (
            bitvmx_protocol_setup_properties_dto.bitvmx_bitcoin_scripts_dto.trace_script_list[
                bitvmx_protocol_setup_properties_dto.bitvmx_bitcoin_scripts_dto.trace_script_index()
            ]
        )
        trace_signature = self.private_key.sign_taproot_input(
            bitvmx_protocol_setup_properties_dto.bitvmx_transactions_dto.trace_tx,
            0,
            [trace_script_address.to_script_pub_key()],
            [
                funding_prevout_amount
                - (2 * len(bitvmx_protocol_setup_properties_dto.bitvmx_transactions_dto.search_hash_tx_list) + 2)
                * bitvmx_protocol_setup_properties_dto.step_fees_satoshis
            ],
            script_path=True,
            tapleaf_script=trace_script,
            sighash=TAPROOT_SIGHASH_ALL,
            tweak=False,
        )
        
        # Trigger execution challenge signature
        trigger_trace_challenge_address = bitvmx_protocol_setup_properties_dto.bitvmx_bitcoin_scripts_dto.trigger_trace_challenge_address(
            self.destroyed_public_key
        )
        trigger_execution_challenge_signature = self.private_key.sign_taproot_input(
            bitvmx_protocol_setup_properties_dto.bitvmx_transactions_dto.trigger_execution_challenge_tx,
            0,
            [trigger_trace_challenge_address.to_script_pub_key()],
            [
                funding_prevout_amount
                - (2 * len(bitvmx_protocol_setup_properties_dto.bitvmx_transactions_dto.search_hash_tx_list) + 3)
                * bitvmx_protocol_setup_properties_dto.step_fees_satoshis
            ],
            script_path=True,
            tapleaf_script=bitvmx_protocol_setup_properties_dto.bitvmx_bitcoin_scripts_dto.trigger_challenge_scripts[0],
            sighash=TAPROOT_SIGHASH_ALL,
            tweak=False,
        )
        
        # First read search choice signature
        read_search_choice_signatures = []
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
            
            first_read_search_choice_signature = self.private_key.sign_taproot_input(
                first_read_search_choice_tx,
                0,
                [trigger_trace_challenge_address.to_script_pub_key()],
                [
                    funding_prevout_amount
                    - (2 * len(bitvmx_protocol_setup_properties_dto.bitvmx_transactions_dto.search_hash_tx_list) + 3)
                    * bitvmx_protocol_setup_properties_dto.step_fees_satoshis
                ],
                script_path=True,
                tapleaf_script=trigger_challenge_scripts_list[choice_read_search_index],
                sighash=TAPROOT_SIGHASH_ALL,
                tweak=False,
            )
            read_search_choice_signatures.append(first_read_search_choice_signature)
        
        # Batch process read search signatures
        num_read_iterations = len(bitvmx_protocol_setup_properties_dto.bitvmx_transactions_dto.search_hash_tx_list) - 1
        if num_read_iterations > 0 and bitvmx_protocol_setup_properties_dto.bitvmx_transactions_dto.read_search_hash_tx_list:
            print(f"[BATCHED SIGN] Processing {num_read_iterations} read search iterations in parallel...")
            batch_start = time.time()
            read_search_hash_signatures, additional_read_choice_sigs = self._batch_sign_read_search_signatures(
                bitvmx_protocol_setup_properties_dto,
                funding_prevout_amount,
                num_read_iterations
            )
            read_search_choice_signatures.extend(additional_read_choice_sigs)
            print(f"[BATCHED SIGN] Read search signatures completed in {time.time() - batch_start:.2f}s")
        else:
            read_search_hash_signatures = []
        
        # Read trace signature
        read_trace_script_address = bitvmx_protocol_setup_properties_dto.bitvmx_bitcoin_scripts_dto.read_trace_script_list.get_taproot_address(
            public_key=self.destroyed_public_key
        )
        read_trace_index = (
            bitvmx_protocol_setup_properties_dto.bitvmx_bitcoin_scripts_dto.read_trace_script_index()
        )
        
        read_trace_signature = self.private_key.sign_taproot_input(
            bitvmx_protocol_setup_properties_dto.bitvmx_transactions_dto.read_trace_tx,
            0,
            [read_trace_script_address.to_script_pub_key()],
            [
                funding_prevout_amount
                - (
                    2
                    + 2 * len(bitvmx_protocol_setup_properties_dto.bitvmx_transactions_dto.search_hash_tx_list)
                    + 2
                    + 2 * len(bitvmx_protocol_setup_properties_dto.bitvmx_transactions_dto.read_search_hash_tx_list)
                )
                * bitvmx_protocol_setup_properties_dto.step_fees_satoshis
            ],
            script_path=True,
            tapleaf_script=bitvmx_protocol_setup_properties_dto.bitvmx_bitcoin_scripts_dto.read_trace_script_list[
                read_trace_index
            ],
            sighash=TAPROOT_SIGHASH_ALL,
            tweak=False,
        )
        
        elapsed = time.time() - start_time
        print(f"[BATCHED SIGN] ✅ All signatures generated in {elapsed:.2f} seconds")
        
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
