from typing import List

from bitcoinutils.keys import PublicKey

from bitvmx_protocol_library.script_generation.entities.business_objects.bitcoin_script import (
    BitcoinScript,
)
from bitvmx_protocol_library.winternitz_keys_handling.scripts.verify_digit_signature_nibbles_service import (
    VerifyDigitSignatureNibblesService,
)


class HashResultScriptGeneratorService:

    def __init__(self, bits_per_digit: int = 4):
        self.bits_per_digit = 8 if bits_per_digit == 8 else 4
        self.verify_input_nibbles_message_from_public_keys = VerifyDigitSignatureNibblesService(bits_per_digit=self.bits_per_digit)

    def __call__(
        self,
        signature_public_keys: List[str],
        hash_result_public_keys: List[str],
        halt_step_public_keys: List[str],
        input_public_keys_list: List[List[str]],
        n0: int,
        amount_of_nibbles_halt_step: int,
        bits_per_digit_checksum: int,
    ):
        script = BitcoinScript()

        # per-word digit count depends on base: 8 nibbles or 4 bytes
        per_word_digits = 4 if self.bits_per_digit == 8 else 8
        for input_public_keys in reversed(input_public_keys_list):
            self.verify_input_nibbles_message_from_public_keys(
                script,
                input_public_keys,
                per_word_digits,
                bits_per_digit_checksum,
                to_alt_stack=True,
            )

        self.verify_input_nibbles_message_from_public_keys(
            script,
            halt_step_public_keys,
            amount_of_nibbles_halt_step,
            bits_per_digit_checksum,
            to_alt_stack=True,
        )

        self.verify_input_nibbles_message_from_public_keys(
            script,
            hash_result_public_keys,
            n0,
            bits_per_digit_checksum,
            to_alt_stack=True,
        )

        # script.append("OP_CODESEPARATOR")

        for signature_public_key in reversed(signature_public_keys):
            script.extend(
                [PublicKey(signature_public_key).to_x_only_hex(), "OP_CHECKSIGVERIFY"]
            )

        script.append(1)
        return script
