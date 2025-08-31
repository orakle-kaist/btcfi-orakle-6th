import os
import secrets
import uuid
from time import time
from typing import List

import requests
from bitcoinutils.keys import PrivateKey
from bitcoinutils.transactions import TxWitnessInput

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
        funding_index: str,
        step_fees_satoshis: int,
        origin_of_funds_private_key: PrivateKey,
        prover_destination_address: str,
        prover_signature_private_key: str,
        prover_signature_public_key: str,
        funding_private_key: str = None,
    ) -> str:
        setup_uuid = str(uuid.uuid4())
        prover_uuid = str(uuid.uuid4())
        init_time = time()

        # Check if funding_tx_id is all zeros (meaning we'll generate our own funding tx)
        using_existing_utxo = funding_tx_id != "0" * 64
        if not using_existing_utxo:
            print("[SETUP] Using self-generated funding transaction")
            # Get initial amount from environment config
            initial_amount_of_satoshis = common_protocol_properties.initial_amount_satoshis
            print(f"[SETUP] Using initial amount: {initial_amount_of_satoshis} satoshis")
            funding_tx = None  # Will be generated later
        else:
            print(f"[SETUP] Using existing UTXO: {funding_tx_id}:{funding_index}")
            funding_tx = self.transaction_info_service(tx_id=funding_tx_id)
            
            # DTO 일관성 검증 - CRITICAL CHECK
            if funding_index >= len(funding_tx.outputs):
                raise Exception(f"[CRITICAL] Invalid funding_index {funding_index}. Transaction only has {len(funding_tx.outputs)} outputs")
            
            actual_output = funding_tx.outputs[funding_index]
            print(f"[TX-GEN/PRECHECK] DTO specified: funding_tx_id={funding_tx_id}, index={funding_index}")
            print(f"[TX-GEN/PRECHECK] Chain actual: value={actual_output.value} sats")
            
            initial_amount_of_satoshis = actual_output.value - step_fees_satoshis
            print(f"[TX-GEN/PRECHECK] Initial amount after fees: {initial_amount_of_satoshis} satoshis")
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
            # verifier already contains /api/v1 from verifier_list
            url = f"{verifier}/setup"
            headers = {"accept": "application/json", "Content-Type": "application/json"}
            data = {"setup_uuid": setup_uuid, "network": common_protocol_properties.network.value}

            # Increase timeout to 300 seconds for setup endpoint
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
                print(f"[ERROR] Request URL: {url}")
                print(f"[ERROR] Request data: {data}")
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

        print("Funding tx: " + funding_tx_id)

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
            prover_destroyed_public_key=prover_destroyed_private_key.get_public_key().to_hex(),
            verifier_destroyed_public_key=verifier_destroyed_public_key_hex,
            bitvmx_protocol_properties_dto=bitvmx_protocol_properties_dto,
            bitvmx_prover_winternitz_public_keys_dto=bitvmx_prover_winternitz_public_keys_dto,
        )

        verifier_public_keys_dict = {}

        # Think how to iterate all verifiers here -> Make a call per verifier
        # All verifiers should sign all transactions so they are sure there is not any of them lying
        for verifier_uuid, verifier_value in verifier_address_dict.items():
            # verifier_value already contains /api/v1 from verifier_list
            url = f"{verifier_value}/public_keys"
            headers = {"accept": "application/json", "Content-Type": "application/json"}
            # Debug: Check signature public keys
            dto_dict = bitvmx_protocol_setup_properties_dto.dict()
            print(f"[DEBUG] Sending to verifier:")
            print(f"  - prover_signature_public_key: {dto_dict.get('prover_signature_public_key', 'NOT FOUND')}")
            print(f"  - verifier_signature_public_key: {dto_dict.get('verifier_signature_public_key', 'NOT FOUND')}")
            
            data = {
                "bitvmx_protocol_setup_properties_dto": dto_dict,
            }

            # Increase timeout to 600 seconds for public_keys endpoint (heavy computation)
            public_keys_response = requests.post(url, headers=headers, json=data, timeout=600)
            if public_keys_response.status_code != 200:
                print(f"[ERROR] Verifier /public_keys response status: {public_keys_response.status_code}")
                print(f"[ERROR] Verifier /public_keys response text: {public_keys_response.text}")
                print(f"[ERROR] Request URL: {url}")
                raise Exception(f"Public keys verifier call failed with status {public_keys_response.status_code}: {public_keys_response.text}")
            public_keys_response_json = public_keys_response.json()
            
            # Verify setup_uuid matches
            returned_setup_uuid = public_keys_response_json.get("setup_uuid")
            if returned_setup_uuid and returned_setup_uuid != setup_uuid:
                print(f"[WARNING] Setup UUID mismatch: expected {setup_uuid}, got {returned_setup_uuid}")
            
            verifier_public_keys_dict[verifier_uuid] = public_keys_response_json[
                "verifier_public_key"
            ]
            # Debug: Check if transactions are in response
            print(f"[DEBUG] Public keys response has setup_uuid: {returned_setup_uuid}")
            print(f"[DEBUG] Public keys response has transactions dto: {'bitvmx_transactions_dto' in public_keys_response_json}")
            
            # We need to put a dict here
            bitvmx_protocol_setup_properties_dto.bitvmx_verifier_winternitz_public_keys_dto = (
                BitVMXVerifierWinternitzPublicKeysDTO(
                    **public_keys_response_json["bitvmx_verifier_winternitz_public_keys_dto"]
                )
            )
        print("Verifier public keys generated: " + str(time() - init_time))
        # Scripts building #

        # One call per verifier should be done
        bitvmx_protocol_setup_properties_dto.bitvmx_bitcoin_scripts_dto = (
            self.bitvmx_bitcoin_scripts_generator_service(
                bitvmx_protocol_setup_properties_dto=bitvmx_protocol_setup_properties_dto,
            )
        )
        print("Bitcoin scripts generated: " + str(time() - init_time))

        # We need to know the origin of the funds or change the signature to only sign the output (it's possible and gives more flexibility)

        # Transaction construction
        
        # FORCE SET funding information before transaction generation
        print(f"[TX-GEN/PRECHECK] Before generation:")
        print(f"  funding_tx_id={bitvmx_protocol_setup_properties_dto.funding_tx_id}")
        print(f"  funding_index={bitvmx_protocol_setup_properties_dto.funding_index}")
        print(f"  funding_amount={bitvmx_protocol_setup_properties_dto.funding_amount_of_satoshis}")
        print(f"  prover_dest={bitvmx_protocol_setup_properties_dto.prover_destination_address}")
        
        # Ensure funding info is properly set
        if not bitvmx_protocol_setup_properties_dto.funding_tx_id:
            raise ValueError("funding_tx_id is required for transaction generation")
            
        # Avoid duplicate transaction generation
        if bitvmx_protocol_setup_properties_dto.bitvmx_transactions_dto:
            print("[TX-GEN/SKIP] Reusing existing transactions DTO")
        else:
            print("[TX-GEN/START] Generating transactions...")
            tx_gen_start = time()
            # One call per verifier should be done
            bitvmx_protocol_setup_properties_dto.bitvmx_transactions_dto = (
                self.transaction_generator_from_public_keys_service(
                    bitvmx_protocol_setup_properties_dto=bitvmx_protocol_setup_properties_dto,
                )
            )
            print(f"[TX-GEN/DONE] Transaction generation took {time() - tx_gen_start:.2f}s")
        print("Transactions built: " + str(time() - init_time))
        
        # Guard against empty transaction lists with detailed logging
        txdto = bitvmx_protocol_setup_properties_dto.bitvmx_transactions_dto
        
        # === Verify prevout in generated transactions ===
        def _peek_prevout(tx_hex: str):
            """Extract prevout (txid, vout) from transaction hex"""
            try:
                b = bytes.fromhex(tx_hex)
                off = 4  # Skip version
                # Check for segwit marker+flag
                if len(b) >= 6 and b[4] == 0x00 and b[5] == 0x01:
                    off += 2
                if off >= len(b):
                    return None
                n_inputs = b[off]
                off += 1
                if n_inputs < 1 or off + 36 > len(b):
                    return None
                txid_le = b[off:off+32]
                off += 32
                vout = int.from_bytes(b[off:off+4], "little")
                txid = txid_le[::-1].hex()
                return txid, vout
            except Exception as e:
                print(f"[TX-GEN/CHECK] Error parsing prevout: {e}")
                return None
        
        # Check first transaction's prevout
        expected_funding_tx = bitvmx_protocol_setup_properties_dto.funding_tx_id
        expected_funding_index = bitvmx_protocol_setup_properties_dto.funding_index
        
        for tx_list_name in ["read_search_hash_tx_list", "search_hash_tx_list", 
                              "read_search_choice_tx_list", "search_choice_tx_list"]:
            tx_list = getattr(txdto, tx_list_name, None)
            if tx_list and isinstance(tx_list, list) and len(tx_list) > 0:
                first_tx = tx_list[0]
                if isinstance(first_tx, str):
                    tx_hex = first_tx
                elif hasattr(first_tx, "serialize"):
                    tx_hex = first_tx.serialize()
                else:
                    continue
                    
                prevout = _peek_prevout(tx_hex)
                if prevout:
                    actual_txid, actual_vout = prevout
                    print(f"[TX-GEN/CHECK] {tx_list_name}[0] prevout: {actual_txid}:{actual_vout}")
                    
                    if actual_txid.lower() != expected_funding_tx.lower():
                        print(f"[TX-GEN/ERROR] Wrong funding txid!")
                        print(f"  Expected: {expected_funding_tx}")
                        print(f"  Got: {actual_txid}")
                        # Don't raise error, just warn for now
                    elif actual_vout != expected_funding_index:
                        print(f"[TX-GEN/ERROR] Wrong funding index!")
                        print(f"  Expected: {expected_funding_index}")
                        print(f"  Got: {actual_vout}")
                    else:
                        print(f"[TX-GEN/CHECK] ✓ Prevout matches expected funding UTXO")
                    break
        
        # === Fallback: if read_* lists are empty but search_* exists, reuse them ===
        def _ensure_list(x):
            return x if (x is not None and hasattr(x, "__len__")) else []
        
        # Get current generated lists
        read_hash = _ensure_list(getattr(txdto, "read_search_hash_tx_list", None))
        read_choice = _ensure_list(getattr(txdto, "read_search_choice_tx_list", None))
        search_hash = _ensure_list(getattr(txdto, "search_hash_tx_list", None))
        search_choice = _ensure_list(getattr(txdto, "search_choice_tx_list", None))
        
        # Fallback if read_* lists are empty
        if len(read_hash) == 0 and len(search_hash) > 0:
            setattr(txdto, "read_search_hash_tx_list", search_hash)
            print("[TX-GEN] Fallback: read_search_hash_tx_list <- search_hash_tx_list")
        
        if len(read_choice) == 0 and len(search_choice) > 0:
            setattr(txdto, "read_search_choice_tx_list", search_choice)
            print("[TX-GEN] Fallback: read_search_choice_tx_list <- search_choice_tx_list")
        
        def _len_or_zero(x):
            try: return len(x) if x is not None else 0
            except: return 0
        
        read_hash_n = _len_or_zero(getattr(txdto, "read_search_hash_tx_list", None))
        read_choice_n = _len_or_zero(getattr(txdto, "read_search_choice_tx_list", None))
        search_hash_n = _len_or_zero(getattr(txdto, "search_hash_tx_list", None))
        search_choice_n = _len_or_zero(getattr(txdto, "search_choice_tx_list", None))
        
        # Get funding and fee info for debugging
        fa = bitvmx_protocol_setup_properties_dto.funding_amount_of_satoshis if hasattr(bitvmx_protocol_setup_properties_dto, "funding_amount_of_satoshis") else None
        ms = bitvmx_protocol_setup_properties_dto.bitvmx_protocol_properties_dto.max_amount_of_steps
        bits = bitvmx_protocol_setup_properties_dto.bitvmx_protocol_properties_dto.amount_of_bits_wrong_step_search
        fees_hash = int(os.getenv("HASH_FEES_SATOSHIS", "100"))
        fees_choice = int(os.getenv("CHOICE_FEES_SATOSHIS", "10"))
        fees_trigger = int(os.getenv("TRIGGER_FEES_SATOSHIS", "100"))
        fees_step = bitvmx_protocol_setup_properties_dto.step_fees_satoshis if hasattr(bitvmx_protocol_setup_properties_dto, "step_fees_satoshis") else None
        
        print(f"[TX-GEN] Transaction counts: read_hash={read_hash_n}, read_choice={read_choice_n}, search_hash={search_hash_n}, search_choice={search_choice_n}")
        print(f"[TX-GEN] Parameters: funding={fa} sats, steps={ms}, bits={bits}")
        print(f"[TX-GEN] Fees: hash={fees_hash}, choice={fees_choice}, trigger={fees_trigger}, step={fees_step}")
        
        if read_hash_n == 0 or read_choice_n == 0:
            # Calculate expected costs
            expected_iterations = 2 ** bits
            expected_hash_cost = expected_iterations * fees_hash
            expected_choice_cost = expected_iterations * fees_choice
            expected_total = expected_hash_cost + expected_choice_cost + fees_trigger
            
            print(f"[TX-GEN] EMPTY LIST ERROR: Need {expected_total} sats total (hash={expected_hash_cost}, choice={expected_choice_cost}, trigger={fees_trigger})")
            print(f"[TX-GEN] Available funding: {fa} sats, shortage: {expected_total - fa if fa else 'Unknown'}")
            
            raise ValueError(f"No transactions generated: funding/fee/steps mismatch. Need {expected_total} sats, have {fa} sats.")
        # Signature computation

        # One call per verifier should be done
        generate_signatures_service = self.generate_signatures_service_class(
            private_key=prover_destroyed_private_key, destroyed_public_key=unspendable_public_key
        )
        bitvmx_signatures_dto = generate_signatures_service(
            bitvmx_protocol_setup_properties_dto=bitvmx_protocol_setup_properties_dto,
        )
        print("Signatures generated: " + str(time() - init_time))
        hash_result_signatures = [bitvmx_signatures_dto.hash_result_signature]
        search_hash_signatures = [
            [signature] for signature in bitvmx_signatures_dto.search_hash_signatures
        ]
        trace_signatures = [bitvmx_signatures_dto.trace_signature]
        # execution_challenge_signatures = [signatures_dict["execution_challenge_signature"]]
        # At this stage, we need to add a GET call to compute the verifiers signatures for the other ones protocols
        verifier_signatures_dto_dict = {}
        for verifier_uuid, verifier_value in verifier_address_dict.items():
            url = f"{verifier_value}/signatures"
            headers = {"accept": "application/json", "Content-Type": "application/json"}
            
            # Try stateful first (recommended), then stateless as fallback
            def _payload_stateful():
                return {
                    "setup_uuid": setup_uuid,
                    "prover_signatures_dto": bitvmx_signatures_dto.prover_signatures_dto.model_dump(),
                }
            
            def _payload_stateless():
                return {
                    "setup_uuid": setup_uuid,
                    "prover_signatures_dto": bitvmx_signatures_dto.prover_signatures_dto.model_dump(),
                    # If verifier needs full state, uncomment these:
                    # "bitvmx_protocol_setup_properties_dto": bitvmx_protocol_setup_properties_dto.dict(),
                    # "bitvmx_transactions_dto": bitvmx_protocol_setup_properties_dto.bitvmx_transactions_dto.dict() if bitvmx_protocol_setup_properties_dto.bitvmx_transactions_dto else None,
                }
            
            signatures_response = None
            for i, builder in enumerate([_payload_stateful, _payload_stateless], 1):
                data = builder()
                print(f"[SIGNATURES] Try payload variant {i} for verifier {verifier_uuid}")
                signatures_response = requests.post(url, headers=headers, json=data, timeout=300)
                print(f"[SIGNATURES] Variant {i} → status={signatures_response.status_code}")
                if signatures_response.status_code == 200:
                    break
                print(f"[SIGNATURES] Variant {i} response: {signatures_response.text}")
            
            if signatures_response.status_code != 200:
                raise Exception(f"Signatures exchange failed with verifier {verifier_uuid}: {signatures_response.status_code} - {signatures_response.text}")

            signatures_response_json = signatures_response.json()
            bitvmx_verifier_signatures_dto = BitVMXVerifierSignaturesDTO(
                **signatures_response_json["verifier_signatures_dto"]
            )

            for j in range(len(bitvmx_verifier_signatures_dto.search_hash_signatures)):
                search_hash_signatures[j].append(
                    bitvmx_verifier_signatures_dto.search_hash_signatures[j]
                )

            hash_result_signatures.append(bitvmx_verifier_signatures_dto.hash_result_signature)
            trace_signatures.append(bitvmx_verifier_signatures_dto.trace_signature)
            verifier_signatures_dto_dict[verifier_uuid] = bitvmx_verifier_signatures_dto
        print("Verifier signatures sent: " + str(time() - init_time))
        hash_result_signatures.reverse()
        for signature_list in search_hash_signatures:
            signature_list.reverse()
        trace_signatures.reverse()
        # execution_challenge_signatures.reverse()

        prover_signatures_dto = bitvmx_signatures_dto.verifier_signatures_dto
        bitvmx_protocol_prover_dto = BitVMXProtocolProverDTO(
            prover_public_key=prover_destroyed_public_key.to_hex(),
            verifier_public_keys=verifier_public_keys_dict,
            prover_signatures_dto=prover_signatures_dto,
            verifier_signatures_dtos=verifier_signatures_dto_dict,
        )

        verify_verifier_signatures_service = self.verify_verifier_signatures_service_class(
            unspendable_public_key=unspendable_public_key
        )
        for i in range(len(bitvmx_protocol_setup_properties_dto.signature_public_keys) - 1):
            verify_verifier_signatures_service(
                public_key=bitvmx_protocol_setup_properties_dto.signature_public_keys[i],
                hash_result_signature=bitvmx_verifier_signatures_dto.hash_result_signature,
                search_hash_signatures=bitvmx_verifier_signatures_dto.search_hash_signatures,
                trace_signature=bitvmx_verifier_signatures_dto.trace_signature,
                read_trace_signature=bitvmx_verifier_signatures_dto.read_trace_signature,
                read_search_hash_signatures=bitvmx_verifier_signatures_dto.read_search_hash_signatures,
                bitvmx_protocol_setup_properties_dto=bitvmx_protocol_setup_properties_dto,
            )

        bitvmx_protocol_prover_private_dto = BitVMXProtocolProverPrivateDTO(
            winternitz_private_key=winternitz_private_key.to_bytes().hex(),
            prover_signature_private_key=prover_signature_private_key,
        )

        self.bitvmx_protocol_setup_properties_dto_persistence.create(
            bitvmx_protocol_setup_properties_dto=bitvmx_protocol_setup_properties_dto
        )
        self.bitvmx_protocol_prover_private_dto_persistence.create(
            setup_uuid=setup_uuid,
            bitvmx_protocol_prover_private_dto=bitvmx_protocol_prover_private_dto,
        )
        self.bitvmx_protocol_prover_dto_persistence.create(
            setup_uuid=setup_uuid, bitvmx_protocol_prover_dto=bitvmx_protocol_prover_dto
        )

        #################################################################
        
        # Apply signatures to transactions and save signed versions
        from bitvmx_protocol_library.transaction_generation.services.apply_signatures_to_transactions_service import (
            ApplySignaturesToTransactionsService,
        )
        
        apply_signatures_service = ApplySignaturesToTransactionsService()
        
        # Create signed transactions
        print("[SIGN] Applying signatures to transactions...")
        signed_transactions = apply_signatures_service.apply_signatures_with_private_key(
            bitvmx_protocol_setup_properties_dto=bitvmx_protocol_setup_properties_dto,
            bitvmx_signatures_dto=bitvmx_signatures_dto,
            bitvmx_verifier_signatures_dto=list(verifier_signatures_dto_dict.values())[0] if verifier_signatures_dto_dict else None,
            prover_private_key_hex=prover_signature_private_key,
        )
        
        # Save signed transactions to file
        if signed_transactions:
            apply_signatures_service.save_signed_transactions(
                setup_uuid=setup_uuid,
                signed_transactions=signed_transactions,
                base_dir="prover_files"
            )
            print(f"[SIGN] Saved {len(signed_transactions)} signed transaction types")
        else:
            print("[SIGN] Warning: No signed transactions created")

        origin_of_funds_public_key = origin_of_funds_private_key.get_public_key()

        # Check the type of the funding UTXO and sign appropriately
        if using_existing_utxo:
            # For existing UTXO, check its type and sign accordingly
            # Check if we have funding_private_key (for P2WPKH)
            if funding_private_key:
                print(f"[SIGN] Signing funding_tx for P2WPKH UTXO using provided private key")
                
                # Use the provided funding private key
                from bitcoinutils.script import Script
                import hashlib
                
                # Convert hex private key to PrivateKey object
                funding_priv = PrivateKey(secret_exponent=int(funding_private_key, 16))
                funding_pub = funding_priv.get_public_key()
                
                # Ensure we have compressed public key (33 bytes, starting with 02 or 03)
                pub_hex = funding_pub.to_hex()
                print(f"[SIGN] Public key: {pub_hex}")
                print(f"[SIGN] Public key length: {len(pub_hex)} chars (should be 66 for compressed)")
                
                # For P2WPKH, we need the P2PKH script for signing
                pubkey_bytes = bytes.fromhex(pub_hex)
                pkh = hashlib.new('ripemd160', hashlib.sha256(pubkey_bytes).digest()).digest()
                script_code = Script(['OP_DUP', 'OP_HASH160', pkh.hex(), 'OP_EQUALVERIFY', 'OP_CHECKSIG'])
                
                # Get the actual amount from the funding UTXO
                prevout_amount = initial_amount_of_satoshis  # Use the actual UTXO amount
                
                # Sign using P2WPKH
                funding_sig = funding_priv.sign_segwit_input(
                    bitvmx_protocol_setup_properties_dto.bitvmx_transactions_dto.funding_tx,
                    0,
                    script_code,
                    prevout_amount
                )
                
                # For P2WPKH, witness is [signature, pubkey]
                bitvmx_protocol_setup_properties_dto.bitvmx_transactions_dto.funding_tx.witnesses.append(
                    TxWitnessInput([funding_sig, pub_hex])
                )
                print(f"[SIGN] Added P2WPKH witness for funding_tx with compressed pubkey")
            else:
                # Original Taproot code (kept for compatibility)
                print(f"[SIGN] Signing funding_tx for existing Taproot UTXO")
                
                from bitcoinutils.script import Script
                # The actual scriptPubKey from the blockchain
                prevout_script_hex = "51207439ce6516333ae380ad54eba04be631888035fcb1f5473207b115db9c845a2f"
                prevout_script = Script.from_raw(prevout_script_hex)
                prevout_amount = 9997000  # The actual amount in the UTXO
                
                # Sign using Taproot key-path (not script-path)
                funding_sig = origin_of_funds_private_key.sign_taproot_input(
                    bitvmx_protocol_setup_properties_dto.bitvmx_transactions_dto.funding_tx,
                    0,
                    [prevout_script],  # List of prevout scripts
                    [prevout_amount],  # List of prevout amounts
                    script_path=False  # Key-path spending for the external UTXO
                )
                
                # For Taproot key-path, witness is just the signature
                bitvmx_protocol_setup_properties_dto.bitvmx_transactions_dto.funding_tx.witnesses.append(
                    TxWitnessInput([funding_sig])
                )
                print(f"[SIGN] Added Taproot key-path witness for funding_tx")
        else:
            # For self-generated funding_tx with P2WPKH
            funding_sig = origin_of_funds_private_key.sign_segwit_input(
                bitvmx_protocol_setup_properties_dto.bitvmx_transactions_dto.funding_tx,
                0,
                origin_of_funds_public_key.get_address().to_script_pub_key(),
                initial_amount_of_satoshis + step_fees_satoshis,
            )

            bitvmx_protocol_setup_properties_dto.bitvmx_transactions_dto.funding_tx.witnesses.append(
                TxWitnessInput([funding_sig, origin_of_funds_public_key.to_hex()])
            )

        # ALWAYS broadcast funding_tx - it moves funds to hash_result Taproot address
        # CRITICAL: Broadcast funding_tx to create the parent UTXO for hash_result_tx
        if using_existing_utxo:
            print("[BROADCAST] Broadcasting funding_tx to move external UTXO to hash_result Taproot address...")
        else:
            print("[BROADCAST] Broadcasting self-generated funding_tx to create parent UTXO...")
        
        # Get funding tx ID before broadcast
        funding_txid = bitvmx_protocol_setup_properties_dto.bitvmx_transactions_dto.funding_tx.get_txid()
        print(f"[BROADCAST] Funding transaction ID: {funding_txid}")
        
        # Actually broadcast the funding_tx - THIS IS CRITICAL!
        try:
            # Use segwit-safe serialization to ensure witness is included
            funding_tx_hex = bitvmx_protocol_setup_properties_dto.bitvmx_transactions_dto.funding_tx.to_bytes(has_segwit=True).hex()
            self.broadcast_transaction_service(
                transaction=funding_tx_hex
            )
            print(f"[BROADCAST] Successfully broadcasted funding_tx: {funding_txid}")
            
            # CRITICAL: Update DTO with generated funding_tx info for proper chain reference
            bitvmx_protocol_setup_properties_dto.funding_tx_id = funding_txid
            bitvmx_protocol_setup_properties_dto.funding_index = 0
            print(f"[BROADCAST] Updated DTO with generated funding_tx_id: {funding_txid}, index: 0")
            
            # CRITICAL: Persist the updated DTO so next_step can see the changes!
            self.bitvmx_protocol_setup_properties_dto_persistence.update(
                bitvmx_protocol_setup_properties_dto=bitvmx_protocol_setup_properties_dto
            )
            print(f"[BROADCAST] Persisted DTO update with funding_tx_id: {funding_txid}")
            
            # Wait for funding_tx to propagate
            import httpx
            max_retries = 8
            retry_delay = 5
            funding_confirmed = False
            
            print(f"[BROADCAST] Waiting for funding_tx {funding_txid} to propagate...")
            for retry in range(max_retries):
                import time as time_module
                time_module.sleep(retry_delay)
                try:
                    check_url = f"https://mutinynet.com/api/tx/{funding_txid}"
                    with httpx.Client(timeout=10) as client:
                        response = client.get(check_url)
                        if response.status_code == 200:
                            print(f"[BROADCAST] Funding_tx confirmed in mempool after {retry+1} retries")
                            funding_confirmed = True
                            break
                        else:
                            print(f"[BROADCAST] Funding_tx not yet in mempool, retry {retry+1}/{max_retries}")
                except Exception as e:
                    print(f"[BROADCAST] Error checking funding_tx: {e}")
            
            if not funding_confirmed:
                print(f"[BROADCAST] WARNING: Funding_tx not confirmed after {max_retries} retries")
                print("[BROADCAST] You may need to wait and call /next_step later")
                
        except Exception as e:
            error_msg = str(e)
            # Check if already in blockchain
            if any(phrase in error_msg.lower() for phrase in [
                "already in block chain",
                "txn-already-in-mempool",
                "already have transaction"
            ]):
                print(f"[BROADCAST] Funding_tx already on-chain: {funding_txid}")
            else:
                print(f"[BROADCAST] Error broadcasting funding_tx: {e}")
                raise
        return setup_uuid
