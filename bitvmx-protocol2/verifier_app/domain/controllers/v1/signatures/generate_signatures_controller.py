from time import time

from bitcoinutils.keys import PrivateKey
from bitcoinutils.setup import get_network

from bitvmx_protocol_library.bitvmx_protocol_definition.entities.bitvmx_protocol_verifier_dto import (
    BitVMXProtocolVerifierDTO,
)
from bitvmx_protocol_library.enums import BitcoinNetwork
from bitvmx_protocol_library.transaction_generation.entities.dtos.bitvmx_prover_signatures_dto import (
    BitVMXProverSignaturesDTO,
)
from bitvmx_protocol_library.transaction_generation.entities.dtos.bitvmx_verifier_signatures_dto import (
    BitVMXVerifierSignaturesDTO,
)
from verifier_app.domain.persistences.interfaces.bitvmx_protocol_setup_properties_dto_persistence_interface import (
    BitVMXProtocolSetupPropertiesDTOPersistenceInterface,
)
from verifier_app.domain.persistences.interfaces.bitvmx_protocol_verifier_dto_persistence_interface import (
    BitVMXProtocolVerifierDTOPersistenceInterface,
)
from verifier_app.domain.persistences.interfaces.bitvmx_protocol_verifier_private_dto_persistence_interface import (
    BitVMXProtocolVerifierPrivateDTOPersistenceInterface,
)


class GenerateSignaturesController:
    def __init__(
        self,
        bitvmx_bitcoin_scripts_generator_service,
        transaction_generator_from_public_keys_service,
        generate_signatures_service_class,
        verify_prover_signatures_service_class,
        common_protocol_properties,
        bitvmx_protocol_verifier_private_dto_persistence: BitVMXProtocolVerifierPrivateDTOPersistenceInterface,
        bitvmx_protocol_setup_properties_dto_persistence: BitVMXProtocolSetupPropertiesDTOPersistenceInterface,
        bitvmx_protocol_verifier_dto_persistence: BitVMXProtocolVerifierDTOPersistenceInterface,
    ):
        self.bitvmx_bitcoin_scripts_generator_service = bitvmx_bitcoin_scripts_generator_service
        self.transaction_generator_from_public_keys_service = (
            transaction_generator_from_public_keys_service
        )
        self.generate_signatures_service_class = generate_signatures_service_class
        self.verify_prover_signatures_service_class = verify_prover_signatures_service_class
        self.common_protocol_properties = common_protocol_properties
        self.bitvmx_protocol_verifier_private_dto_persistence = (
            bitvmx_protocol_verifier_private_dto_persistence
        )
        self.bitvmx_protocol_setup_properties_dto_persistence = (
            bitvmx_protocol_setup_properties_dto_persistence
        )
        self.bitvmx_protocol_verifier_dto_persistence = bitvmx_protocol_verifier_dto_persistence

    def __call__(
        self,
        setup_uuid: str,
        bitvmx_prover_signatures_dto: BitVMXProverSignaturesDTO,
        bitvmx_protocol_setup_properties_dto=None,  # Optional parameter from prover
    ) -> BitVMXVerifierSignaturesDTO:
        init_time = time()
        print(f"[SIGNATURES] Generate signatures for setup_uuid: {setup_uuid}")
        
        if self.common_protocol_properties.network == BitcoinNetwork.MUTINYNET:
            assert get_network() == "testnet"
        else:
            assert get_network() == self.common_protocol_properties.network.value

        bitvmx_protocol_verifier_private_dto = (
            self.bitvmx_protocol_verifier_private_dto_persistence.get(setup_uuid=setup_uuid)
        )
        
        if not bitvmx_protocol_verifier_private_dto:
            print(f"[ERROR] No private DTO found for setup_uuid: {setup_uuid}")
            raise ValueError(f"No private key found for setup_uuid: {setup_uuid}")
        
        if not bitvmx_protocol_verifier_private_dto.destroyed_private_key:
            print(f"[ERROR] Private DTO has no destroyed_private_key for setup_uuid: {setup_uuid}")
            raise ValueError(f"Private DTO has no destroyed_private_key for setup_uuid: {setup_uuid}")
        destroyed_private_key = PrivateKey(
            b=bytes.fromhex(bitvmx_protocol_verifier_private_dto.destroyed_private_key)
        )

        # Use the DTO from prover if provided, otherwise fetch from storage
        if bitvmx_protocol_setup_properties_dto is None:
            bitvmx_protocol_setup_properties_dto = (
                self.bitvmx_protocol_setup_properties_dto_persistence.get(setup_uuid=setup_uuid)
            )
        else:
            # Convert dict to DTO object if needed
            from bitvmx_protocol_library.bitvmx_protocol_definition.entities.bitvmx_protocol_setup_properties_dto import (
                BitVMXProtocolSetupPropertiesDTO,
            )
            if isinstance(bitvmx_protocol_setup_properties_dto, dict):
                bitvmx_protocol_setup_properties_dto = BitVMXProtocolSetupPropertiesDTO(**bitvmx_protocol_setup_properties_dto)
        
        # Apply fallback mapping if read_search_* lists are empty
        if bitvmx_protocol_setup_properties_dto.bitvmx_transactions_dto:
            txdto = bitvmx_protocol_setup_properties_dto.bitvmx_transactions_dto
            
            # Check and fallback for read_search_hash_tx_list
            if hasattr(txdto, 'read_search_hash_tx_list') and hasattr(txdto, 'search_hash_tx_list'):
                if not txdto.read_search_hash_tx_list and txdto.search_hash_tx_list:
                    txdto.read_search_hash_tx_list = txdto.search_hash_tx_list
                    print("[VERIFIER] Fallback: read_search_hash_tx_list <- search_hash_tx_list")
            
            # Check and fallback for read_search_choice_tx_list
            if hasattr(txdto, 'read_search_choice_tx_list') and hasattr(txdto, 'search_choice_tx_list'):
                if not txdto.read_search_choice_tx_list and txdto.search_choice_tx_list:
                    txdto.read_search_choice_tx_list = txdto.search_choice_tx_list
                    print("[VERIFIER] Fallback: read_search_choice_tx_list <- search_choice_tx_list")

        verify_prover_signatures_service = self.verify_prover_signatures_service_class(
            bitvmx_protocol_setup_properties_dto.unspendable_public_key
        )
        verify_prover_signatures_service(
            public_key=bitvmx_protocol_setup_properties_dto.prover_destroyed_public_key,
            bitvmx_prover_signatures_dto=bitvmx_prover_signatures_dto,
            bitvmx_protocol_setup_properties_dto=bitvmx_protocol_setup_properties_dto,
        )

        # Use standard version for now due to performance issues with optimized versions
        print("[VERIFIER SIGNATURES] Using standard signature generation")
        generate_signatures_service = self.generate_signatures_service_class(
            destroyed_private_key, bitvmx_protocol_setup_properties_dto.unspendable_public_key
        )
        
        bitvmx_signatures_dto = generate_signatures_service(
            bitvmx_protocol_setup_properties_dto=bitvmx_protocol_setup_properties_dto,
        )

        search_choice_signatures = []
        for i in range(len(bitvmx_signatures_dto.search_choice_signatures)):
            search_choice_signatures.append(
                [
                    bitvmx_signatures_dto.search_choice_signatures[i],
                    bitvmx_prover_signatures_dto.search_choice_signatures[i],
                ]
            )

        bitvmx_verifier_signatures_dto = bitvmx_signatures_dto.prover_signatures_dto
        # This should be sent in the API call
        verifier_signatures_dtos = {
            bitvmx_protocol_setup_properties_dto.uuid: bitvmx_verifier_signatures_dto
        }

        verifier_public_keys = {
            bitvmx_protocol_setup_properties_dto.uuid: bitvmx_protocol_setup_properties_dto.verifier_destroyed_public_key
        }

        bitvmx_protocol_verifier_dto = BitVMXProtocolVerifierDTO(
            prover_public_key=bitvmx_protocol_setup_properties_dto.prover_destroyed_public_key,
            verifier_public_keys=verifier_public_keys,
            prover_signatures_dto=bitvmx_prover_signatures_dto,
            verifier_signatures_dtos=verifier_signatures_dtos,
        )

        self.bitvmx_protocol_verifier_private_dto_persistence.delete_private_key(
            setup_uuid=setup_uuid
        )
        self.bitvmx_protocol_verifier_dto_persistence.create(
            setup_uuid=setup_uuid, bitvmx_protocol_verifier_dto=bitvmx_protocol_verifier_dto
        )
        print("Signatures controller total time: " + str(time() - init_time))
        return bitvmx_signatures_dto.verifier_signatures_dto
