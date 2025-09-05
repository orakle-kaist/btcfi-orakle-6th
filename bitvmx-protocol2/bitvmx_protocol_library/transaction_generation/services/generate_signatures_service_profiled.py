from bitcoinutils.constants import TAPROOT_SIGHASH_ALL
import time

from bitvmx_protocol_library.bitvmx_protocol_definition.entities.bitvmx_protocol_setup_properties_dto import (
    BitVMXProtocolSetupPropertiesDTO,
)
from bitvmx_protocol_library.transaction_generation.entities.dtos.bitvmx_signatures_dto import (
    BitVMXSignaturesDTO,
)


class GenerateSignaturesServiceProfiled:
    """Profiled version to identify actual bottlenecks"""

    def __init__(self, private_key, destroyed_public_key):
        self.private_key = private_key
        self.destroyed_public_key = destroyed_public_key
        self.timing_data = {}

    def _time_operation(self, name, func, *args, **kwargs):
        """Helper to time operations"""
        start = time.time()
        result = func(*args, **kwargs)
        elapsed = time.time() - start
        self.timing_data[name] = elapsed
        return result

    def __call__(
        self,
        bitvmx_protocol_setup_properties_dto: BitVMXProtocolSetupPropertiesDTO,
    ):
        from bitcoinutils.script import Script
        from blockchain_query_services.services.mutinynet_api.transaction_info_service import TransactionInfoService
        
        total_start = time.time()
        
        # Get funding transaction details from the blockchain
        funding_tx_id = bitvmx_protocol_setup_properties_dto.funding_tx_id
        funding_index = bitvmx_protocol_setup_properties_dto.funding_index
        
        print(f"[PROFILE] Starting signature generation...")
        
        # Time blockchain query
        query_start = time.time()
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
        
        self.timing_data['blockchain_query'] = time.time() - query_start
        
        # Count signatures to generate
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
        
        total_signatures = 5 + (num_iterations * 2)  # Base signatures + search iterations
        if bitvmx_protocol_setup_properties_dto.bitvmx_transactions_dto.read_search_hash_tx_list:
            read_iterations = len(bitvmx_protocol_setup_properties_dto.bitvmx_transactions_dto.search_hash_tx_list) - 1
            if read_iterations > 0:
                total_signatures += read_iterations * 2 + 1
        
        print(f"[PROFILE] Need to generate {total_signatures} signatures")
        print(f"[PROFILE]   - Base signatures: 5")
        print(f"[PROFILE]   - Search iterations: {num_iterations} x 2 = {num_iterations * 2}")
        if bitvmx_protocol_setup_properties_dto.bitvmx_transactions_dto.read_search_hash_tx_list:
            print(f"[PROFILE]   - Read search iterations: {read_iterations if read_iterations > 0 else 0} x 2")
        
        # Time individual signature generation
        sig_timings = []
        
        # Generate hash_result_signature
        sig_start = time.time()
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
        sig_timings.append(('hash_result', time.time() - sig_start))
        
        # Continue with other signatures (abbreviated for clarity)
        # The real implementation would time all signatures
        
        # Calculate statistics
        if sig_timings:
            avg_sig_time = sum(t[1] for t in sig_timings) / len(sig_timings)
            max_sig_time = max(t[1] for t in sig_timings)
            min_sig_time = min(t[1] for t in sig_timings)
            
            print(f"\n[PROFILE] Signature timing statistics:")
            print(f"  - Total signatures: {len(sig_timings)}")
            print(f"  - Average time per signature: {avg_sig_time:.4f} seconds")
            print(f"  - Min time: {min_sig_time:.4f} seconds")
            print(f"  - Max time: {max_sig_time:.4f} seconds")
            print(f"  - Total signature time: {sum(t[1] for t in sig_timings):.2f} seconds")
            
            # Show slowest signatures
            slowest = sorted(sig_timings, key=lambda x: x[1], reverse=True)[:5]
            print(f"\n[PROFILE] Slowest signatures:")
            for name, timing in slowest:
                print(f"  - {name}: {timing:.4f} seconds")
        
        total_time = time.time() - total_start
        print(f"\n[PROFILE] Total generation time: {total_time:.2f} seconds")
        print(f"[PROFILE] Theoretical parallel speedup (8 workers): ~{total_time/8:.2f} seconds")
        
        # Return dummy DTO for profiling
        return BitVMXSignaturesDTO(
            hash_result_signature=hash_result_signature,
            trigger_protocol_signature="",
            search_hash_signatures=[],
            search_choice_signatures=[],
            trace_signature="",
            trigger_execution_challenge_signature="",
            read_search_hash_signatures=[],
            read_search_choice_signatures=[],
            read_trace_signature="",
        )