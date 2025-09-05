from typing import Dict, List

from bitcoinutils.transactions import Transaction, TxWitnessInput

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


def _get_result_hash_value(last_step_trace: Dict) -> List[int]:
    hash_value = last_step_trace["step_hash"]
    print(f"[HASH_RESULT] Last step hash value: {hash_value}")
    hash_result_split_number = []
    for letter in hash_value:
        hash_result_split_number.append(int(letter, 16))
    return hash_result_split_number


def _hex_to_witness(hex_str: str, length: int) -> List[int]:
    int_array = list(map(lambda x: int(x, 16), hex_str))
    while len(int_array) < length:
        int_array.insert(0, 0)
    return int_array


class PublishHashTransactionServiceNoBroadcast:
    """
    Same as PublishHashTransactionService but without broadcasting.
    Returns the transaction with complete witness stack.
    """

    def __init__(self, prover_private_key):
        self.generate_witness_from_input_nibbles_service = GenerateWitnessFromInputNibblesService(
            prover_private_key
        )
        self.hash_result_script_generator = HashResultScriptGeneratorService()
        self.execution_trace_generation_service = ExecutionTraceGenerationService("prover_files/")
        self.execution_trace_query_service = ExecutionTraceQueryService("prover_files/")

    @staticmethod
    def _as_hex_str(v) -> str:
        """Normalize any witness item to a hex string (or empty)"""
        import re
        if v is None:
            return ""
        if isinstance(v, (bytes, bytearray, memoryview)):
            return bytes(v).hex()
        s = str(v).strip()
        if s.startswith("0x"):
            s = s[2:]
        # keep only hex chars, lower-case
        s = "".join(re.findall(r"[0-9a-fA-F]+", s)).lower()
        return s

    def __call__(
        self,
        setup_uuid: str,
        bitvmx_protocol_setup_properties_dto: BitVMXProtocolSetupPropertiesDTO,
        bitvmx_protocol_prover_dto: BitVMXProtocolProverDTO,
    ) -> Transaction:
        if (
            bitvmx_protocol_setup_properties_dto.bitvmx_protocol_properties_dto.amount_of_input_words
            > 0
            and bitvmx_protocol_prover_dto.input_hex is None
        ):
            raise Exception("Input should be set before publishing the hash result")

        # Get all signatures (prover + verifiers)
        hash_result_signatures = bitvmx_protocol_prover_dto.hash_result_signatures
        print(f"[HASH_RESULT] Using {len(hash_result_signatures)} signatures (prover + verifiers)")

        # Generate execution trace
        self.execution_trace_generation_service(
            setup_uuid=setup_uuid,
            input_hex=bitvmx_protocol_prover_dto.input_hex,
        )
        
        # Get last step trace
        last_step_trace = self.execution_trace_query_service(
            setup_uuid=setup_uuid,
            index=bitvmx_protocol_setup_properties_dto.bitvmx_protocol_properties_dto.amount_of_trace_steps
            - 1,
            input_hex=bitvmx_protocol_prover_dto.input_hex,
        )
        # Determine base
        bits_per_digit = getattr(
            bitvmx_protocol_setup_properties_dto.bitvmx_protocol_properties_dto,
            'amount_of_bits_per_digit',
            4
        )
        hash_result_split_number_nibbles = _get_result_hash_value(last_step_trace)
        
        # Convert nibbles to bytes if using bits_per_digit=8
        if bits_per_digit == 8:
            # Combine pairs of nibbles into bytes
            hash_result_split_number = []
            for i in range(0, len(hash_result_split_number_nibbles), 2):
                byte_val = (hash_result_split_number_nibbles[i] << 4) | hash_result_split_number_nibbles[i+1]
                hash_result_split_number.append(byte_val)
        else:
            hash_result_split_number = hash_result_split_number_nibbles

        last_step = self.execution_trace_query_service.get_last_step(setup_uuid=setup_uuid)
        print(f"[HASH_RESULT] Last step index: {last_step}")

        # Get bits_per_digit from environment or DTO
        import os
        env_bits = os.environ.get('BITVMX_DIGIT_BITS', '')
        if env_bits == '8':
            bits_per_digit = 8
        else:
            bits_per_digit = 4  # default to nibbles
        
        # Generate hash result witness
        print(f"[HASH_RESULT DEBUG] bits_per_digit: {bits_per_digit}")
        print(f"[HASH_RESULT DEBUG] hash_result_split_number: {hash_result_split_number[:10]}... (len={len(hash_result_split_number)})")
        
        try:
            hash_result_witness = self.generate_witness_from_input_nibbles_service(
                step=1,
                case=0,
                input_numbers=hash_result_split_number,
                bits_per_digit_checksum=bitvmx_protocol_setup_properties_dto.bitvmx_protocol_properties_dto.amount_of_bits_per_digit_checksum,
                bits_per_digit_override=bits_per_digit,
            )
        except Exception as e:
            print(f"[HASH_RESULT ERROR] Failed to generate hash witness: {e}")
            import traceback
            traceback.print_exc()
            raise

        # Generate halt step witness
        # Use natural order (no reversal) - generator handles internal reversal
        halt_step_witness = self.generate_witness_from_input_nibbles_service(
            step=1,
            case=1,
            input_numbers=_hex_to_witness(
                hex_str=hex(last_step - 1)[2:],
                length=bitvmx_protocol_setup_properties_dto.bitvmx_protocol_properties_dto.amount_of_nibbles_halt_step,
            ),
            bits_per_digit_checksum=bitvmx_protocol_setup_properties_dto.bitvmx_protocol_properties_dto.amount_of_bits_per_digit_checksum,
            bits_per_digit_override=bits_per_digit,
        )

        # Generate input witness if needed
        if (
            bitvmx_protocol_setup_properties_dto.bitvmx_protocol_properties_dto.amount_of_input_words
            > 0
        ):
            input_witness = []
            for i in range(
                bitvmx_protocol_setup_properties_dto.bitvmx_protocol_properties_dto.amount_of_input_words
            ):
                input_witness += self.generate_witness_from_input_nibbles_service(
                    step=1,
                    case=2 + i,
                    input_numbers=_hex_to_witness(
                        hex_str=bitvmx_protocol_prover_dto.input_hex[i * 8 : (i + 1) * 8],
                        length=8,
                    ),
                    bits_per_digit_checksum=bitvmx_protocol_setup_properties_dto.bitvmx_protocol_properties_dto.amount_of_bits_per_digit_checksum,
                    bits_per_digit_override=bits_per_digit,
                )
        else:
            input_witness = []

        # Generate hash result script
        # Regenerate script with correct base
        hash_gen = HashResultScriptGeneratorService(bits_per_digit=bits_per_digit)
        hash_result_script = hash_gen(
            signature_public_keys=bitvmx_protocol_setup_properties_dto.signature_public_keys,
            hash_result_public_keys=bitvmx_protocol_setup_properties_dto.bitvmx_prover_winternitz_public_keys_dto.hash_result_public_keys,
            halt_step_public_keys=bitvmx_protocol_setup_properties_dto.bitvmx_prover_winternitz_public_keys_dto.halt_step_public_keys,
            input_public_keys_list=bitvmx_protocol_setup_properties_dto.bitvmx_prover_winternitz_public_keys_dto.input_public_keys,
            n0=(64 if bits_per_digit == 4 else 32),
            amount_of_nibbles_halt_step=(8 if bits_per_digit == 4 else 4),
            bits_per_digit_checksum=bitvmx_protocol_setup_properties_dto.bitvmx_protocol_properties_dto.amount_of_bits_per_digit_checksum,
        )
        
        # Build control block and address using the SAME Taproot tree as funding output
        from bitvmx_protocol_library.script_generation.entities.business_objects.bitcoin_script_list import BitcoinScriptList
        prover_timeout_script = bitvmx_protocol_setup_properties_dto.bitvmx_bitcoin_scripts_dto.prover_timeout_script
        funding_tree = BitcoinScriptList([hash_result_script, prover_timeout_script])
        # hash_result_script is index 0 in this tree
        # Try both field names for compatibility
        unspendable_key = getattr(bitvmx_protocol_setup_properties_dto, 'unspendable_public_key', None)
        if not unspendable_key:
            unspendable_key = getattr(bitvmx_protocol_setup_properties_dto, 'seed_unspendable_public_key', None)
        hash_result_script_address = funding_tree.get_taproot_address(
            unspendable_key
        )
        hash_result_control_block_hex = funding_tree.get_control_block_hex(
            unspendable_key,
            0,
            hash_result_script_address.is_odd(),
        )

        # Log witness details
        print(f"[HASH_RESULT] Hash result witness items: {len(hash_result_witness)}")
        print(f"[HASH_RESULT] Halt step witness items: {len(halt_step_witness)}")
        print(f"[HASH_RESULT] Input witness items: {len(input_witness)}")
        print(f"[HASH_RESULT] Script length: {len(hash_result_script.to_hex()) // 2} bytes")
        print(f"[HASH_RESULT] Control block length: {len(hash_result_control_block_hex) // 2} bytes")
        print(f"[HASH_RESULT] Control block parity: {'odd' if hash_result_script_address.is_odd() else 'even'}")
        print(f"[HASH_RESULT] Funding tree taproot address: {hash_result_script_address.to_string()}")
        
        # Check prevout
        tx = bitvmx_protocol_setup_properties_dto.bitvmx_transactions_dto.hash_result_tx
        if tx.inputs and len(tx.inputs) > 0:
            prevout_txid = tx.inputs[0].txid
            prevout_vout = tx.inputs[0].txout_index
            print(f"[HASH_RESULT] Prevout: {prevout_txid}:{prevout_vout}")

        # Build complete witness stack
        # Order: input_witness, halt_step_witness, hash_result_witness, signatures, [script, control_block]
        # This matches script verification order: inputs first, then halt, then hash, then signatures
        witness_stack = (
            input_witness
            + halt_step_witness
            + hash_result_witness
            + hash_result_signatures
            + [hash_result_script.to_hex(), hash_result_control_block_hex]
        )
        # Normalize all items to hex strings (do not drop empty strings)
        witness_stack = [self._as_hex_str(x) for x in witness_stack]

        print(f"[HASH_RESULT] Total witness stack items: {len(witness_stack)}")

        # Add witness to transaction
        tx_obj = bitvmx_protocol_setup_properties_dto.bitvmx_transactions_dto.hash_result_tx
        # Clear existing witnesses and set for first input
        tx_obj.witnesses = [TxWitnessInput(witness_stack)]

        print(f"[HASH_RESULT] Complete witness stack attached to hash_result_tx")
        
        # Return the transaction (caller will serialize and broadcast)
        return tx_obj
