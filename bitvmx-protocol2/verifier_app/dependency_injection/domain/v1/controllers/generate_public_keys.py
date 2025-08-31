from dependency_injector import containers, providers

from bitvmx_protocol_library.bitvmx_protocol_definition.services.public_keys_generation.generate_verifier_public_keys_service import (
    GenerateVerifierPublicKeysService,
)
from bitvmx_protocol_library.config import common_protocol_properties
# Use optimized version with UTXO fix
from bitvmx_protocol_library.transaction_generation.services.transaction_generator_from_public_keys_service_optimized import (
    TransactionGeneratorFromPublicKeysServiceOptimized as TransactionGeneratorFromPublicKeysService,
)
print("[OPTIMIZED] Using optimized TransactionGeneratorFromPublicKeysService with UTXO fix")
from verifier_app.dependency_injection.persistences.bitvmx_protocol_setup_properties_dto_persistences import (
    BitVMXProtocolSetupPropertiesDTOPersistences,
)
from verifier_app.dependency_injection.persistences.bitvmx_protocol_verifier_private_dto_persistences import (
    BitVMXProtocolVerifierPrivateDTOPersistences,
)
# Use optimized controller to avoid serialization issues
try:
    from verifier_app.domain.controllers.v1.public_keys.generate_public_keys_controller_optimized import (
        GeneratePublicKeysControllerOptimized as GeneratePublicKeysController,
    )
    print("[OPTIMIZED] Using optimized GeneratePublicKeysController")
except ImportError:
    from verifier_app.domain.controllers.v1.public_keys.generate_public_keys_controller import (
        GeneratePublicKeysController,
    )
    print("[WARNING] Failed to load optimized controller, using default")


class GeneratePublicKeysControllers(containers.DeclarativeContainer):
    bitvmx_protocol = providers.Singleton(
        GeneratePublicKeysController,
        generate_verifier_public_keys_service_class=GenerateVerifierPublicKeysService,
        common_protocol_properties=common_protocol_properties,
        transaction_generator_from_public_keys_service=TransactionGeneratorFromPublicKeysService(),
        bitvmx_protocol_verifier_private_dto_persistence=BitVMXProtocolVerifierPrivateDTOPersistences.bitvmx,
        bitvmx_protocol_setup_properties_dto_persistence=BitVMXProtocolSetupPropertiesDTOPersistences.bitvmx,
    )
