import time
from concurrent.futures import ThreadPoolExecutor
from bitvmx_protocol_library.script_generation.services.bitvmx_bitcoin_scripts_generator_service import (
    BitVMXBitcoinScriptsGeneratorService
)
from bitvmx_protocol_library.bitvmx_protocol_definition.entities.bitvmx_protocol_setup_properties_dto import (
    BitVMXProtocolSetupPropertiesDTO,
)
from bitvmx_protocol_library.script_generation.entities.dtos.bitvmx_bitcoin_scripts_dto import (
    BitVMXBitcoinScriptsDTO,
)


class BitVMXBitcoinScriptsGeneratorServiceOptimized(BitVMXBitcoinScriptsGeneratorService):
    """
    Optimized version of BitVMXBitcoinScriptsGeneratorService.
    For now, we'll use the parent implementation with logging to track performance.
    """
    
    def __init__(self):
        super().__init__()
        print("[OPTIMIZED SCRIPTS] Initialized optimized script generator")
    
    def __call__(
        self,
        bitvmx_protocol_setup_properties_dto: BitVMXProtocolSetupPropertiesDTO,
    ) -> BitVMXBitcoinScriptsDTO:
        """
        Use parent implementation with performance logging.
        """
        start_time = time.time()
        print(f"[OPTIMIZED SCRIPTS] Starting script generation...")
        print(f"[OPTIMIZED SCRIPTS] Parameters: max_steps={bitvmx_protocol_setup_properties_dto.bitvmx_protocol_properties_dto.max_amount_of_steps}, "
              f"search_iterations={bitvmx_protocol_setup_properties_dto.bitvmx_protocol_properties_dto.amount_of_wrong_step_search_iterations}")
        
        # Call parent implementation
        result = super().__call__(bitvmx_protocol_setup_properties_dto)
        
        total_time = time.time() - start_time
        print(f"[OPTIMIZED SCRIPTS] ✅ Script generation completed in {total_time:.2f}s")
        
        return result