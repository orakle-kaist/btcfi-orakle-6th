import secrets
import uuid
from time import time
from typing import List
import logging
import json

import httpx
from bitcoinutils.keys import PrivateKey
from bitcoinutils.keys import PrivateKey as BTCPrivateKey
import binascii
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
from prover_app.domain.persistences.interfaces.bitvmx_protocol_setup_properties_dto_persistence_interface import (
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
        funding_amount_of_satoshis: int = None,  # 추가: 사용할 금액 지정
        # 옵션 관련 파라미터 (선택적)
        option_type: str = None,
        strike_price: float = None,
        expiry_timestamp: int = None,
        premium_sats: int = None,
    ) -> str:
        # Get logger for this process
        logger = logging.getLogger(__name__)
        setup_uuid = str(uuid.uuid4())
        prover_uuid = str(uuid.uuid4())
        init_time = time()
        
        # Debug logging
        logger.debug(f"setup_uuid: {setup_uuid}")
        print(f"[DEBUG] prover_signature_public_key: '{prover_signature_public_key}'")
        print(f"[DEBUG] prover_signature_public_key type: {type(prover_signature_public_key)}")
        print(f"[DEBUG] prover_signature_public_key length: {len(prover_signature_public_key) if prover_signature_public_key else 0}")
        print(f"[DEBUG] prover_destination_address: '{prover_destination_address}'")

        funding_tx = self.transaction_info_service(tx_id=funding_tx_id)
        target_output = None
        for output in funding_tx.outputs:
            if output.index == funding_index:
                target_output = output
                break
        
        if target_output is None:
            raise Exception(f"Output with index {funding_index} not found in transaction {funding_tx_id}")
        
        # 필요한 최소 수수료 계산 (16 steps 기준)
        # Hash + Choice 트랜잭션 수: 2 * max_amount_of_steps
        # 추가 트랜잭션들을 위한 여유분 포함
        min_required_fees = step_fees_satoshis * (2 * max_amount_of_steps + 10)
        print(f"[DEBUG] Minimum required fees for {max_amount_of_steps} steps: {min_required_fees} satoshis")
        
        # 사용할 금액 결정: 지정된 금액 또는 전체 UTXO 금액
        if funding_amount_of_satoshis is not None:
            # 지정된 금액 사용
            if funding_amount_of_satoshis < min_required_fees:
                raise Exception(f"Funding amount {funding_amount_of_satoshis} is less than minimum required {min_required_fees} satoshis")
            initial_amount_of_satoshis = funding_amount_of_satoshis
            # 사용 가능한 금액 확인
            if initial_amount_of_satoshis > target_output.value:
                raise Exception(f"Requested amount {funding_amount_of_satoshis} exceeds available UTXO value {target_output.value}")
        else:
            # 전체 UTXO 사용
            if target_output.value < min_required_fees:
                raise Exception(f"UTXO value {target_output.value} is less than minimum required {min_required_fees} satoshis")
            initial_amount_of_satoshis = target_output.value
        
        print(f"[DEBUG] Using initial_amount_of_satoshis: {initial_amount_of_satoshis}")
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
            url = f"{verifier}/api/v1/setup"
            headers = {"accept": "application/json", "Content-Type": "application/json"}
            data = {"setup_uuid": setup_uuid, "network": common_protocol_properties.network.value}
            
            print(f"[DEBUG] Sending async request to verifier: {url}")
            async with httpx.AsyncClient(timeout=120.0) as client:
                response = await client.post(url, headers=headers, json=data)
            print(f"[DEBUG] Verifier response: {response.status_code}")
            if response.status_code == 200:
                response_json = response.json()
                verifier_destroyed_public_key_hex = response_json["public_key"]
                verifier_signature_public_key_hex = response_json["verifier_signature_public_key"]
                verifier_destination_address = response_json["verifier_destination_address"]
                public_keys.append(verifier_destroyed_public_key_hex)
                signatures_public_keys_dict[current_uuid] = verifier_destroyed_public_key_hex
            else:
                raise Exception("Some error ocurred with the setup call to the verifier")

        winternitz_private_key = PrivateKey(b=secrets.token_bytes(32))

        unspendable_public_key = None
        seed_unspendable_public_key = ""
        # Use provided prover signature private key instead of random
        prover_destroyed_private_key = PrivateKey.from_bytes(binascii.unhexlify(prover_signature_private_key))
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
                break
            except IndexError:
                # If IndexError, regenerate with same provided key
                prover_destroyed_private_key = PrivateKey.from_bytes(binascii.unhexlify(prover_signature_private_key))
                prover_destroyed_public_key = prover_destroyed_private_key.get_public_key()
                public_keys[-1] = prover_destroyed_public_key.to_hex()

        generate_prover_public_keys_service = self.generate_prover_public_keys_service_class(
            winternitz_private_key
        )
        logger.info(f"[{setup_uuid}] Public keys generated. Time elapsed: {time() - init_time:.2f}s")
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
            url = f"{verifier_value}/api/v1/public_keys"
            headers = {"accept": "application/json", "Content-Type": "application/json"}
            
            logger.info(f"[{setup_uuid}] Preparing to send public_keys request to verifier {verifier_uuid}")
            logger.debug(f"[{setup_uuid}] Verifier URL: {url}")
            logger.debug(f"[{setup_uuid}] prover_signature_public_key: '{bitvmx_protocol_setup_properties_dto.prover_signature_public_key}'")
            
            data = {
                "bitvmx_protocol_setup_properties_dto": bitvmx_protocol_setup_properties_dto.dict(),
            }

            try:
                logger.info(f"[{setup_uuid}] Sending POST request to verifier...")
                client = httpx.AsyncClient()
                try:
                    public_keys_response = await client.post(url, headers=headers, json=data, timeout=120.0)
                    
                    logger.info(f"[{setup_uuid}] Received response: status={public_keys_response.status_code}")
                    
                    if public_keys_response.status_code != 200:
                        logger.error(f"[{setup_uuid}] Verifier returned error: {public_keys_response.status_code}")
                        logger.error(f"[{setup_uuid}] Response body: {public_keys_response.text[:500]}")
                        raise Exception(f"Verifier call failed: {public_keys_response.status_code}")
                    
                    logger.info(f"[{setup_uuid}] Parsing JSON response...")
                    public_keys_response_json = public_keys_response.json()
                    logger.info(f"[{setup_uuid}] JSON parsed successfully, keys: {list(public_keys_response_json.keys())}")
                    
                    # Extract verifier public key
                    logger.info(f"[{setup_uuid}] Extracting verifier_public_key...")
                    verifier_public_keys_dict[verifier_uuid] = public_keys_response_json[
                        "verifier_public_key"
                    ]
                    logger.info(f"[{setup_uuid}] verifier_public_key extracted successfully")
                    
                    # Parse Winternitz public keys DTO
                    logger.info(f"[{setup_uuid}] Creating BitVMXVerifierWinternitzPublicKeysDTO...")
                    winternitz_data = public_keys_response_json.get("bitvmx_verifier_winternitz_public_keys_dto")
                    if not winternitz_data:
                        logger.error(f"[{setup_uuid}] Missing bitvmx_verifier_winternitz_public_keys_dto in response")
                        logger.error(f"[{setup_uuid}] Full response: {json.dumps(public_keys_response_json, indent=2)[:1000]}")
                        raise Exception("Missing bitvmx_verifier_winternitz_public_keys_dto in verifier response")
                    
                    bitvmx_protocol_setup_properties_dto.bitvmx_verifier_winternitz_public_keys_dto = (
                        BitVMXVerifierWinternitzPublicKeysDTO(
                            **winternitz_data
                        )
                    )
                    logger.info(f"[{setup_uuid}] BitVMXVerifierWinternitzPublicKeysDTO created successfully")
                finally:
                    await client.aclose()
                
            except Exception as e:
                logger.error(f"[{setup_uuid}] FATAL ERROR while processing verifier response!")
                logger.error(f"[{setup_uuid}] Error type: {type(e).__name__}")
                logger.error(f"[{setup_uuid}] Error message: {str(e)}")
                if 'public_keys_response' in locals():
                    try:
                        logger.error(f"[{setup_uuid}] Raw response text: {public_keys_response.text[:1000]}")
                    except:
                        pass
                import traceback
                logger.error(f"[{setup_uuid}] Full traceback:\n{traceback.format_exc()}")
                raise
        logger.info(f"[{setup_uuid}] Verifier public keys generated. Time elapsed: {time() - init_time:.2f}s")
        
        # Scripts building #
        logger.info(f"[{setup_uuid}] STARTING: Bitcoin scripts generation...")
        logger.info(f"[{setup_uuid}] Script generator type: {type(self.bitvmx_bitcoin_scripts_generator_service).__name__}")
        script_start_time = time()
        
        # One call per verifier should be done
        try:
            logger.info(f"[{setup_uuid}] Calling script generator...")
            bitvmx_protocol_setup_properties_dto.bitvmx_bitcoin_scripts_dto = (
                self.bitvmx_bitcoin_scripts_generator_service(
                    bitvmx_protocol_setup_properties_dto=bitvmx_protocol_setup_properties_dto,
                )
            )
            logger.info(f"[{setup_uuid}] COMPLETED: Bitcoin scripts generation. Took: {time() - script_start_time:.2f}s, Total elapsed: {time() - init_time:.2f}s")
        except Exception as e:
            logger.error(f"[{setup_uuid}] Script generation failed: {e}")
            import traceback
            logger.error(f"[{setup_uuid}] Traceback:\n{traceback.format_exc()}")
            raise

        # We need to know the origin of the funds or change the signature to only sign the output (it's possible and gives more flexibility)
        origin_of_funds_public_key = origin_of_funds_private_key.get_public_key()
        
        # Transaction construction
        
        # One call per verifier should be done
        logger.info(f"[{setup_uuid}] STARTING: Transaction generation...")
        tx_start_time = time()
        bitvmx_protocol_setup_properties_dto.bitvmx_transactions_dto = (
            self.transaction_generator_from_public_keys_service(
                bitvmx_protocol_setup_properties_dto=bitvmx_protocol_setup_properties_dto,
            )
        )
        logger.info(f"[{setup_uuid}] COMPLETED: Transaction generation. Took: {time() - tx_start_time:.2f}s, Total elapsed: {time() - init_time:.2f}s")
        
        # Add change output to funding transaction if necessary
        origin_address = origin_of_funds_public_key.get_address()
        
        # Calculate change amount safely
        actual_utxo_value = target_output.value
        # The funding_amount already includes everything needed for the protocol
        total_needed = bitvmx_protocol_setup_properties_dto.funding_amount_of_satoshis + step_fees_satoshis
        
        logger.info(f"[{setup_uuid}] Change calculation: UTXO={actual_utxo_value}, total_needed={total_needed}")
        
        # Only calculate change if we have excess funds
        if actual_utxo_value > total_needed:
            change_amount = actual_utxo_value - total_needed
            logger.info(f"[{setup_uuid}] Change amount: {change_amount}")
            
            if change_amount > 546:  # Dust limit
                from bitcoinutils.transactions import TxOutput, TxInput
                change_output = TxOutput(
                    change_amount,
                    origin_address.to_script_pub_key()
                )
                # Add change output to funding transaction
                bitvmx_protocol_setup_properties_dto.bitvmx_transactions_dto.funding_tx.outputs.append(change_output)
            
                # Update hash_result_tx to use the new funding tx id
                new_funding_txid = bitvmx_protocol_setup_properties_dto.bitvmx_transactions_dto.funding_tx.get_txid()
                bitvmx_protocol_setup_properties_dto.bitvmx_transactions_dto.hash_result_tx.inputs[0] = TxInput(
                    new_funding_txid, 0
                )
            
                # Update trigger_protocol_tx to use the new hash_result_tx id
                new_hash_result_txid = bitvmx_protocol_setup_properties_dto.bitvmx_transactions_dto.hash_result_tx.get_txid()
                bitvmx_protocol_setup_properties_dto.bitvmx_transactions_dto.trigger_protocol_tx.inputs[0] = TxInput(
                    new_hash_result_txid, 0
                )
                
                # Update all search transactions
                previous_txid = bitvmx_protocol_setup_properties_dto.bitvmx_transactions_dto.trigger_protocol_tx.get_txid()
                for i in range(len(bitvmx_protocol_setup_properties_dto.bitvmx_transactions_dto.search_hash_tx_list)):
                    bitvmx_protocol_setup_properties_dto.bitvmx_transactions_dto.search_hash_tx_list[i].inputs[0] = TxInput(
                        previous_txid, 0
                    )
                    hash_tx_id = bitvmx_protocol_setup_properties_dto.bitvmx_transactions_dto.search_hash_tx_list[i].get_txid()
                    
                    bitvmx_protocol_setup_properties_dto.bitvmx_transactions_dto.search_choice_tx_list[i].inputs[0] = TxInput(
                        hash_tx_id, 0
                    )
                    previous_txid = bitvmx_protocol_setup_properties_dto.bitvmx_transactions_dto.search_choice_tx_list[i].get_txid()
                
                # Update trace_tx
                bitvmx_protocol_setup_properties_dto.bitvmx_transactions_dto.trace_tx.inputs[0] = TxInput(
                    previous_txid, 0
                )
        
        logger.info(f"[{setup_uuid}] Transactions built. Time elapsed: {time() - init_time:.2f}s")
        
        # Signature computation
        logger.info(f"[{setup_uuid}] STARTING: Signature generation...")
        sig_start_time = time()
        
        # One call per verifier should be done
        generate_signatures_service = self.generate_signatures_service_class(
            private_key=prover_destroyed_private_key, destroyed_public_key=unspendable_public_key
        )
        bitvmx_signatures_dto = generate_signatures_service(
            bitvmx_protocol_setup_properties_dto=bitvmx_protocol_setup_properties_dto,
        )
        logger.info(f"[{setup_uuid}] COMPLETED: Signature generation. Took: {time() - sig_start_time:.2f}s, Total elapsed: {time() - init_time:.2f}s")
        hash_result_signatures = [bitvmx_signatures_dto.hash_result_signature]
        search_hash_signatures = [
            [signature] for signature in bitvmx_signatures_dto.search_hash_signatures
        ]
        trace_signatures = [bitvmx_signatures_dto.trace_signature]
        # execution_challenge_signatures = [signatures_dict["execution_challenge_signature"]]
        # At this stage, we need to add a GET call to compute the verifiers signatures for the other ones protocols
        logger.info(f"[{setup_uuid}] STARTING: Verifier signatures exchange...")
        verifier_sig_start_time = time()
        verifier_signatures_dto_dict = {}
        for verifier_uuid, verifier_value in verifier_address_dict.items():
            url = f"{verifier_value}/api/v1/signatures"
            headers = {"accept": "application/json", "Content-Type": "application/json"}
            data = {
                "setup_uuid": setup_uuid,
                "prover_signatures_dto": bitvmx_signatures_dto.prover_signatures_dto.model_dump(),
                "bitvmx_protocol_setup_properties_dto": bitvmx_protocol_setup_properties_dto.model_dump(),
            }
            async with httpx.AsyncClient() as client:
                signatures_response = await client.post(url, headers=headers, json=data, timeout=120.0)
            if signatures_response.status_code != 200:
                raise Exception("Some error when exchanging the signatures")

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
        logger.info(f"[{setup_uuid}] COMPLETED: Verifier signatures exchange. Took: {time() - verifier_sig_start_time:.2f}s, Total elapsed: {time() - init_time:.2f}s")
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

        # Use actual UTXO value for signature
        actual_utxo_value = target_output.value
        funding_sig = origin_of_funds_private_key.sign_segwit_input(
            bitvmx_protocol_setup_properties_dto.bitvmx_transactions_dto.funding_tx,
            0,
            origin_of_funds_public_key.get_address().to_script_pub_key(),
            actual_utxo_value,
        )

        bitvmx_protocol_setup_properties_dto.bitvmx_transactions_dto.funding_tx.witnesses.append(
            TxWitnessInput([funding_sig, origin_of_funds_public_key.to_hex()])
        )

        self.broadcast_transaction_service(
            transaction=bitvmx_protocol_setup_properties_dto.bitvmx_transactions_dto.funding_tx.serialize()
        )
        logger.info(f"[{setup_uuid}] Funding transaction broadcasted. TXID: {bitvmx_protocol_setup_properties_dto.bitvmx_transactions_dto.funding_tx.get_txid()}")
        logger.info(f"[{setup_uuid}] Setup process completed. Total time: {time() - init_time:.2f}s")
        return setup_uuid
