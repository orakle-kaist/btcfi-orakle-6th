from dependency_injector import providers

from verifier_app.persistence.json.bitvmx_protocol_setup_properties_dto_json_persistence import (
    BitVMXProtocolSetupPropertiesDTOJsonPersistence,
)

# Try to import optimized version
try:
    from verifier_app.domain.persistences.services.bitvmx_protocol_setup_properties_dto_persistence_optimized import (
        BitVMXProtocolSetupPropertiesDTOPersistenceOptimized,
    )
    USE_OPTIMIZED = True
    print("[OPTIMIZED] Using optimized persistence service")
except ImportError:
    USE_OPTIMIZED = False
    print("[WARNING] Optimized persistence not available, using standard version")


class BitVMXProtocolSetupPropertiesDTOPersistences:
    json = providers.Singleton(
        BitVMXProtocolSetupPropertiesDTOJsonPersistence, base_path="verifier_files"
    )
    
    if USE_OPTIMIZED:
        optimized = providers.Singleton(BitVMXProtocolSetupPropertiesDTOPersistenceOptimized)
        bitvmx = optimized
    else:
        bitvmx = json
