from typing import Dict, List
import requests

from bitcoinutils.transactions import Transaction, TxWitnessInput, TxInput

from bitvmx_protocol_library.bitvmx_execution.services.execution_trace_generation_service import (
    ExecutionTraceGenerationService,
)
from bitvmx_protocol_library.bitvmx_execution.services.execution_trace_query_service import (
    ExecutionTraceQueryService,
)
from bitvmx_protocol_library.bitvmx_protocol_definition.entities.bitvmx_protocol_prover_dto import (
    BitVMXProtocolProverDTO,
)
from bitvmx_protocol_library.bitvmx_protocol_definition.entities.bitvmx_protocol_setup_properties_dto import (
    BitVMXProtocolSetupPropertiesDTO,
)
from bitvmx_protocol_library.script_generation.services.script_generation.prover.hash_result_script_generator_service import (
    HashResultScriptGeneratorService,
)
from bitvmx_protocol_library.winternitz_keys_handling.services.generate_witness_from_input_nibbles_service import (
    GenerateWitnessFromInputNibblesService,
)
from blockchain_query_services.services.blockchain_query_services_dependency_injection import (
    broadcast_transaction_service,
)


def _to_digits_from_hex(hex_str: str, bits_per_digit: int) -> List[int]:
    hex_str = hex_str.lower()
    if bits_per_digit == 8:
        # group by bytes
        if len(hex_str) % 2 == 1:
            hex_str = '0' + hex_str
        return [int(hex_str[i:i+2], 16) for i in range(0, len(hex_str), 2)]
    # default nibble mode
    return [int(c, 16) for c in hex_str]

def _get_result_hash_value(last_step_trace: Dict, bits_per_digit: int) -> List[int]:
    hash_value = last_step_trace["step_hash"]
    print(hash_value)
    return _to_digits_from_hex(hash_value, bits_per_digit)


def _hex_to_witness(hex_str: str, length: int, bits_per_digit: int = 4) -> List[int]:
    digits = _to_digits_from_hex(hex_str, bits_per_digit)
    while len(digits) < length:
        digits.insert(0, 0)
    return digits


class PublishHashTransactionService:

    def __init__(self, prover_private_key):
        self.generate_witness_from_input_nibbles_service = GenerateWitnessFromInputNibblesService(
            prover_private_key
        )
        self.hash_result_script_generator = HashResultScriptGeneratorService()
        self.execution_trace_generation_service = ExecutionTraceGenerationService("prover_files/")
        self.execution_trace_query_service = ExecutionTraceQueryService("prover_files/")

    def __call__(
        self,
        setup_uuid: str,
        bitvmx_protocol_setup_properties_dto: BitVMXProtocolSetupPropertiesDTO,
        bitvmx_protocol_prover_dto: BitVMXProtocolProverDTO,
    ) -> Transaction:
        print(f"[DEBUG PublishHash] Starting PublishHashTransactionService")
        print(f"[DEBUG PublishHash] Setup UUID: {setup_uuid}")
        print(f"[DEBUG PublishHash] Input words: {bitvmx_protocol_setup_properties_dto.bitvmx_protocol_properties_dto.amount_of_input_words}")
        print(f"[DEBUG PublishHash] Input hex: {bitvmx_protocol_prover_dto.input_hex}")
        
        if (
            bitvmx_protocol_setup_properties_dto.bitvmx_protocol_properties_dto.amount_of_input_words
            > 0
            and bitvmx_protocol_prover_dto.input_hex is None
        ):
            raise Exception("Input should be set before publishing the hash result")

        hash_result_signatures = bitvmx_protocol_prover_dto.hash_result_signatures
        print(f"[DEBUG PublishHash] Hash result signatures count: {len(hash_result_signatures) if hash_result_signatures else 0}")

        print(f"[DEBUG PublishHash] Calling execution_trace_generation_service...")
        try:
            self.execution_trace_generation_service(
                setup_uuid=setup_uuid,
                input_hex=bitvmx_protocol_prover_dto.input_hex,
            )
            print(f"[DEBUG PublishHash] execution_trace_generation_service completed successfully")
        except Exception as e:
            print(f"[ERROR PublishHash] execution_trace_generation_service failed: {e}")
            print(f"[ERROR PublishHash] Exception type: {type(e).__name__}")
            import traceback
            print(f"[ERROR PublishHash] Traceback:\n{traceback.format_exc()}")
            raise
        print(f"[DEBUG PublishHash] Querying last step trace...")
        trace_index = bitvmx_protocol_setup_properties_dto.bitvmx_protocol_properties_dto.amount_of_trace_steps - 1
        print(f"[DEBUG PublishHash] Trace index: {trace_index}")
        
        try:
            last_step_trace = self.execution_trace_query_service(
                setup_uuid=setup_uuid,
                index=trace_index,
                input_hex=bitvmx_protocol_prover_dto.input_hex,
            )
            print(f"[DEBUG PublishHash] Last step trace retrieved: {last_step_trace}")
        except Exception as e:
            print(f"[ERROR PublishHash] execution_trace_query_service failed: {e}")
            import traceback
            print(f"[ERROR PublishHash] Traceback:\n{traceback.format_exc()}")
            raise
            
        bits_per_digit = bitvmx_protocol_setup_properties_dto.bitvmx_protocol_properties_dto.amount_of_bits_per_digit
        hash_result_split_number = _get_result_hash_value(last_step_trace, bits_per_digit)
        print(f"[DEBUG PublishHash] Hash result split: {hash_result_split_number[:10]}..." if len(hash_result_split_number) > 10 else f"{hash_result_split_number}")

        last_step = self.execution_trace_query_service.get_last_step(setup_uuid=setup_uuid)
        print(f"[DEBUG PublishHash] Last step: {last_step}")

        print(f"[DEBUG PublishHash] Generating hash result witness...")
        hash_result_witness = self.generate_witness_from_input_nibbles_service(
            step=1,
            case=0,
            input_numbers=hash_result_split_number,
            bits_per_digit_checksum=bitvmx_protocol_setup_properties_dto.bitvmx_protocol_properties_dto.amount_of_bits_per_digit_checksum,
            bits_per_digit_override=bits_per_digit,
        )
        print(f"[DEBUG PublishHash] Hash result witness length: {len(hash_result_witness)}")
        try:
            print(f"[DEBUG PublishHash] Hash witness head: {hash_result_witness[:8]}")
            print(f"[DEBUG PublishHash] Hash witness tail: {hash_result_witness[-8:]}")
        except Exception:
            pass

        print(f"[DEBUG PublishHash] Generating halt step witness...")
        halt_hex = hex(last_step - 1)[2:]
        print(f"[DEBUG PublishHash] Halt hex: {halt_hex}")
        # Provide halt digits in natural order; generator handles reversal internally
        halt_step_witness = self.generate_witness_from_input_nibbles_service(
            step=1,
            case=1,
            input_numbers=_hex_to_witness(
                hex_str=halt_hex,
                length=(bitvmx_protocol_setup_properties_dto.bitvmx_protocol_properties_dto.amount_of_nibbles_halt_step if bits_per_digit == 4 else bitvmx_protocol_setup_properties_dto.bitvmx_protocol_properties_dto.amount_of_bytes_halt_step),
                bits_per_digit=bits_per_digit,
            ),
            bits_per_digit_checksum=bitvmx_protocol_setup_properties_dto.bitvmx_protocol_properties_dto.amount_of_bits_per_digit_checksum,
            bits_per_digit_override=bits_per_digit,
        )
        print(f"[DEBUG PublishHash] Halt step witness length: {len(halt_step_witness)}")
        try:
            print(f"[DEBUG PublishHash] Halt witness head: {halt_step_witness[:8]}")
            print(f"[DEBUG PublishHash] Halt witness tail: {halt_step_witness[-8:]}")
        except Exception:
            pass

        if (
            bitvmx_protocol_setup_properties_dto.bitvmx_protocol_properties_dto.amount_of_input_words
            > 0
        ):
            print(f"[DEBUG PublishHash] Generating input witness for {bitvmx_protocol_setup_properties_dto.bitvmx_protocol_properties_dto.amount_of_input_words} words...")
            input_witness = []
            for i in range(
                bitvmx_protocol_setup_properties_dto.bitvmx_protocol_properties_dto.amount_of_input_words
            ):
                input_hex_slice = bitvmx_protocol_prover_dto.input_hex[i * 8 : (i + 1) * 8]
                print(f"[DEBUG PublishHash] Input word {i}: {input_hex_slice}")
                input_witness += self.generate_witness_from_input_nibbles_service(
                    step=1,
                    case=2 + i,
                    input_numbers=_hex_to_witness(
                        hex_str=input_hex_slice,
                        length=(8 if bits_per_digit == 4 else 4),
                        bits_per_digit=bits_per_digit,
                    ),
                    bits_per_digit_checksum=bitvmx_protocol_setup_properties_dto.bitvmx_protocol_properties_dto.amount_of_bits_per_digit_checksum,
                    bits_per_digit_override=bits_per_digit,
                )
            print(f"[DEBUG PublishHash] Total input witness length: {len(input_witness)}")
            try:
                print(f"[DEBUG PublishHash] Input witness head: {input_witness[:8]}")
                print(f"[DEBUG PublishHash] Input witness tail: {input_witness[-8:]}")
            except Exception:
                pass
        else:
            input_witness = []
            print(f"[DEBUG PublishHash] No input words, empty input witness")

        # Recreate script generator with correct base
        hash_gen = HashResultScriptGeneratorService(bits_per_digit=bits_per_digit)
        hash_result_script = hash_gen(
            signature_public_keys=bitvmx_protocol_setup_properties_dto.signature_public_keys,
            hash_result_public_keys=bitvmx_protocol_setup_properties_dto.bitvmx_prover_winternitz_public_keys_dto.hash_result_public_keys,
            halt_step_public_keys=bitvmx_protocol_setup_properties_dto.bitvmx_prover_winternitz_public_keys_dto.halt_step_public_keys,
            input_public_keys_list=bitvmx_protocol_setup_properties_dto.bitvmx_prover_winternitz_public_keys_dto.input_public_keys,
            n0=(bitvmx_protocol_setup_properties_dto.bitvmx_protocol_properties_dto.amount_of_nibbles_hash if bits_per_digit == 4 else bitvmx_protocol_setup_properties_dto.bitvmx_protocol_properties_dto.amount_of_nibbles_hash // 2),
            amount_of_nibbles_halt_step=(bitvmx_protocol_setup_properties_dto.bitvmx_protocol_properties_dto.amount_of_nibbles_halt_step if bits_per_digit == 4 else bitvmx_protocol_setup_properties_dto.bitvmx_protocol_properties_dto.amount_of_bytes_halt_step),
            bits_per_digit_checksum=bitvmx_protocol_setup_properties_dto.bitvmx_protocol_properties_dto.amount_of_bits_per_digit_checksum,
        )
        # Use library ControlBlock for single-leaf hash_result (align to internal encoding)
        hash_result_script_address = (
            bitvmx_protocol_setup_properties_dto.unspendable_public_key.get_taproot_address(
                [[hash_result_script]]
            )
        )
        hash_result_control_block = ControlBlock(
            bitvmx_protocol_setup_properties_dto.unspendable_public_key,
            scripts=[[hash_result_script]],
            index=0,
            is_odd=hash_result_script_address.is_odd(),
        )

        print(f"[DEBUG PublishHash] Building final witness stack...")
        print(f"[DEBUG PublishHash]   - Signatures: {len(hash_result_signatures) if hash_result_signatures else 0} items")
        print(f"[DEBUG PublishHash]   - Hash result witness: {len(hash_result_witness)} items")
        print(f"[DEBUG PublishHash]   - Halt step witness: {len(halt_step_witness)} items")
        print(f"[DEBUG PublishHash]   - Input witness: {len(input_witness)} items")
        print(f"[DEBUG PublishHash]   - Script + control block: 2 items")
        
        total_witness_items = (
            (len(hash_result_signatures) if hash_result_signatures else 0) +
            len(hash_result_witness) +
            len(halt_step_witness) +
            len(input_witness) +
            2  # script + control block
        )
        print(f"[DEBUG PublishHash] Total witness stack items: {total_witness_items}")
        
        # Order matters: script verifies inputs first, then halt, then hash_result, then checks signatures.
        # So signatures must come last among stack items (before script and control block).
        witness_items = (
            input_witness
            + halt_step_witness
            + hash_result_witness
            + hash_result_signatures
            + [
                hash_result_script.to_hex(),
                hash_result_control_block.to_hex(),
            ]
        )
        print(f"[DEBUG PublishHash] Witness ordering: inputs({len(input_witness)}), halt({len(halt_step_witness)}), hash({len(hash_result_witness)}), sigs({len(hash_result_signatures) if hash_result_signatures else 0})")
        bitvmx_protocol_setup_properties_dto.bitvmx_transactions_dto.hash_result_tx.witnesses.append(
            TxWitnessInput(witness_items)
        )

        tx_hex = bitvmx_protocol_setup_properties_dto.bitvmx_transactions_dto.hash_result_tx.serialize()
        
        broadcast_transaction_service(transaction=tx_hex)
        print(
            "Hash result revelation transaction: "
            + bitvmx_protocol_setup_properties_dto.bitvmx_transactions_dto.hash_result_tx.get_txid()
        )
        return bitvmx_protocol_setup_properties_dto.bitvmx_transactions_dto.hash_result_tx
