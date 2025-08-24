from typing import Optional
from pydantic import BaseModel

class SetupPostV1Input(BaseModel):
    amount_of_nibbles_hash: int
    amount_of_nibbles_hash_step: int
    amount_of_bits_per_digit_checksum: int
    max_amount_of_steps: int
    amount_of_bits_wrong_step_search: int
    amount_of_bits_per_digit_checksum_step: int
    amount_of_bits_per_digit_checksum_hash_step: int
    amount_of_bits_per_digit_checksum_address: int
    amount_of_bits_per_digit_checksum_read_value: int
    amount_of_nibbles_committed_readable_data: int
    max_size_prover_winternitz_public_keys: int
    max_size_verifier_winternitz_public_keys: int
    prover_public_key: str
    verifier_public_key: str
    input_hex: str
    elf_file_path: str
    funding_tx_id: Optional[str] = None
    funding_index: Optional[int] = None
    funding_amount_of_satoshis: Optional[int] = None
    secret_origin_of_funds: Optional[str] = None
    prover_destination_address: Optional[str] = None
    prover_signature_private_key: Optional[str] = None
    prover_signature_public_key: Optional[str] = None

class SetupPostV1Output(BaseModel):
    setup_uuid: str
    message: str