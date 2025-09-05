from typing import List

from bitcoinutils.keys import PrivateKey

from bitvmx_protocol_library.winternitz_keys_handling.services.compute_max_checksum_service import (
    ComputeMaxChecksumService,
)
from bitvmx_protocol_library.winternitz_keys_handling.services.generate_winternitz_keys_nibbles_service import (
    GenerateWinternitzKeysNibblesService,
)


def _compute_checksum(
    message: List[int],
    bits_per_digit_checksum: int,
    max_checksum_value: int,
    n1: int,
):
    checksum_value = max_checksum_value - sum(message)

    binary_checksum_value = bin(checksum_value)[2:].zfill(n1 * bits_per_digit_checksum)

    checksum_digits = []
    for i in range(n1):
        checksum_digits.insert(
            0,
            int(
                binary_checksum_value[
                    i * bits_per_digit_checksum : i * bits_per_digit_checksum
                    + bits_per_digit_checksum
                ],
                2,
            ),
        )

    return checksum_digits


class GenerateWitnessFromInputNibblesService:

    def __init__(self, secret_key: PrivateKey, bits_per_digit: int = 4):
        self.bits_per_digit = 8 if bits_per_digit == 8 else 4
        self.compute_max_checksum_service = ComputeMaxChecksumService()
        self.generate_winternitz_keys_nibbles_service = GenerateWinternitzKeysNibblesService(
            secret_key, bits_per_digit=self.bits_per_digit
        )

    def __call__(
        self,
        step: int,
        case: int,
        input_numbers: List[int],
        bits_per_digit_checksum: int,
        bits_per_digit_override: int = None,
    ):
        # Determine base for this call
        call_bits = self.bits_per_digit if bits_per_digit_override is None else (8 if bits_per_digit_override == 8 else 4)
        d0 = 2 ** call_bits
        n0 = len(input_numbers)
        d1, n1, max_checksum_value = self.compute_max_checksum_service(
            d0, n0, bits_per_digit_checksum
        )
        checksum_digits = _compute_checksum(
            input_numbers,
            bits_per_digit_checksum,
            max_checksum_value,
            n1,
        )
        # Use key generator with matching bits; recreate if override differs
        key_gen = self.generate_winternitz_keys_nibbles_service
        if bits_per_digit_override is not None and call_bits != self.bits_per_digit:
            try:
                from bitcoinutils.keys import PrivateKey
                sk_hex = getattr(self.generate_winternitz_keys_nibbles_service, 'private_key', None)
                if sk_hex:
                    key_gen = GenerateWinternitzKeysNibblesService(PrivateKey(b=bytes.fromhex(sk_hex)), bits_per_digit=call_bits)
            except Exception:
                # fallback to existing generator
                key_gen = self.generate_winternitz_keys_nibbles_service
        current_keys = key_gen(step, case, n0)
        input_keys = current_keys[n1:]
        checksum_keys = current_keys[:n1]
        # checksum_keys.reverse()
        witness = []
        for digit_index in range(len(input_numbers) - 1, -1, -1):
            current_digit = input_numbers[digit_index]
            current_private_key = input_keys[digit_index][current_digit]
            witness.append(current_private_key)
            witness.append(hex(current_digit)[2:].zfill(2) if current_digit > 0 else "")

        for i in range(n1 - 1, -1, -1):
            current_digit = checksum_digits[i]
            current_private_key = checksum_keys[i][current_digit]
            witness.append(current_private_key)
            witness.append(hex(current_digit)[2:].zfill(2) if current_digit > 0 else "")

        return witness
