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
    ) -> str:
        setup_uuid = str(uuid.uuid4())
        prover_uuid = str(uuid.uuid4())
        init_time = time()

        funding_tx = self.transaction_info_service(tx_id=funding_tx_id)
        initial_amount_of_satoshis = funding_tx.outputs[funding_index].value - step_fees_satoshis
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
            data = {
                "bitvmx_protocol_setup_properties_dto": bitvmx_protocol_setup_properties_dto.dict(),
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

        # One call per verifier should be done
        bitvmx_protocol_setup_properties_dto.bitvmx_transactions_dto = (
            self.transaction_generator_from_public_keys_service(
                bitvmx_protocol_setup_properties_dto=bitvmx_protocol_setup_properties_dto,
            )
        )
        print("Transactions built: " + str(time() - init_time))
        
        # Guard against empty transaction lists with detailed logging
        txdto = bitvmx_protocol_setup_properties_dto.bitvmx_transactions_dto
        
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

        origin_of_funds_public_key = origin_of_funds_private_key.get_public_key()

        funding_sig = origin_of_funds_private_key.sign_segwit_input(
            bitvmx_protocol_setup_properties_dto.bitvmx_transactions_dto.funding_tx,
            0,
            origin_of_funds_public_key.get_address().to_script_pub_key(),
            initial_amount_of_satoshis + step_fees_satoshis,
        )

        bitvmx_protocol_setup_properties_dto.bitvmx_transactions_dto.funding_tx.witnesses.append(
            TxWitnessInput([funding_sig, origin_of_funds_public_key.to_hex()])
        )

        # Skip broadcasting funding_tx as it's already on-chain
        print("[BROADCAST] Skipping funding_tx broadcast (already on-chain)")
        print(
            "Funding transaction ID: "
            + bitvmx_protocol_setup_properties_dto.bitvmx_transactions_dto.funding_tx.get_txid()
        )
        
        # Only broadcast new protocol transactions, not the funding tx
        # self.broadcast_transaction_service(
        #     transaction=bitvmx_protocol_setup_properties_dto.bitvmx_transactions_dto.funding_tx.serialize()
        # )
        return setup_uuid
