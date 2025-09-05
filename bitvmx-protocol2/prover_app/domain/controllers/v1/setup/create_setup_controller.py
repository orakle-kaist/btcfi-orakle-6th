import os
import json
import secrets
import uuid
from time import time
from typing import List

import requests
from bitcoinutils.keys import PrivateKey
from bitcoinutils.transactions import TxInput, TxWitnessInput
from bitcoinutils.script import Script
import hashlib

from bitvmx_protocol_library.bitvmx_protocol_definition.entities.bitvmx_protocol_properties_dto import (
    BitVMXProtocolPropertiesDTO,
)
from bitvmx_protocol_library.bitvmx_protocol_definition.entities.bitvmx_protocol_prover_dto import (
    BitVMXProtocolProverDTO,
)
from bitvmx_protocol_library.bitvmx_protocol_definition.entities.bitvmx_protocol_prover_private_dto import (
    BitVMXProtocolProverPrivateDTO,
)
from bitvmx_protocol_library.bitvmx_protocol_definition.entities.bitvmx_protocol_setup_properties_dto import (
    BitVMXProtocolSetupPropertiesDTO,
)
from bitvmx_protocol_library.bitvmx_protocol_definition.entities.bitvmx_verifier_winternitz_public_keys_dto import (
    BitVMXVerifierWinternitzPublicKeysDTO,
)
from bitvmx_protocol_library.config import common_protocol_properties
from bitvmx_protocol_library.transaction_generation.entities.dtos.bitvmx_verifier_signatures_dto import (
    BitVMXVerifierSignaturesDTO,
)
from prover_app.domain.persistences.interfaces.bitvmx_protocol_prover_dto_persistence_interface import (
    BitVMXProtocolProverDTOPersistenceInterface,
)
from prover_app.domain.persistences.interfaces.bitvmx_protocol_prover_private_dto_persistence_interface import (
    BitVMXProtocolProverPrivateDTOPersistenceInterface,
)
from verifier_app.domain.persistences.interfaces.bitvmx_protocol_setup_properties_dto_persistence_interface import (
    BitVMXProtocolSetupPropertiesDTOPersistenceInterface,
)


class CreateSetupController:
    
    def _describe_input(self, setup_type: str, input_hex: str) -> str:
        """Describe the input data based on setup type"""
        if not input_hex:
            return "No input data"
        
        try:
            # Parse hex input (assuming 4 words of 32 bits each = 32 hex chars total)
            if setup_type == "OPTION_REGISTRATION" and len(input_hex) == 32:
                # Format: option_type(8) + strike(8) + expiry(8) + pool_size(8)
                option_type = int(input_hex[0:8], 16)
                strike = int(input_hex[8:16], 16)
                expiry = int(input_hex[16:24], 16)
                pool_size = int(input_hex[24:32], 16)
                
                option_type_str = "CALL" if option_type == 0 else "PUT"
                return f"Option Type: {option_type_str}, Strike: ${strike/100:.2f}, Expiry: {expiry}, Pool Size: {pool_size}"
                
            elif setup_type == "OPTION_PURCHASE" and len(input_hex) >= 24:
                # Format: option_id(8) + quantity(8) + premium(8)
                option_id = input_hex[0:8]
                quantity = int(input_hex[8:16], 16)
                premium = int(input_hex[16:24], 16)
                return f"Option ID: {option_id}, Quantity: {quantity}, Premium: {premium} sats"
                
            elif setup_type == "OPTION_SETTLEMENT" and len(input_hex) >= 24:
                # Format: option_id(8) + spot_price(8) + timestamp(8)
                option_id = input_hex[0:8]
                spot_price = int(input_hex[8:16], 16)
                timestamp = int(input_hex[16:24], 16)
                return f"Option ID: {option_id}, Spot Price: ${spot_price/100:.2f}, Timestamp: {timestamp}"
                
            else:
                return f"Raw input: {input_hex}"
                
        except Exception as e:
            return f"Failed to parse input: {input_hex}"
    def __init__(
        self,
        broadcast_transaction_service,
        transaction_info_service,
        transaction_generator_from_public_keys_service,
        faucet_service,
        bitvmx_bitcoin_scripts_generator_service,
        generate_prover_public_keys_service_class,
        verify_verifier_signatures_service_class,
        generate_signatures_service_class,
        bitvmx_protocol_setup_properties_dto_persistence: BitVMXProtocolSetupPropertiesDTOPersistenceInterface,
        bitvmx_protocol_prover_private_dto_persistence: BitVMXProtocolProverPrivateDTOPersistenceInterface,
        bitvmx_protocol_prover_dto_persistence: BitVMXProtocolProverDTOPersistenceInterface,
    ):
        self.broadcast_transaction_service = broadcast_transaction_service
        self.transaction_info_service = transaction_info_service
        self.transaction_generator_from_public_keys_service = (
            transaction_generator_from_public_keys_service
        )
        self.faucet_service = faucet_service
        self.bitvmx_bitcoin_scripts_generator_service = bitvmx_bitcoin_scripts_generator_service
        self.generate_prover_public_keys_service_class = generate_prover_public_keys_service_class
        self.verify_verifier_signatures_service_class = verify_verifier_signatures_service_class
        self.generate_signatures_service_class = generate_signatures_service_class
        self.bitvmx_protocol_setup_properties_dto_persistence = (
            bitvmx_protocol_setup_properties_dto_persistence
        )
        self.bitvmx_protocol_prover_private_dto_persistence = (
            bitvmx_protocol_prover_private_dto_persistence
        )
        self.bitvmx_protocol_prover_dto_persistence = bitvmx_protocol_prover_dto_persistence

    async def __call__(
        self,
        max_amount_of_steps: int,
        amount_of_input_words: int,
        amount_of_bits_wrong_step_search: int,
        amount_of_bits_per_digit_checksum: int,
        verifier_list: List[str],
        controlled_prover_private_key: PrivateKey,
        funding_tx_id: str,
        funding_index: int,
        step_fees_satoshis: int,
        origin_of_funds_private_key: PrivateKey,
        prover_destination_address: str,
        prover_signature_private_key: str,
        prover_signature_public_key: str,
        funding_private_key: str = None,
        elf_file_name: str = None,
    ) -> str:
        setup_uuid = str(uuid.uuid4())
        prover_uuid = str(uuid.uuid4())
        init_time = time()

        if funding_tx_id == "0" * 64:
            raise Exception("[NO_FAUCET] funding_tx_id is required. Provide your P2WPKH UTXO to wrap.")
        
        print(f"[NO_FAUCET] Wrapping mode: Using our P2WPKH UTXO: {funding_tx_id}:{funding_index}")
        funding_tx_info = self.transaction_info_service(tx_id=funding_tx_id)
        
        if funding_index >= len(funding_tx_info.outputs):
            raise Exception(f"[CRITICAL] Invalid funding_index {funding_index}. Transaction only has {len(funding_tx_info.outputs)} outputs")
        
        actual_output = funding_tx_info.outputs[funding_index]
        print(f"[NO_FAUCET] Input UTXO verified: {actual_output.value} satoshis")
        print(f"[NO_FAUCET] Will wrap this to BitVMX-compatible Taproot output")
        # Preflight: ensure funding UTXO is unspent to avoid 500s on retries
        try:
            outspends_url = f"https://mutinynet.com/api/tx/{funding_tx_id}/outspends"
            resp = requests.get(outspends_url, timeout=15)
            if resp.status_code == 200 and resp.content:
                arr = resp.json()
                if isinstance(arr, list) and funding_index < len(arr):
                    if bool(arr[funding_index].get("spent")):
                        raise Exception(f"[NO_FAUCET] Funding UTXO already spent: {funding_tx_id}:{funding_index}")
                else:
                    print(f"[WARNING] outspends response unexpected for {funding_tx_id}")
            else:
                print(f"[WARNING] outspends query failed status={resp.status_code} url={outspends_url}")
        except Exception as e:
            if "already spent" in str(e).lower():
                raise
            print(f"[WARNING] outspends preflight check error: {e}")
        
        initial_amount_of_satoshis = actual_output.value
        print(f"[NO_FAUCET] Using full UTXO amount: {initial_amount_of_satoshis} satoshis")

        bitvmx_protocol_properties_dto = BitVMXProtocolPropertiesDTO(
            max_amount_of_steps=max_amount_of_steps,
            amount_of_input_words=amount_of_input_words,
            amount_of_bits_wrong_step_search=amount_of_bits_wrong_step_search,
            amount_of_bits_per_digit_checksum=amount_of_bits_per_digit_checksum,
        )

        public_keys = []
        verifier_destroyed_public_key_hex = None
        verifier_signature_public_key_hex = None
        verifier_destination_address = None
        verifier_address_dict = {}
        signatures_public_keys_dict = {}
        for verifier in verifier_list:
            current_uuid = str(uuid.uuid4())
            verifier_address_dict[current_uuid] = verifier
            url = f"{verifier}/setup"
            headers = {"accept": "application/json", "Content-Type": "application/json"}
            data = {"setup_uuid": setup_uuid, "network": common_protocol_properties.network.value}

            response = requests.post(url, headers=headers, json=data, timeout=300)
            if response.status_code == 200:
                response_json = response.json()
                verifier_destroyed_public_key_hex = response_json["public_key"]
                verifier_signature_public_key_hex = response_json["verifier_signature_public_key"]
                verifier_destination_address = response_json["verifier_destination_address"]
                public_keys.append(verifier_destroyed_public_key_hex)
                signatures_public_keys_dict[current_uuid] = verifier_signature_public_key_hex
            else:
                print(f"[ERROR] Verifier /setup response status: {response.status_code}")
                print(f"[ERROR] Verifier /setup response text: {response.text}")
                raise Exception(f"Verifier setup call failed with status {response.status_code}: {response.text}")

        winternitz_private_key = PrivateKey(b=secrets.token_bytes(32))

        unspendable_public_key = None
        seed_unspendable_public_key = ""
        prover_destroyed_private_key = PrivateKey(b=secrets.token_bytes(32))
        prover_destroyed_public_key = prover_destroyed_private_key.get_public_key()
        public_keys.append(prover_destroyed_public_key.to_hex())
        while unspendable_public_key is None:
            try:
                seed_unspendable_public_key = "".join(public_keys)
                unspendable_public_key = (
                    BitVMXProtocolSetupPropertiesDTO.unspendable_public_key_from_seed(
                        seed_unspendable_public_key=seed_unspendable_public_key
                    )
                )
                continue
            except IndexError:
                prover_destroyed_private_key = PrivateKey(b=secrets.token_bytes(32))
                prover_destroyed_public_key = prover_destroyed_private_key.get_public_key()
                public_keys[-1] = prover_destroyed_public_key.to_hex()

        generate_prover_public_keys_service = self.generate_prover_public_keys_service_class(
            winternitz_private_key
        )
        print("Public keys generated: " + str(time() - init_time))
        bitvmx_prover_winternitz_public_keys_dto = generate_prover_public_keys_service(
            bitvmx_protocol_properties_dto=bitvmx_protocol_properties_dto,
        )

        # Calculate instruction commitment path once at setup time
        from bitvmx_protocol_library.bitvmx_execution.services.execution_trace_generation_service import ExecutionTraceGenerationService
        import os
        import subprocess
        
        instruction_commitment_path = ExecutionTraceGenerationService.commitment_file(elf_file_name=elf_file_name)
        print(f"[SETUP] Using commitment file: {instruction_commitment_path}")
        
        # Auto-generate commitment file if it doesn't exist
        if not os.path.exists(instruction_commitment_path):
            print(f"[SETUP] Commitment file not found, generating: {instruction_commitment_path}")
            elf_path = f"./execution_files/{elf_file_name}"
            if os.path.exists(elf_path):
                try:
                    # Generate ROM commitment
                    result = subprocess.run(
                        ["cargo", "run", "-p", "emulator", "--", "generate-rom-commitment", "--elf", elf_path],
                        capture_output=True, text=True, cwd="./BitVMX-CPU"
                    )
                    if result.returncode == 0:
                        # Save to commitment file
                        with open(instruction_commitment_path, 'w') as f:
                            f.write(result.stdout)
                        print(f"[SETUP] Successfully generated commitment file")
                    else:
                        print(f"[SETUP] Warning: Failed to generate commitment: {result.stderr}")
                except Exception as e:
                    print(f"[SETUP] Warning: Could not generate commitment file: {e}")
            else:
                print(f"[SETUP] Warning: ELF file not found: {elf_path}")
        
        bitvmx_protocol_setup_properties_dto = BitVMXProtocolSetupPropertiesDTO(
            setup_uuid=setup_uuid,
            uuid=prover_uuid,
            funding_amount_of_satoshis=initial_amount_of_satoshis,
            step_fees_satoshis=step_fees_satoshis,
            funding_tx_id=funding_tx_id,
            funding_index=funding_index,
            funding_private_key=funding_private_key,
            verifier_address_dict=verifier_address_dict,
            prover_destination_address=prover_destination_address,
            prover_signature_public_key=prover_signature_public_key,
            verifier_signature_public_key=verifier_signature_public_key_hex,
            verifier_destination_address=verifier_destination_address,
            seed_unspendable_public_key=seed_unspendable_public_key,
            unspendable_public_key=unspendable_public_key,  # CRITICAL: Add the actual unspendable key!
            prover_destroyed_public_key=prover_destroyed_private_key.get_public_key().to_hex(),
            verifier_destroyed_public_key=verifier_destroyed_public_key_hex,
            bitvmx_protocol_properties_dto=bitvmx_protocol_properties_dto,
            elf_file_name=elf_file_name,
            instruction_commitment_path=instruction_commitment_path,
            bitvmx_prover_winternitz_public_keys_dto=bitvmx_prover_winternitz_public_keys_dto,
        )

        verifier_public_keys_dict = {}

        for verifier_uuid, verifier_value in verifier_address_dict.items():
            url = f"{verifier_value}/public_keys"
            headers = {"accept": "application/json", "Content-Type": "application/json"}
            data = {
                "bitvmx_protocol_setup_properties_dto": bitvmx_protocol_setup_properties_dto.model_dump() if hasattr(bitvmx_protocol_setup_properties_dto, 'model_dump') else bitvmx_protocol_setup_properties_dto.dict()
            }

            public_keys_response = requests.post(url, headers=headers, json=data, timeout=600)
            if public_keys_response.status_code != 200:
                print(f"[ERROR] Verifier /public_keys response status: {public_keys_response.status_code}")
                print(f"[ERROR] Verifier /public_keys response text: {public_keys_response.text}")
                raise Exception(f"Public keys verifier call failed with status {public_keys_response.status_code}: {public_keys_response.text}")
            public_keys_response_json = public_keys_response.json()
            
            returned_setup_uuid = public_keys_response_json.get("setup_uuid")
            if returned_setup_uuid and returned_setup_uuid != setup_uuid:
                print(f"[WARNING] Setup UUID mismatch: expected {setup_uuid}, got {returned_setup_uuid}")
            
            verifier_public_keys_dict[verifier_uuid] = public_keys_response_json[
                "verifier_public_key"
            ]
            
            bitvmx_protocol_setup_properties_dto.bitvmx_verifier_winternitz_public_keys_dto = (
                BitVMXVerifierWinternitzPublicKeysDTO(
                    **public_keys_response_json["bitvmx_verifier_winternitz_public_keys_dto"]
                )
            )
        print("Verifier public keys generated: " + str(time() - init_time))

        # Create scripts generator with elf_file_name if provided
        if elf_file_name:
            from bitvmx_protocol_library.script_generation.services.bitvmx_bitcoin_scripts_generator_service import BitVMXBitcoinScriptsGeneratorService
            scripts_generator = BitVMXBitcoinScriptsGeneratorService(elf_file_name=elf_file_name)
        else:
            scripts_generator = self.bitvmx_bitcoin_scripts_generator_service
        
        # CRITICAL: Check if scripts already exist (from previous setup) and reuse them
        # This prevents script tree changes that cause fingerprint mismatches
        existing_dto_path = f"{self.bitvmx_protocol_setup_properties_dto_persistence.base_path}/{setup_uuid}/{self.bitvmx_protocol_setup_properties_dto_persistence.file_name}"
        
        if os.path.exists(existing_dto_path):
            # Load existing DTO to get the scripts
            try:
                with open(existing_dto_path, 'r') as f:
                    existing_data = json.load(f)
                if 'bitvmx_bitcoin_scripts_dto' in existing_data and existing_data['bitvmx_bitcoin_scripts_dto']:
                    print("[SCRIPT_REUSE] Found existing scripts DTO, reusing to maintain fingerprint")
                    from bitvmx_protocol_library.script_generation.entities.dtos.bitvmx_bitcoin_scripts_dto import BitVMXBitcoinScriptsDTO
                    bitvmx_protocol_setup_properties_dto.bitvmx_bitcoin_scripts_dto = BitVMXBitcoinScriptsDTO(**existing_data['bitvmx_bitcoin_scripts_dto'])
                    print("[SCRIPT_REUSE] Scripts loaded from existing setup")
                else:
                    # No existing scripts, generate new ones
                    print("[SCRIPT_GEN] No existing scripts found, generating new ones")
                    bitvmx_protocol_setup_properties_dto.bitvmx_bitcoin_scripts_dto = (
                        scripts_generator(
                            bitvmx_protocol_setup_properties_dto=bitvmx_protocol_setup_properties_dto,
                        )
                    )
                    print("Bitcoin scripts generated: " + str(time() - init_time))
            except Exception as e:
                print(f"[SCRIPT_GEN] Could not load existing scripts: {e}, generating new ones")
                bitvmx_protocol_setup_properties_dto.bitvmx_bitcoin_scripts_dto = (
                    scripts_generator(
                        bitvmx_protocol_setup_properties_dto=bitvmx_protocol_setup_properties_dto,
                    )
                )
                print("Bitcoin scripts generated: " + str(time() - init_time))
        else:
            # No existing setup, generate new scripts
            print("[SCRIPT_GEN] First time setup, generating scripts")
            bitvmx_protocol_setup_properties_dto.bitvmx_bitcoin_scripts_dto = (
                scripts_generator(
                    bitvmx_protocol_setup_properties_dto=bitvmx_protocol_setup_properties_dto,
                )
            )
            print("Bitcoin scripts generated: " + str(time() - init_time))

        # =================================================================
        # [GEMINI] Save critical signing data to bypass DTO hydration issues
        # =================================================================
        try:
            print("[GEMINI_CACHE] Saving golden hash_result_script...")
            
            golden_hash_script_hex = bitvmx_protocol_setup_properties_dto.bitvmx_bitcoin_scripts_dto.hash_result_script.to_hex()
            
            signing_cache_dir = f"prover_files/{setup_uuid}"
            if not os.path.exists(signing_cache_dir):
                os.makedirs(signing_cache_dir)
            
            signing_cache_file = f"{signing_cache_dir}/signing_cache.json"
            
            cache_data = {
                "hash_result_script_hex": golden_hash_script_hex,
                "comment": "This data is saved at setup time to ensure consistency and bypass DTO hydration bugs during signing."
            }
            
            with open(signing_cache_file, 'w') as f:
                json.dump(cache_data, f, indent=2)
                
            print(f"[GEMINI_CACHE] Successfully saved golden script to {signing_cache_file}")

        except Exception as e:
            print(f"[GEMINI_CACHE] CRITICAL WARNING: Failed to save signing cache: {e}")
            # This is critical, so we should probably halt.
            raise Exception(f"Failed to save critical signing cache: {e}")

        # =================================================================
        # [GEMINI] Save critical signing data to bypass DTO hydration issues
        # =================================================================
        try:
            print("[GEMINI_CACHE] Saving critical signing data (script and control block)...")
            
            # Get the necessary components from the golden DTO
            scripts_dto = bitvmx_protocol_setup_properties_dto.bitvmx_bitcoin_scripts_dto
            golden_hash_script = scripts_dto.hash_result_script
            prover_timeout_script = scripts_dto.prover_timeout_script
            unspendable_pk = bitvmx_protocol_setup_properties_dto.unspendable_public_key

            # Re-create the exact script tree for the funding transaction output
            from bitvmx_protocol_library.script_generation.entities.business_objects.bitcoin_script_list import BitcoinScriptList
            funding_script_tree = BitcoinScriptList([golden_hash_script, prover_timeout_script])
            
            # The index of hash_result_script in this tree is 0
            script_index = 0
            
            # Generate the control block from this specific tree
            # This requires the taproot address to be calculated first to get the is_odd() property
            funding_taproot_address = funding_script_tree.get_taproot_address(unspendable_pk)
            control_block_hex = funding_script_tree.get_control_block_hex(unspendable_pk, script_index, funding_taproot_address.is_odd())

            # Create the cache directory and file
            signing_cache_dir = f"prover_files/{setup_uuid}"
            if not os.path.exists(signing_cache_dir):
                os.makedirs(signing_cache_dir)
            
            signing_cache_file = f"{signing_cache_dir}/signing_cache.json"
            
            # Save the data
            cache_data = {
                "hash_result_script_hex": golden_hash_script.to_hex(),
                "control_block_hex": control_block_hex,
                "comment": "This data is saved at setup time to ensure consistency and bypass DTO hydration bugs during signing."
            }
            
            with open(signing_cache_file, 'w') as f:
                json.dump(cache_data, f, indent=2)
                
            print(f"[GEMINI_CACHE] Successfully saved signing data to {signing_cache_file}")

        except Exception as e:
            print(f"[GEMINI_CACHE] CRITICAL WARNING: Failed to save signing cache: {e}")
            raise Exception(f"Failed to save critical signing cache: {e}")
        
        # Store initial fingerprint for later verification
        initial_fingerprint = None
        if hasattr(bitvmx_protocol_setup_properties_dto.bitvmx_bitcoin_scripts_dto, 'tree_fingerprint'):
            initial_fingerprint = bitvmx_protocol_setup_properties_dto.bitvmx_bitcoin_scripts_dto.tree_fingerprint
            print(f"[SCRIPT FINGERPRINT] Initial: {initial_fingerprint}")

        # =================================================================
        # REFACTORED LOGIC STARTS HERE
        # =================================================================
        
        # 1. Generate a dummy funding_tx object to satisfy the generator service
        # This will be overwritten later, but it's needed for the initial DTO structure.
        # The important part is that the transaction generator will use the correct
        # funding_tx_id and funding_index from the setup_properties DTO.
        
        # CRITICAL: Use a SINGLE generator instance throughout to ensure consistent scripts/addresses
        # This prevents cache/state mismatch between wrapping and transaction generation
        print("[NO_FAUCET] Creating single generator instance for consistent state")
        
        # Create ONE generator instance that will be used for both wrapping and final generation
        from bitvmx_protocol_library.transaction_generation.services.transaction_generator_from_public_keys_service_optimized import (
            TransactionGeneratorFromPublicKeysServiceOptimized
        )
        
        # Create the single generator instance
        single_generator = TransactionGeneratorFromPublicKeysServiceOptimized()
        print("[GENERATOR] Created single generator instance to use throughout")
        
        # Generate initial transactions to get the funding address
        # This ensures all scripts and addresses are consistent
        bitvmx_protocol_setup_properties_dto.bitvmx_transactions_dto = single_generator(
            bitvmx_protocol_setup_properties_dto=bitvmx_protocol_setup_properties_dto,
        )
        print("[GENERATOR] Initial transactions generated with single instance")
        
        # 2. Create a NEW wrapper transaction (not using the BitVMX-generated one)
        # BitVMX assumes Taproot input, but we have P2WPKH input
        from bitcoinutils.transactions import Transaction, TxOutput
        from bitcoinutils.script import Script
        
        # Create a fresh transaction for wrapping
        funding_tx = Transaction()
        
        # CRITICAL: Generate the correct Taproot address from scripts
        # We need to use the EXACT same tree structure that will be used later
        from bitvmx_protocol_library.script_generation.entities.business_objects.bitcoin_script_list import BitcoinScriptList
        
        # Get the hash_result and timeout scripts
        hash_result_script = bitvmx_protocol_setup_properties_dto.bitvmx_bitcoin_scripts_dto.hash_result_script
        prover_timeout_script = bitvmx_protocol_setup_properties_dto.bitvmx_bitcoin_scripts_dto.prover_timeout_script
        
        # Build the EXACT same tree structure with FIXED tree_key
        # Generate a deterministic tree_key based on script content FIRST
        import hashlib
        script_hash = hashlib.sha256(hash_result_script.to_hex().encode() + prover_timeout_script.to_hex().encode()).digest()
        tree_key_hex = script_hash[:8].hex()
        print(f"[WRAPPER] Using deterministic tree_key: {tree_key_hex}")
        
        # Pass tree_key directly to BitcoinScriptList constructor
        funding_script_tree = BitcoinScriptList([hash_result_script, prover_timeout_script], tree_key=tree_key_hex)
        
        # Also set tree_key on individual scripts to ensure consistency
        hash_result_script.tree_key = tree_key_hex
        prover_timeout_script.tree_key = tree_key_hex
        
        # Get the unspendable key
        unspendable_key = bitvmx_protocol_setup_properties_dto.unspendable_public_key
        
        # Get the Taproot address from the tree with fixed tree_key
        taproot_address_obj = funding_script_tree.get_taproot_address(unspendable_key)
        
        # Convert to Script object for the output
        from bitcoinutils.script import Script
        target_taproot_script = Script.from_raw(taproot_address_obj.to_script_pub_key().to_hex())
        
        # Create output to the Taproot address
        wrapper_output_amount = initial_amount_of_satoshis - 5000  # Deduct fee
        funding_tx.outputs = [TxOutput(amount=wrapper_output_amount, script_pubkey=target_taproot_script)]
        
        print(f"[WRAPPER] Created new wrapper TX with P2WPKH input → Taproot output")
        print(f"[WRAPPER] Output script: {target_taproot_script.to_hex()}")
        print(f"[WRAPPER] Taproot address: {taproot_address_obj.to_string()}")
        
        # CRITICAL DEBUG: What script does the wrapping tx output have?
        if funding_tx.outputs and funding_tx.outputs[0].script_pubkey:
            wrapping_output_script = funding_tx.outputs[0].script_pubkey
            print(f"[WRAPPER DEBUG] Output script (hex): {wrapping_output_script.to_hex()}")
            print(f"[WRAPPER DEBUG] Output script type: {type(wrapping_output_script)}")
            # Try to get the address from the script
            try:
                from bitcoinutils.keys import P2trAddress
                # Check if it's a Taproot script (starts with OP_1 0x20)
                script_hex = wrapping_output_script.to_hex()
                if script_hex.startswith("5120"):
                    witness_program = bytes.fromhex(script_hex[4:])
                    print(f"[WRAPPER DEBUG] Taproot witness program: {witness_program.hex()}")
            except:
                pass
        
        # 2b. Fee already deducted when creating the output above
        
        # 3. Forcibly overwrite the inputs to ensure they are correct
        from bitcoinutils.transactions import TxInput
        from bitcoinutils.script import Script
        funding_utxo_txid = bitvmx_protocol_setup_properties_dto.funding_tx_id
        funding_utxo_index = bitvmx_protocol_setup_properties_dto.funding_index
        funding_tx.inputs = [TxInput(txid=funding_utxo_txid, txout_index=funding_utxo_index, script_sig=Script([]))]
        print(f"[CLEANUP FIX] Inputs overwritten to be: {funding_tx.inputs}")

        # Log the wrapper transaction structure
        print(f"[WRAPPER] Transaction has {len(funding_tx.inputs)} input(s) and {len(funding_tx.outputs)} output(s)")
        if funding_tx.outputs:
            print(f"[WRAPPER] Output amount: {funding_tx.outputs[0].amount} sats")
            if hasattr(funding_tx.outputs[0].script_pubkey, 'to_hex'):
                print(f"[WRAPPER] Output script: {funding_tx.outputs[0].script_pubkey.to_hex()[:64]}...")

        # 4. Detect the script type of the funding UTXO and sign with the correct logic.
        script_pubkey_hex = actual_output.scriptpubkey_hex
        print(f"[SIGN] Detected script pubkey: {script_pubkey_hex}")

        if script_pubkey_hex.startswith("0014"):
            print(f"[SIGN] Detected P2WPKH UTXO. Signing with SegWit logic.")
            funding_priv = origin_of_funds_private_key
            funding_pub = funding_priv.get_public_key()
            pub_hex = funding_pub.to_hex()
            print(f"[SIGN_DEBUG] Generated public key for signing: {pub_hex}")
            print(f"[SIGN_DEBUG] Public key length: {len(pub_hex) // 2} bytes. (33 bytes means compressed)")
            
            # Calculate script for P2WPKH
            pkh = hashlib.new('ripemd160', hashlib.sha256(bytes.fromhex(pub_hex)).digest()).digest()
            script_code = Script(['OP_DUP', 'OP_HASH160', pkh.hex(), 'OP_EQUALVERIFY', 'OP_CHECKSIG'])
            prevout_amount = initial_amount_of_satoshis
            
            # Sign using the standard method
            funding_sig = funding_priv.sign_segwit_input(funding_tx, 0, script_code, prevout_amount)
            
            # Handle different return types and ensure proper DER format
            if isinstance(funding_sig, str):
                # If it's a hex string, convert to bytes
                funding_sig = bytes.fromhex(funding_sig)
            elif not isinstance(funding_sig, bytes):
                # If it's neither string nor bytes, something is wrong
                raise Exception(f"Unexpected signature type: {type(funding_sig)}")
            
            # Ensure we have a valid signature
            if not funding_sig or len(funding_sig) == 0:
                raise Exception("Empty signature generated")
            
            # Debug: Print signature details
            print(f"[SIGN_DEBUG] Raw signature length: {len(funding_sig)} bytes")
            print(f"[SIGN_DEBUG] Raw signature hex: {funding_sig.hex()}")
            
            # Check DER format and SIGHASH_ALL byte
            # DER format should start with 0x30 and have proper structure
            if len(funding_sig) > 0 and funding_sig[0] == 0x30:
                # It's already in DER format
                # Check if it needs SIGHASH_ALL byte (0x01) at the end
                if funding_sig[-1] != 0x01:
                    funding_sig = funding_sig + b'\x01'
                    print(f"[SIGN_DEBUG] Added SIGHASH_ALL byte, final length: {len(funding_sig)}")
            else:
                # Not in DER format, might be raw r,s values
                # Try to construct proper DER encoding
                if len(funding_sig) == 64:  # Raw r,s signature (32 bytes each)
                    r = funding_sig[:32]
                    s = funding_sig[32:]
                    
                    # Remove leading zeros from r and s
                    r = r.lstrip(b'\x00')
                    s = s.lstrip(b'\x00')
                    
                    # Add 0x00 padding if high bit is set (to maintain positive number)
                    if r[0] >= 0x80:
                        r = b'\x00' + r
                    if s[0] >= 0x80:
                        s = b'\x00' + s
                    
                    # Construct DER format
                    der_sig = b'\x30' + bytes([len(r) + len(s) + 4])
                    der_sig += b'\x02' + bytes([len(r)]) + r
                    der_sig += b'\x02' + bytes([len(s)]) + s
                    der_sig += b'\x01'  # SIGHASH_ALL
                    
                    funding_sig = der_sig
                    print(f"[SIGN_DEBUG] Converted to DER format, length: {len(funding_sig)}")
                else:
                    # Unknown format, add SIGHASH_ALL if not present
                    if funding_sig[-1] != 0x01:
                        funding_sig = funding_sig + b'\x01'
            
            print(f"[SIGN_DEBUG] Final signature hex: {funding_sig.hex()}")
            
            # Add witness with signature and public key (convert bytes to hex string)
            funding_sig_hex = funding_sig.hex() if isinstance(funding_sig, bytes) else funding_sig
            funding_tx.witnesses = [TxWitnessInput([funding_sig_hex, pub_hex])]
            print(f"[SIGN] Added P2WPKH witness for funding_tx (signature: {len(funding_sig_hex)//2} bytes, pubkey: {len(pub_hex)//2} bytes)")

        elif script_pubkey_hex.startswith("5120"):
            print(f"[SIGN] Detected Taproot UTXO. Signing with Taproot logic.")
            prevout_script = Script.from_raw(script_pubkey_hex)
            prevout_amount = initial_amount_of_satoshis
            funding_sig = origin_of_funds_private_key.sign_taproot_input(funding_tx, 0, [prevout_script], [prevout_amount], script_path=False)
            funding_tx.witnesses = [TxWitnessInput([funding_sig])]
            print(f"[SIGN] Added Taproot key-path witness for funding_tx.")

        else:
            raise Exception(f"Unsupported funding UTXO script type for signing: {script_pubkey_hex}")

        # 5. Calculate the correct TX ID for the signed transaction
        # IMPORTANT: Use the library's get_txid() method which correctly handles SegWit
        # The get_txid() method calculates WITHOUT witness data, which is what we need
        new_funding_txid = funding_tx.get_txid()
        
        # Also serialize for broadcast
        funding_tx_hex = funding_tx.to_bytes(has_segwit=True).hex()
        
        print(f"[NO_FAUCET] Wrapping tx ID (calculated): {new_funding_txid}")
        
        try:
            print(f"[NO_FAUCET] Broadcasting wrapping tx (length={len(funding_tx_hex)})...")
            
            # Save wrapper TX to file for later use
            wrapper_tx_path = f"prover_files/{setup_uuid}/wrapper_tx.hex"
            os.makedirs(os.path.dirname(wrapper_tx_path), exist_ok=True)
            with open(wrapper_tx_path, 'w') as f:
                f.write(funding_tx_hex)
            print(f"[NO_FAUCET] Saved wrapper TX to {wrapper_tx_path}")
            
            # Also save to /tmp for backward compatibility
            with open("/tmp/funding_tx.hex", "w") as f:
                f.write(funding_tx_hex)
            
            self.broadcast_transaction_service(transaction=funding_tx_hex)
            print(f"[NO_FAUCET] Successfully broadcasted: {new_funding_txid}")
            
            # 6. UPDATE the DTO with the NEW funding txid, index, AND AMOUNT
            bitvmx_protocol_setup_properties_dto.funding_tx_id = new_funding_txid
            bitvmx_protocol_setup_properties_dto.funding_index = 0
            
            # CRITICAL: Update the amount to match the actual wrapping tx output
            # The wrapping tx has a fee deducted, so the output is less than the input
            new_funding_amount = funding_tx.outputs[0].amount
            bitvmx_protocol_setup_properties_dto.funding_amount_of_satoshis = new_funding_amount
            
            # CRITICAL: Also update _original_funding to avoid assertion error in optimized generator
            # The generator checks that funding_amount hasn't been mutated, so we need to update both
            if hasattr(bitvmx_protocol_setup_properties_dto, '_original_funding'):
                bitvmx_protocol_setup_properties_dto._original_funding = int(new_funding_amount)
                print(f"[REFACTOR] Updated _original_funding to {new_funding_amount}")
            
            # Also update _original_stepfee if it exists
            if hasattr(bitvmx_protocol_setup_properties_dto, '_original_stepfee'):
                bitvmx_protocol_setup_properties_dto._original_stepfee = int(bitvmx_protocol_setup_properties_dto.step_fees_satoshis)
                print(f"[REFACTOR] Updated _original_stepfee to {bitvmx_protocol_setup_properties_dto.step_fees_satoshis}")
            
            print(f"[REFACTOR] Updated DTO with new funding_tx_id={new_funding_txid}, index=0, amount={new_funding_amount}")
            
            # Wait for propagation and verify the amount from chain
            import httpx
            import time as time_module
            max_retries = 8
            retry_delay = 5
            print(f"[NO_FAUCET] Waiting for tx {new_funding_txid} to propagate...")
            for retry in range(max_retries):
                time_module.sleep(retry_delay)
                try:
                    check_url = f"https://mutinynet.com/api/tx/{new_funding_txid}"
                    with httpx.Client(timeout=10) as client:
                        response = client.get(check_url)
                        if response.status_code == 200:
                            print(f"[NO_FAUCET] Confirmed in mempool after {retry+1} retries")
                            
                            # Double-check the amount from chain
                            tx_data = response.json()
                            if tx_data and 'vout' in tx_data and len(tx_data['vout']) > 0:
                                chain_amount = tx_data['vout'][0]['value']
                                if chain_amount != new_funding_amount:
                                    print(f"[AMOUNT_FIX] Chain amount {chain_amount} differs from calculated {new_funding_amount}, using chain value")
                                    bitvmx_protocol_setup_properties_dto.funding_amount_of_satoshis = chain_amount
                                    new_funding_amount = chain_amount
                                    # Update _original_funding as well
                                    if hasattr(bitvmx_protocol_setup_properties_dto, '_original_funding'):
                                        bitvmx_protocol_setup_properties_dto._original_funding = int(chain_amount)
                            break
                        print(f"[NO_FAUCET] Not yet in mempool, retry {retry+1}/{max_retries}")
                except Exception as e:
                    print(f"[NO_FAUCET] Check error: {e}")

        except Exception as e:
            error_msg = str(e).lower()
            known_already = any(k in error_msg for k in ["already", "already known", "already in block chain", "in chain", "known transaction"])
            if known_already:
                print(f"[NO_FAUCET] Tx already known/on-chain: {new_funding_txid}")
            else:
                # Fallback idempotency check: if broadcast fails but tx is present, treat as success
                try:
                    import httpx
                    check_url = f"https://mutinynet.com/api/tx/{new_funding_txid}"
                    with httpx.Client(timeout=10) as client:
                        r = client.get(check_url)
                        if r.status_code == 200:
                            print(f"[NO_FAUCET] Tx found via API after broadcast error; treating as success: {new_funding_txid}")
                        else:
                            print(f"[NO_FAUCET] Broadcast error and tx not found (status={r.status_code}): {e}")
                            raise
                except Exception:
                    print(f"[NO_FAUCET] Broadcast error and tx not found: {e}")
                    raise
        
        # 6b. Refresh verifier-side DTOs with the updated wrapped funding UTXO
        print("[NO_FAUCET] Refreshing verifier DTOs with wrapped funding UTXO...")
        for verifier_uuid, verifier_value in verifier_address_dict.items():
            url = f"{verifier_value}/public_keys"
            headers = {"accept": "application/json", "Content-Type": "application/json"}
            # Use model_dump() instead of deprecated dict()
            if hasattr(bitvmx_protocol_setup_properties_dto, 'model_dump'):
                data = {"bitvmx_protocol_setup_properties_dto": bitvmx_protocol_setup_properties_dto.model_dump()}
            else:
                # Fallback for older pydantic versions
                data = {"bitvmx_protocol_setup_properties_dto": bitvmx_protocol_setup_properties_dto.model_dump() if hasattr(bitvmx_protocol_setup_properties_dto, 'model_dump') else bitvmx_protocol_setup_properties_dto.dict()}
            try:
                resp = requests.post(url, headers=headers, json=data, timeout=120)
                if resp.status_code == 200:
                    print(f"[NO_FAUCET] Verifier DTO refreshed: {verifier_uuid}")
                else:
                    print(f"[NO_FAUCET] Verifier DTO refresh failed ({resp.status_code}): {resp.text[:200]}")
            except Exception as e:
                print(f"[NO_FAUCET] Verifier DTO refresh error for {verifier_uuid}: {e}")

        # 7. CRITICAL: After wrapping, regenerate ALL transactions with the new funding
        print("[REGENERATE] Regenerating all transactions with new wrapped funding...")
        print(f"[REGENERATE] New funding: txid={new_funding_txid}, amount={new_funding_amount}")
        
        # Verify scripts haven't changed
        if initial_fingerprint and hasattr(bitvmx_protocol_setup_properties_dto.bitvmx_bitcoin_scripts_dto, 'tree_fingerprint'):
            current_fingerprint = bitvmx_protocol_setup_properties_dto.bitvmx_bitcoin_scripts_dto.tree_fingerprint
            if current_fingerprint != initial_fingerprint:
                print(f"[CRITICAL ERROR] Script fingerprint changed!")
                print(f"  Initial: {initial_fingerprint}")
                print(f"  Current: {current_fingerprint}")
                raise ValueError("Script fingerprint mismatch - scripts were regenerated unexpectedly")
            print(f"[REGENERATE] Script fingerprint verified: {current_fingerprint}")
        
        # Use the same single_generator instance to regenerate transactions
        # This ensures consistency in script generation
        bitvmx_protocol_setup_properties_dto.bitvmx_transactions_dto = single_generator(
            bitvmx_protocol_setup_properties_dto=bitvmx_protocol_setup_properties_dto,
        )
        print("[REGENERATE] All transactions regenerated with wrapped funding")
        
        # No need to call rerate_and_relink anymore since we regenerated transactions
        print("[TRANSACTIONS] All transactions regenerated with correct funding: " + str(time() - init_time))
        
        # 7b. Save the regenerated transactions to signed_transactions.json
        from datetime import datetime
        
        signed_txs_dir = f"prover_files/{setup_uuid}"
        if not os.path.exists(signed_txs_dir):
            os.makedirs(signed_txs_dir)
        signed_txs_file = f"{signed_txs_dir}/signed_transactions.json"
        
        # Determine setup type based on ELF filename
        setup_type = "UNKNOWN"
        if "option_registration" in elf_file_name.lower():
            setup_type = "OPTION_REGISTRATION"
        elif "option_purchase" in elf_file_name.lower() or "buy" in elf_file_name.lower():
            setup_type = "OPTION_PURCHASE"
        elif "settlement" in elf_file_name.lower() or "settle" in elf_file_name.lower():
            setup_type = "OPTION_SETTLEMENT"
        
        # Save setup metadata for easier tracking
        metadata_file = f"{signed_txs_dir}/setup_metadata.json"
        metadata = {
            "setup_uuid": setup_uuid,
            "setup_type": setup_type,
            "elf_file_name": elf_file_name,
            "created_at": datetime.now().isoformat(),
            "funding_tx_id": new_funding_txid,
            "funding_index": 0,  # After wrapping, it's always index 0
            "funding_amount": bitvmx_protocol_setup_properties_dto.funding_amount_of_satoshis,
            "input_hex": bitvmx_protocol_setup_properties_dto.input_hex if hasattr(bitvmx_protocol_setup_properties_dto, 'input_hex') else None,
            "input_description": self._describe_input(setup_type, bitvmx_protocol_setup_properties_dto.input_hex if hasattr(bitvmx_protocol_setup_properties_dto, 'input_hex') else None),
            "max_amount_of_steps": bitvmx_protocol_setup_properties_dto.bitvmx_protocol_properties_dto.max_amount_of_steps,
            "prover_address": bitvmx_protocol_setup_properties_dto.prover_destination_address,
            "verifier_address": bitvmx_protocol_setup_properties_dto.verifier_destination_address
        }
        with open(metadata_file, 'w') as f:
            json.dump(metadata, f, indent=2)
        print(f"[PERSISTENCE] Setup metadata saved to {metadata_file}")
        
        # Convert transactions DTO to dict for JSON serialization
        tx_dto = bitvmx_protocol_setup_properties_dto.bitvmx_transactions_dto
        signed_transactions = {}
        
        # Add all transaction types to the dict
        if hasattr(tx_dto, 'funding_tx') and tx_dto.funding_tx:
            signed_transactions['funding_tx'] = tx_dto.funding_tx.to_hex() if hasattr(tx_dto.funding_tx, 'to_hex') else str(tx_dto.funding_tx)
        if hasattr(tx_dto, 'hash_result_tx') and tx_dto.hash_result_tx:
            signed_transactions['hash_result_tx'] = tx_dto.hash_result_tx.to_hex() if hasattr(tx_dto.hash_result_tx, 'to_hex') else str(tx_dto.hash_result_tx)
        if hasattr(tx_dto, 'trigger_protocol_tx') and tx_dto.trigger_protocol_tx:
            signed_transactions['trigger_protocol_tx'] = tx_dto.trigger_protocol_tx.to_hex() if hasattr(tx_dto.trigger_protocol_tx, 'to_hex') else str(tx_dto.trigger_protocol_tx)
        if hasattr(tx_dto, 'search_hash_tx_list') and tx_dto.search_hash_tx_list:
            signed_transactions['search_hash_tx_list'] = [tx.to_hex() if hasattr(tx, 'to_hex') else str(tx) for tx in tx_dto.search_hash_tx_list]
        if hasattr(tx_dto, 'search_choice_tx_list') and tx_dto.search_choice_tx_list:
            signed_transactions['search_choice_tx_list'] = [tx.to_hex() if hasattr(tx, 'to_hex') else str(tx) for tx in tx_dto.search_choice_tx_list]
        if hasattr(tx_dto, 'read_search_hash_tx_list') and tx_dto.read_search_hash_tx_list:
            signed_transactions['read_search_hash_tx_list'] = [tx.to_hex() if hasattr(tx, 'to_hex') else str(tx) for tx in tx_dto.read_search_hash_tx_list]
        if hasattr(tx_dto, 'read_search_choice_tx_list') and tx_dto.read_search_choice_tx_list:
            signed_transactions['read_search_choice_tx_list'] = [tx.to_hex() if hasattr(tx, 'to_hex') else str(tx) for tx in tx_dto.read_search_choice_tx_list]
        if hasattr(tx_dto, 'trigger_trace_challenge_tx') and tx_dto.trigger_trace_challenge_tx:
            signed_transactions['trigger_trace_challenge_tx'] = tx_dto.trigger_trace_challenge_tx.to_hex() if hasattr(tx_dto.trigger_trace_challenge_tx, 'to_hex') else str(tx_dto.trigger_trace_challenge_tx)
            
        # Save to JSON file
        with open(signed_txs_file, 'w') as f:
            json.dump(signed_transactions, f, indent=2)
        print(f"[PERSISTENCE] Signed transactions saved to {signed_txs_file}")

        # 8. Generate signatures for the regenerated transactions
        print("[SIGNATURES] Generating signatures for regenerated transactions...")
        generate_signatures_service = self.generate_signatures_service_class(
            private_key=prover_destroyed_private_key, 
            destroyed_public_key=unspendable_public_key
        )
        
        bitvmx_signatures_dto = generate_signatures_service(
            bitvmx_protocol_setup_properties_dto=bitvmx_protocol_setup_properties_dto,
        )
        print("[SIGNATURES] Signatures generated: " + str(time() - init_time))

        verifier_signatures_dto_dict = {}
        for verifier_uuid, verifier_value in verifier_address_dict.items():
            url = f"{verifier_value}/signatures"
            headers = {"accept": "application/json", "Content-Type": "application/json"}
            data = {
                "setup_uuid": setup_uuid,
                "prover_signatures_dto": bitvmx_signatures_dto.prover_signatures_dto.model_dump(),
            }
            signatures_response = requests.post(url, headers=headers, json=data, timeout=300)
            if signatures_response.status_code != 200:
                raise Exception(f"Signatures exchange failed with verifier {verifier_uuid}: {signatures_response.status_code} - {signatures_response.text}")

            signatures_response_json = signatures_response.json()
            bitvmx_verifier_signatures_dto = BitVMXVerifierSignaturesDTO(
                **signatures_response_json["verifier_signatures_dto"]
            )
            verifier_signatures_dto_dict[verifier_uuid] = bitvmx_verifier_signatures_dto
        print("Verifier signatures sent: " + str(time() - init_time))

        prover_signatures_dto = bitvmx_signatures_dto.verifier_signatures_dto
        bitvmx_protocol_prover_dto = BitVMXProtocolProverDTO(
            prover_public_key=prover_destroyed_public_key.to_hex(),
            verifier_public_keys=verifier_public_keys_dict,
            prover_signatures_dto=prover_signatures_dto,
            verifier_signatures_dtos=verifier_signatures_dto_dict,
        )
        bitvmx_protocol_prover_private_dto = BitVMXProtocolProverPrivateDTO(
            winternitz_private_key=winternitz_private_key.to_bytes().hex(),
            prover_signature_private_key=prover_signature_private_key,
        )

        # Persist all DTOs with the final, correct state
        # Use update method to save the modified DTO with wrapping tx info
        self.bitvmx_protocol_setup_properties_dto_persistence.update(
            bitvmx_protocol_setup_properties_dto=bitvmx_protocol_setup_properties_dto
        )
        self.bitvmx_protocol_prover_private_dto_persistence.create(
            setup_uuid=setup_uuid,
            bitvmx_protocol_prover_private_dto=bitvmx_protocol_prover_private_dto,
        )
        self.bitvmx_protocol_prover_dto_persistence.create(
            setup_uuid=setup_uuid, bitvmx_protocol_prover_dto=bitvmx_protocol_prover_dto
        )
        print("[PERSISTENCE] All setup DTOs saved with final state.")
        
        print(f"[NO_FAUCET] Setup completed with wrapped funding_tx: {new_funding_txid}")
        return setup_uuid
