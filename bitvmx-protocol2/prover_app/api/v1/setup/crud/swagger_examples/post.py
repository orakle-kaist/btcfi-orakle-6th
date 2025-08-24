setup_post_v1_input_swagger_examples = {
    "example_1": {
        "summary": "BitVMX Setup Example",
        "value": {
            "amount_of_nibbles_hash": 4,
            "amount_of_nibbles_hash_step": 4,
            "amount_of_bits_per_digit_checksum": 4,
            "max_amount_of_steps": 50,
            "amount_of_bits_wrong_step_search": 2,
            "amount_of_bits_per_digit_checksum_step": 4,
            "amount_of_bits_per_digit_checksum_hash_step": 4,
            "amount_of_bits_per_digit_checksum_address": 4,
            "amount_of_bits_per_digit_checksum_read_value": 4,
            "amount_of_nibbles_committed_readable_data": 8,
            "max_size_prover_winternitz_public_keys": 50,
            "max_size_verifier_winternitz_public_keys": 50,
            "prover_public_key": "0279be667ef9dcbbac55a06295ce870b07029bfcdb2dce28d959f2815b16f81798",
            "verifier_public_key": "02c6047f9441ed7d6d3045406e95c07cd85c778e4b8cef3ca7abac09b95c709ee5",
            "input_hex": "11111111",
            "elf_file_path": "/bitvmx-backend/execution_files/hello-world.elf"
        }
    }
}

setup_post_v1_output_swagger_examples = {
    "example_1": {
        "summary": "Successful Setup Response",
        "value": {
            "setup_uuid": "123e4567-e89b-12d3-a456-426614174000",
            "message": "Setup created successfully"
        }
    }
}