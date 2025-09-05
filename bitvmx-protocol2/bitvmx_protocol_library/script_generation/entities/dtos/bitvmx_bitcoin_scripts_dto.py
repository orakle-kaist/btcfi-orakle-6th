import json
import hashlib
import pickle
from typing import Dict, List, Optional, Any

from bitcoinutils.keys import P2trAddress, PublicKey
from pydantic import BaseModel, ConfigDict, Field, field_serializer

from bitvmx_protocol_library.bitvmx_execution.services.execution_trace_generation_service import (
    ExecutionTraceGenerationService,
)
from bitvmx_protocol_library.bitvmx_execution.services.input_and_constant_addresses_generation_service import (
    InputAndConstantAddressesGenerationService,
)
from bitvmx_protocol_library.script_generation.entities.business_objects.bitcoin_script import (
    BitcoinScript,
)
from bitvmx_protocol_library.script_generation.entities.business_objects.bitcoin_script_list import (
    BitcoinScriptList,
)
from bitvmx_protocol_library.script_generation.entities.business_objects.bitvmx_execution_script_list import (
    BitVMXExecutionScriptList,
)
from bitvmx_protocol_library.script_generation.entities.business_objects.bitvmx_wrong_hash_script_list import (
    BitVMXLastHashEquivocationScriptList,
    BitVMXWrongHashScriptList,
    BitVMXWrongProgramCounterScriptList,
)


class BitVMXBitcoinScriptsDTO(BaseModel):
    hash_result_script: BitcoinScript
    trigger_protocol_script: BitcoinScript
    hash_search_scripts: List[BitcoinScript]
    choice_search_scripts: List[BitcoinScript]
    trace_script: BitcoinScript
    trigger_challenge_scripts: BitcoinScriptList
    execution_challenge_script_list: BitVMXExecutionScriptList
    wrong_hash_challenge_script_list: BitVMXWrongHashScriptList
    last_hash_equivocation_script_list: BitVMXLastHashEquivocationScriptList
    wrong_program_counter_challenge_scripts_list: BitVMXWrongProgramCounterScriptList
    input_1_equivocation_challenge_scripts: BitcoinScriptList
    input_2_equivocation_challenge_scripts: BitcoinScriptList
    constants_1_equivocation_challenge_scripts: BitcoinScriptList
    constants_2_equivocation_challenge_scripts: BitcoinScriptList
    wrong_init_value_1_challenge_script: BitcoinScript
    wrong_init_value_2_challenge_script: BitcoinScript
    cached_trigger_trace_challenge_address: Dict[str, str] = Field(default_factory=dict)
    hash_read_search_scripts: List[BitcoinScript]
    choice_read_search_scripts: List[BitcoinScript]
    trigger_read_search_equivocation_scripts: List[BitcoinScript]
    read_trace_script: BitcoinScript
    
    # Fixed script trees (generated once and cached)
    trigger_trace_challenge_scripts_list_fixed: Optional[BitcoinScriptList] = Field(default=None, exclude=True)
    trigger_read_challenge_scripts_list_fixed: Optional[BitcoinScriptList] = Field(default=None, exclude=True)
    trace_script_list_fixed: Optional[BitcoinScriptList] = Field(default=None, exclude=True)
    read_trace_script_list_fixed: Optional[BitcoinScriptList] = Field(default=None, exclude=True)
    trigger_protocol_scripts_list_fixed: Optional[BitcoinScriptList] = Field(default=None, exclude=True)
    
    # Tree fingerprint for cache key generation and debugging
    tree_fingerprint: Optional[str] = Field(default=None, exclude=True)
    trigger_wrong_trace_step_script: BitcoinScript
    trigger_wrong_read_trace_step_script: BitcoinScript
    trigger_read_wrong_hash_challenge_scripts: BitVMXWrongHashScriptList
    trigger_wrong_value_address_read_1_challenge_script: BitcoinScript
    trigger_wrong_value_address_read_2_challenge_script: BitcoinScript
    trigger_wrong_latter_step_1_challenge_script: BitcoinScript
    trigger_wrong_latter_step_2_challenge_script: BitcoinScript
    trigger_wrong_halt_step_challenge_script: BitcoinScript
    trigger_no_halt_in_halt_step_challenge_script: BitcoinScript
    prover_timeout_script: BitcoinScript
    verifier_timeout_script: BitcoinScript
    cached_trigger_read_challenge_address: Dict[str, str] = Field(default_factory=dict)

    model_config = ConfigDict(arbitrary_types_allowed=True)

    def __init__(self, **data):
        for field_name, field_type in self.__annotations__.items():
            # Skip fixed fields and special fields during deserialization
            if field_name.endswith('_fixed') or field_name == 'tree_fingerprint':
                continue
                
            if field_type == BitcoinScript:
                if field_name in data and not isinstance(data[field_name], BitcoinScript):
                    data[field_name] = BitcoinScript(json.loads(data[field_name]))
            elif field_type == List[BitcoinScript]:
                if field_name in data and (not isinstance(data[field_name], list) or not all(
                    isinstance(item, BitcoinScript) for item in data[field_name]
                )):
                    data[field_name] = list(
                        map(
                            lambda elem: BitcoinScript(json.loads(elem)),
                            json.loads(data[field_name]),
                        )
                    )
            elif field_type == BitcoinScriptList:
                if field_name in data and not isinstance(data[field_name], BitcoinScriptList):
                    data[field_name] = BitcoinScriptList(
                        list(
                            map(
                                lambda elem: BitcoinScript(json.loads(elem)),
                                json.loads(data[field_name]),
                            )
                        )
                    )
            elif field_type == BitVMXExecutionScriptList:
                if field_name in data and not isinstance(data[field_name], BitVMXExecutionScriptList):
                    data[field_name] = BitVMXExecutionScriptList(**data[field_name])
            elif field_type == BitVMXWrongHashScriptList:
                if field_name in data and not isinstance(data[field_name], BitVMXWrongHashScriptList):
                    data[field_name] = BitVMXWrongHashScriptList(**data[field_name])
            elif field_type == BitVMXWrongProgramCounterScriptList:
                if field_name in data and not isinstance(data[field_name], BitVMXWrongProgramCounterScriptList):
                    data[field_name] = BitVMXWrongProgramCounterScriptList(**data[field_name])
            elif field_type == BitVMXLastHashEquivocationScriptList:
                if field_name in data and not isinstance(data[field_name], BitVMXLastHashEquivocationScriptList):
                    data[field_name] = BitVMXLastHashEquivocationScriptList(**data[field_name])
            elif field_type == Dict[str, str]:
                pass
            elif field_type.__origin__ == Optional:
                pass  # Skip Optional fields
            else:
                if field_name in data:
                    raise TypeError(f"Unexpected type {field_type} for field {field_name}")
        
        super().__init__(**data)
        
        # Generate fixed script trees once during initialization
        self._initialize_fixed_script_trees()

    def _generate_tree_key_for_scripts(self, scripts: Any) -> str:
        """Generate a stable tree_key for a script list structure.
        This is computed ONCE during initialization and reused everywhere.
        """
        try:
            # Use pickle to serialize the tree structure
            serialized = pickle.dumps(scripts)
            # Generate hash of the serialized data
            tree_hash = hashlib.sha256(serialized).hexdigest()[:16]
            return tree_hash
        except Exception as e:
            print(f"[DTO] Warning: Failed to generate tree_key via pickle: {e}")
            # Fallback: use simple count-based key
            if hasattr(scripts, '__len__'):
                return f"scripts_{len(scripts)}_{id(scripts) % 1000000}"
            return f"scripts_{id(scripts) % 1000000}"
    
    def _get_script_list_safe(self, obj):
        """Safely extract script_list from an object (handles both property and method)"""
        try:
            # If it's already a list, return as-is
            if isinstance(obj, list):
                return obj
            
            # Try to get script_list attribute
            if hasattr(obj, 'script_list'):
                script_list = getattr(obj, 'script_list')
                # If it's callable (method), call it
                if callable(script_list):
                    result = script_list()
                    # Ensure result is a list
                    return result if isinstance(result, list) else []
                # If it's a property/list, return directly
                elif isinstance(script_list, list):
                    return script_list
                # If it's a BitcoinScriptList object, try to get its script_list
                else:
                    print(f"[DTO] Converting BitcoinScriptList to list: {type(script_list)}")
                    if hasattr(script_list, 'script_list'):
                        inner_list = getattr(script_list, 'script_list')
                        return inner_list if isinstance(inner_list, list) else []
                    return []
            else:
                print(f"[DTO] No script_list attribute in {type(obj)}")
                return []
        except Exception as e:
            print(f"[DTO] Error extracting script_list from {type(obj)}: {e}")
            return []
    
    def _initialize_fixed_script_trees(self):
        """Initialize fixed script trees once during DTO creation to ensure cache consistency"""
        print("[DTO] Initializing fixed script trees with pre-generated tree_keys...")
        
        # CRITICAL: Set tree_keys for ALL BitcoinScriptList objects to prevent on-the-fly computation
        # This ensures control blocks are computed consistently
        
        # Set tree_key for trigger_challenge_scripts
        if hasattr(self.trigger_challenge_scripts, 'set_fixed_tree_keys'):
            scripts = self._get_script_list_safe(self.trigger_challenge_scripts)
            if scripts:
                key = self._generate_tree_key_for_scripts(scripts)
                self.trigger_challenge_scripts.set_fixed_tree_keys(key)
                print(f"[DTO] Set tree_key for trigger_challenge_scripts: {key[:8]}")
        
        # Set tree_key for equivocation scripts
        for attr_name in ['input_1_equivocation_challenge_scripts', 
                         'input_2_equivocation_challenge_scripts',
                         'constants_1_equivocation_challenge_scripts',
                         'constants_2_equivocation_challenge_scripts']:
            if hasattr(self, attr_name):
                obj = getattr(self, attr_name)
                if hasattr(obj, 'set_fixed_tree_keys'):
                    scripts = self._get_script_list_safe(obj)
                    if scripts:
                        key = self._generate_tree_key_for_scripts(scripts)
                        obj.set_fixed_tree_keys(key)
                        print(f"[DTO] Set tree_key for {attr_name}: {key[:8]}")
        
        # Generate trigger_trace_challenge_scripts_list_fixed (most critical for performance)
        # First, compose all the scripts into a flat list
        trigger_trace_scripts = (
            self._get_script_list_safe(self.trigger_challenge_scripts)
            + self._get_script_list_safe(self.wrong_hash_challenge_script_list)
            + self._get_script_list_safe(self.wrong_program_counter_challenge_scripts_list)
            + [self.choice_read_search_scripts[0]]
            + self._get_script_list_safe(self.input_1_equivocation_challenge_scripts)
            + self._get_script_list_safe(self.input_2_equivocation_challenge_scripts)
            + self._get_script_list_safe(self.constants_1_equivocation_challenge_scripts)
            + self._get_script_list_safe(self.constants_2_equivocation_challenge_scripts)
            + [self.trigger_wrong_halt_step_challenge_script]
            + [self.trigger_no_halt_in_halt_step_challenge_script]
            + self._get_script_list_safe(self.last_hash_equivocation_script_list)
            + [self.wrong_init_value_1_challenge_script]
            + [self.wrong_init_value_2_challenge_script]
            + [self.prover_timeout_script]
        )
        # Generate tree_key ONCE for this fixed list
        trigger_trace_tree_key = self._generate_tree_key_for_scripts(trigger_trace_scripts)
        print(f"[DTO] Generated trigger_trace tree_key: {trigger_trace_tree_key} for {len(trigger_trace_scripts)} scripts")
        # Create BitcoinScriptList with pre-computed tree_key
        self.trigger_trace_challenge_scripts_list_fixed = BitcoinScriptList(trigger_trace_scripts)
        self.trigger_trace_challenge_scripts_list_fixed.set_fixed_tree_keys(trigger_trace_tree_key)
        
        # Generate trigger_read_challenge_scripts_list_fixed
        # First, compose all the scripts into a flat list
        trigger_read_scripts = (
            self._get_script_list_safe(self.trigger_read_search_equivocation_scripts)
            + [self.trigger_wrong_trace_step_script]
            + [self.trigger_wrong_read_trace_step_script]
            + self._get_script_list_safe(self.trigger_read_wrong_hash_challenge_scripts)
            + [self.trigger_wrong_value_address_read_1_challenge_script]
            + [self.trigger_wrong_value_address_read_2_challenge_script]
            + [self.trigger_wrong_latter_step_1_challenge_script]
            + [self.trigger_wrong_latter_step_2_challenge_script]
            + [self.verifier_timeout_script]
        )
        # Generate tree_key ONCE for this fixed list
        trigger_read_tree_key = self._generate_tree_key_for_scripts(trigger_read_scripts)
        print(f"[DTO] Generated trigger_read tree_key: {trigger_read_tree_key} for {len(trigger_read_scripts)} scripts")
        # Create BitcoinScriptList with pre-computed tree_key
        self.trigger_read_challenge_scripts_list_fixed = BitcoinScriptList(trigger_read_scripts)
        self.trigger_read_challenge_scripts_list_fixed.set_fixed_tree_keys(trigger_read_tree_key)
        
        # Generate other fixed lists for completeness
        self.trace_script_list_fixed = self.execution_challenge_script_list
        
        # Set tree_key for execution_challenge_script_list (BitVMXExecutionScriptList)
        if hasattr(self.execution_challenge_script_list, 'set_fixed_tree_keys'):
            exec_key = self._generate_tree_key_for_scripts(self.execution_challenge_script_list.key_list)
            self.execution_challenge_script_list.set_fixed_tree_keys(exec_key)
            print(f"[DTO] Set tree_key for execution_challenge_script_list: {exec_key[:8]}")
        
        # Set tree_key for other special script lists
        for attr_name in ['wrong_hash_challenge_script_list', 
                         'last_hash_equivocation_script_list',
                         'wrong_program_counter_challenge_scripts_list',
                         'trigger_read_wrong_hash_challenge_scripts']:
            if hasattr(self, attr_name):
                obj = getattr(self, attr_name)
                if hasattr(obj, 'set_fixed_tree_keys'):
                    # These objects might have different structures
                    if hasattr(obj, 'key_list'):
                        key = self._generate_tree_key_for_scripts(obj.key_list)
                    elif hasattr(obj, 'script_list'):
                        key = self._generate_tree_key_for_scripts(obj.script_list)
                    else:
                        key = self._generate_tree_key_for_scripts(str(obj))
                    obj.set_fixed_tree_keys(key)
                    print(f"[DTO] Set tree_key for {attr_name}: {key[:8]}")
        
        # Generate tree_key for read_trace_script_list
        read_trace_scripts = [self.read_trace_script, self.verifier_timeout_script]
        read_trace_tree_key = self._generate_tree_key_for_scripts(read_trace_scripts)
        self.read_trace_script_list_fixed = BitcoinScriptList(read_trace_scripts)
        self.read_trace_script_list_fixed.set_fixed_tree_keys(read_trace_tree_key)
        
        # Generate tree_key for trigger_protocol_scripts_list
        trigger_protocol_scripts = [self.trigger_protocol_script, self.verifier_timeout_script]
        trigger_protocol_tree_key = self._generate_tree_key_for_scripts(trigger_protocol_scripts)
        self.trigger_protocol_scripts_list_fixed = BitcoinScriptList(trigger_protocol_scripts)
        self.trigger_protocol_scripts_list_fixed.set_fixed_tree_keys(trigger_protocol_tree_key)
        
        # Generate tree fingerprint for cache key and debugging
        self._generate_tree_fingerprint()
        
        print(f"[DTO] Fixed script trees initialized with fingerprint: {self.tree_fingerprint}")
    
    def _generate_tree_fingerprint(self):
        """Generate unique fingerprint for this script tree configuration"""
        # Serialize key components that affect tree structure
        components = []
        
        if self.trigger_trace_challenge_scripts_list_fixed:
            components.append(f"ttc:{len(self.trigger_trace_challenge_scripts_list_fixed.script_list)}")
        if self.trigger_read_challenge_scripts_list_fixed:
            components.append(f"trc:{len(self.trigger_read_challenge_scripts_list_fixed.script_list)}")
        if self.trace_script_list_fixed:
            components.append(f"trace:{len(self.trace_script_list_fixed.key_list)}")
        
        combined = ":".join(components)
        self.tree_fingerprint = hashlib.sha256(combined.encode()).hexdigest()[:32]

    def hash_search_scripts_list(self, iteration: int) -> BitcoinScriptList:
        scripts = [self.hash_search_scripts[iteration], self.prover_timeout_script]
        script_list = BitcoinScriptList(scripts)
        tree_key = self._generate_tree_key_for_scripts(scripts)
        script_list.set_fixed_tree_keys(tree_key)
        return script_list

    @staticmethod
    def hash_search_script_index():
        return 0

    def choice_search_scripts_list(self, iteration: int) -> BitcoinScriptList:
        scripts = [self.choice_search_scripts[iteration], self.verifier_timeout_script]
        script_list = BitcoinScriptList(scripts)
        tree_key = self._generate_tree_key_for_scripts(scripts)
        script_list.set_fixed_tree_keys(tree_key)
        return script_list

    @staticmethod
    def choice_search_script_index():
        return 0

    def hash_read_search_scripts_list(self, iteration: int) -> BitcoinScriptList:
        scripts = [self.hash_read_search_scripts[iteration], self.prover_timeout_script]
        script_list = BitcoinScriptList(scripts)
        tree_key = self._generate_tree_key_for_scripts(scripts)
        script_list.set_fixed_tree_keys(tree_key)
        return script_list

    @staticmethod
    def hash_read_search_script_index():
        return 0

    @property
    def trigger_trace_challenge_scripts_list(self) -> BitcoinScriptList:
        """Return the fixed script list - no more dynamic generation"""
        if self.trigger_trace_challenge_scripts_list_fixed is None:
            raise ValueError("Fixed script trees not initialized. Call _initialize_fixed_script_trees() first.")
        return self.trigger_trace_challenge_scripts_list_fixed

    @property
    def trigger_protocol_scripts_list(self) -> BitcoinScriptList:
        """Return the fixed script list - no more dynamic generation"""
        if self.trigger_protocol_scripts_list_fixed is None:
            raise ValueError("Fixed script trees not initialized. Call _initialize_fixed_script_trees() first.")
        return self.trigger_protocol_scripts_list_fixed

    @staticmethod
    def trigger_protocol_index() -> int:
        return 0

    @property
    def trace_script_list(self) -> BitcoinScriptList:
        """Return the fixed script list - no more dynamic generation"""
        if self.trace_script_list_fixed is None:
            raise ValueError("Fixed script trees not initialized. Call _initialize_fixed_script_trees() first.")
        return self.trace_script_list_fixed

    @staticmethod
    def trace_script_index() -> int:
        return 0

    @staticmethod
    def trigger_wrong_trace_step_index() -> int:
        return 1

    @property
    def read_trace_script_list(self) -> BitcoinScriptList:
        """Return the fixed script list - no more dynamic generation"""
        if self.read_trace_script_list_fixed is None:
            raise ValueError("Fixed script trees not initialized. Call _initialize_fixed_script_trees() first.")
        return self.read_trace_script_list_fixed

    @staticmethod
    def read_trace_script_index() -> int:
        return 0

    @staticmethod
    def trigger_wrong_read_trace_step_index() -> int:
        return 1

    def trigger_trace_challenge_address(self, destroyed_public_key: PublicKey) -> P2trAddress:
        if destroyed_public_key.to_hex() in self.cached_trigger_trace_challenge_address:
            return P2trAddress(
                self.cached_trigger_trace_challenge_address[destroyed_public_key.to_hex()]
            )
        trigger_trace_challenge_address = (
            self.trigger_trace_challenge_scripts_list.get_taproot_address(
                public_key=destroyed_public_key
            )
        )
        self.cached_trigger_trace_challenge_address[destroyed_public_key.to_hex()] = (
            trigger_trace_challenge_address.to_string()
        )
        return trigger_trace_challenge_address

    @property
    def trigger_read_challenge_scripts_list(self) -> BitcoinScriptList:
        """Return the fixed script list - no more dynamic generation"""
        if self.trigger_read_challenge_scripts_list_fixed is None:
            raise ValueError("Fixed script trees not initialized. Call _initialize_fixed_script_trees() first.")
        return self.trigger_read_challenge_scripts_list_fixed

    def trigger_read_challenge_address(self, destroyed_public_key: PublicKey) -> P2trAddress:
        if destroyed_public_key.to_hex() in self.cached_trigger_read_challenge_address:
            return P2trAddress(
                self.cached_trigger_read_challenge_address[destroyed_public_key.to_hex()]
            )
        trigger_read_challenge_address = (
            self.trigger_read_challenge_scripts_list.get_taproot_address(
                public_key=destroyed_public_key
            )
        )
        self.cached_trigger_read_challenge_address[destroyed_public_key.to_hex()] = (
            trigger_read_challenge_address.to_string()
        )
        return trigger_read_challenge_address

    def choice_read_search_scripts_address(
        self, destroyed_public_key: PublicKey, iteration: int
    ) -> P2trAddress:
        assert iteration > 0
        return self.choice_read_search_script_list(iteration=iteration).get_taproot_address(
            destroyed_public_key
        )

    def hash_read_search_scripts_address(
        self, destroyed_public_key: PublicKey, iteration: int
    ) -> P2trAddress:
        assert iteration > 0
        return self.hash_read_search_script_list(iteration=iteration).get_taproot_address(
            destroyed_public_key
        )

    @staticmethod
    def choice_read_search_script_index(iteration: int) -> int:
        assert iteration > 0
        return 0

    @staticmethod
    def trigger_read_search_equivocation_index(iteration: int) -> int:
        assert iteration > 0
        return 1

    def choice_read_search_script_list(self, iteration: int) -> BitcoinScriptList:
        assert iteration > 0
        scripts = [
            self.choice_read_search_scripts[iteration],
            self.trigger_read_search_equivocation_scripts[iteration - 1],
            self.verifier_timeout_script,
        ]
        script_list = BitcoinScriptList(scripts)
        tree_key = self._generate_tree_key_for_scripts(scripts)
        script_list.set_fixed_tree_keys(tree_key)
        return script_list

    def hash_read_search_script_list(self, iteration: int) -> BitcoinScriptList:
        assert iteration > 0
        scripts = [
            self.hash_read_search_scripts[iteration - 1],
            self.prover_timeout_script,
        ]
        script_list = BitcoinScriptList(scripts)
        tree_key = self._generate_tree_key_for_scripts(scripts)
        script_list.set_fixed_tree_keys(tree_key)
        return script_list

    def trigger_challenge_taptree(self):
        return self.trigger_trace_challenge_scripts_list.to_scripts_tree()

    def trigger_read_challenge_taptree(self):
        return self.trigger_read_challenge_scripts_list.to_scripts_tree()

    @staticmethod
    def trigger_challenge_index(index: int) -> int:
        return index

    def trigger_wrong_hash_challenge_index(self, choice: int) -> int:
        return len(
            self.trigger_challenge_scripts
        ) + self.wrong_hash_challenge_script_list.list_index_from_choice(choice=choice)

    def trigger_wrong_program_counter_challenge_index(self, choice: int) -> int:
        return (
            len(self.trigger_challenge_scripts)
            + len(self.wrong_hash_challenge_script_list)
            + self.wrong_program_counter_challenge_scripts_list.list_index_from_choice(
                choice=choice
            )
        )

    def trigger_read_search_challenge_index(self) -> int:
        return (
            len(self.trigger_challenge_scripts)
            + len(self.wrong_hash_challenge_script_list)
            + len(self.wrong_program_counter_challenge_scripts_list)
        )

    @staticmethod
    def _check_input_range(address: str, base_input_address: str, amount_of_input_words: int):
        int_address = int(address, 16)
        int_base_input_address = int(base_input_address, 16)
        if not ((int_address - int_base_input_address) % 4) == 0:
            raise Exception("Input address not aligned with base input address")
        if int_address < int_base_input_address or (
            int_address >= (int_base_input_address + amount_of_input_words * 4)
        ):
            raise Exception("Input address out of input region")

    @staticmethod
    def _get_index_from_address_constant(address: str, amount_of_input_words: int):
        input_and_constant_addresses_generation_service = (
            InputAndConstantAddressesGenerationService(
                instruction_commitment=ExecutionTraceGenerationService.commitment_file()
            )
        )
        static_addresses = input_and_constant_addresses_generation_service(
            input_length=amount_of_input_words
        )
        addresses = list(sorted(static_addresses.constants.keys()))
        return addresses.index(address)

    @staticmethod
    def get_index_from_address(address: str, base_input_address: str):
        int_address = int(address, 16)
        int_base_input_address = int(base_input_address, 16)
        return int((int_address - int_base_input_address) / 4)

    def trigger_input_1_equivocation_challenge_index(
        self, address: str, base_input_address: str, amount_of_input_words: int
    ) -> int:
        self._check_input_range(
            address=address,
            base_input_address=base_input_address,
            amount_of_input_words=amount_of_input_words,
        )
        index_from_address = self.get_index_from_address(
            address=address, base_input_address=base_input_address
        )
        return (
            len(self.trigger_challenge_scripts)
            + len(self.wrong_hash_challenge_script_list)
            + len(self.wrong_program_counter_challenge_scripts_list)
            + 1
            + index_from_address
        )

    def trigger_input_2_equivocation_challenge_index(
        self, address: str, base_input_address: str, amount_of_input_words: int
    ) -> int:
        self._check_input_range(
            address=address,
            base_input_address=base_input_address,
            amount_of_input_words=amount_of_input_words,
        )
        index_from_address = self.get_index_from_address(
            address=address, base_input_address=base_input_address
        )
        return (
            len(self.trigger_challenge_scripts)
            + len(self.wrong_hash_challenge_script_list)
            + len(self.wrong_program_counter_challenge_scripts_list)
            + 1
            + len(self.input_1_equivocation_challenge_scripts)
            + index_from_address
        )

    def trigger_constant_1_equivocation_challenge_index(
        self, address: str, amount_of_input_words: int
    ) -> int:
        index_from_address = self._get_index_from_address_constant(
            address=address, amount_of_input_words=amount_of_input_words
        )
        return (
            len(self.trigger_challenge_scripts)
            + len(self.wrong_hash_challenge_script_list)
            + len(self.wrong_program_counter_challenge_scripts_list)
            + 1
            + len(self.input_1_equivocation_challenge_scripts)
            + len(self.input_2_equivocation_challenge_scripts)
            + index_from_address
        )

    def trigger_constant_2_equivocation_challenge_index(
        self, address: str, amount_of_input_words: int
    ) -> int:
        index_from_address = self._get_index_from_address_constant(
            address=address, amount_of_input_words=amount_of_input_words
        )
        return (
            len(self.trigger_challenge_scripts)
            + len(self.wrong_hash_challenge_script_list)
            + len(self.wrong_program_counter_challenge_scripts_list)
            + 1
            + len(self.input_1_equivocation_challenge_scripts)
            + len(self.input_2_equivocation_challenge_scripts)
            + len(self.constants_1_equivocation_challenge_scripts)
            + index_from_address
        )

    def trigger_wrong_halt_step_challenge_index(self):
        return (
            len(self.trigger_challenge_scripts)
            + len(self.wrong_hash_challenge_script_list)
            + len(self.wrong_program_counter_challenge_scripts_list)
            + 1
            + len(self.input_1_equivocation_challenge_scripts)
            + len(self.input_2_equivocation_challenge_scripts)
            + len(self.constants_1_equivocation_challenge_scripts)
            + len(self.constants_2_equivocation_challenge_scripts)
        )

    def trigger_no_halt_in_halt_step_challenge_index(self):
        return (
            len(self.trigger_challenge_scripts)
            + len(self.wrong_hash_challenge_script_list)
            + len(self.wrong_program_counter_challenge_scripts_list)
            + 1
            + len(self.input_1_equivocation_challenge_scripts)
            + len(self.input_2_equivocation_challenge_scripts)
            + len(self.constants_1_equivocation_challenge_scripts)
            + len(self.constants_2_equivocation_challenge_scripts)
            + 1
        )

    def trigger_last_hash_equivocation_challenge_index(self, choice: int) -> int:
        return (
            len(self.trigger_challenge_scripts)
            + len(self.wrong_hash_challenge_script_list)
            + len(self.wrong_program_counter_challenge_scripts_list)
            + 1
            + len(self.input_1_equivocation_challenge_scripts)
            + len(self.input_2_equivocation_challenge_scripts)
            + len(self.constants_1_equivocation_challenge_scripts)
            + len(self.constants_2_equivocation_challenge_scripts)
            + 2
        ) + self.last_hash_equivocation_script_list.list_index_from_choice(choice=choice)

    def trigger_wrong_init_value_1_challenge_index(self):
        return (
            len(self.trigger_challenge_scripts)
            + len(self.wrong_hash_challenge_script_list)
            + len(self.wrong_program_counter_challenge_scripts_list)
            + 1
            + len(self.input_1_equivocation_challenge_scripts)
            + len(self.input_2_equivocation_challenge_scripts)
            + len(self.constants_1_equivocation_challenge_scripts)
            + len(self.constants_2_equivocation_challenge_scripts)
            + 2
            + len(self.last_hash_equivocation_script_list)
        )

    def trigger_wrong_init_value_2_challenge_index(self):
        return (
            len(self.trigger_challenge_scripts)
            + len(self.wrong_hash_challenge_script_list)
            + len(self.wrong_program_counter_challenge_scripts_list)
            + 1
            + len(self.input_1_equivocation_challenge_scripts)
            + len(self.input_2_equivocation_challenge_scripts)
            + len(self.constants_1_equivocation_challenge_scripts)
            + len(self.constants_2_equivocation_challenge_scripts)
            + 2
            + len(self.last_hash_equivocation_script_list)
            + 1
        )

    def trigger_read_wrong_hash_challenge_index(self, choice: int):
        return self.trigger_read_wrong_hash_challenge_scripts.list_index_from_choice(choice=choice)

    def trigger_wrong_value_address_read_1_index(self):
        return len(self.trigger_read_wrong_hash_challenge_scripts)

    def trigger_wrong_value_address_read_2_index(self):
        return len(self.trigger_read_wrong_hash_challenge_scripts) + 1

    def trigger_wrong_latter_step_1_index(self):
        return len(self.trigger_read_wrong_hash_challenge_scripts) + 2

    def trigger_wrong_latter_step_2_index(self):
        return len(self.trigger_read_wrong_hash_challenge_scripts) + 3

    @staticmethod
    def bitcoin_script_to_str(script: BitcoinScript) -> str:
        return json.dumps(script.script)

    @field_serializer("hash_result_script", when_used="always")
    def serialize_hash_result_script(hash_result_script: BitcoinScript) -> str:
        return BitVMXBitcoinScriptsDTO.bitcoin_script_to_str(script=hash_result_script)

    @field_serializer("trigger_protocol_script", when_used="always")
    def serialize_trigger_protocol_script(trigger_protocol_script: BitcoinScript) -> str:
        return BitVMXBitcoinScriptsDTO.bitcoin_script_to_str(script=trigger_protocol_script)

    @field_serializer("trace_script", when_used="always")
    def serialize_trace_script(trace_script: BitcoinScript) -> str:
        return BitVMXBitcoinScriptsDTO.bitcoin_script_to_str(script=trace_script)

    @field_serializer("hash_search_scripts", when_used="always")
    def serialize_hash_search_scripts(hash_search_scripts: List[BitcoinScript]) -> str:
        return json.dumps(
            list(
                map(
                    lambda btc_scr: BitVMXBitcoinScriptsDTO.bitcoin_script_to_str(script=btc_scr),
                    hash_search_scripts,
                )
            )
        )

    @field_serializer("choice_search_scripts", when_used="always")
    def serialize_choice_search_scripts(choice_search_scripts: List[BitcoinScript]) -> str:
        return json.dumps(
            list(
                map(
                    lambda btc_scr: BitVMXBitcoinScriptsDTO.bitcoin_script_to_str(script=btc_scr),
                    choice_search_scripts,
                )
            )
        )

    @field_serializer("trigger_challenge_scripts", when_used="always")
    def serialize_trigger_challenge_scripts(trigger_challenge_scripts: BitcoinScriptList) -> str:
        return json.dumps(
            list(
                map(
                    lambda btc_scr: BitVMXBitcoinScriptsDTO.bitcoin_script_to_str(script=btc_scr),
                    trigger_challenge_scripts.script_list,
                )
            )
        )

    @field_serializer("input_1_equivocation_challenge_scripts", when_used="always")
    def serialize_input_1_equivocation_challenge_scripts(
        input_1_equivocation_challenge_scripts: BitcoinScriptList,
    ) -> str:
        return json.dumps(
            list(
                map(
                    lambda btc_scr: BitVMXBitcoinScriptsDTO.bitcoin_script_to_str(script=btc_scr),
                    input_1_equivocation_challenge_scripts.script_list,
                )
            )
        )

    @field_serializer("input_2_equivocation_challenge_scripts", when_used="always")
    def serialize_input_2_equivocation_challenge_scripts(
        input_2_equivocation_challenge_scripts: BitcoinScriptList,
    ) -> str:
        return json.dumps(
            list(
                map(
                    lambda btc_scr: BitVMXBitcoinScriptsDTO.bitcoin_script_to_str(script=btc_scr),
                    input_2_equivocation_challenge_scripts.script_list,
                )
            )
        )

    @field_serializer("constants_1_equivocation_challenge_scripts", when_used="always")
    def serialize_constants_1_equivocation_challenge_scripts(
        constants_1_equivocation_challenge_scripts: BitcoinScriptList,
    ) -> str:
        return json.dumps(
            list(
                map(
                    lambda btc_scr: BitVMXBitcoinScriptsDTO.bitcoin_script_to_str(script=btc_scr),
                    constants_1_equivocation_challenge_scripts.script_list,
                )
            )
        )

    @field_serializer("constants_2_equivocation_challenge_scripts", when_used="always")
    def serialize_constants_2_equivocation_challenge_scripts(
        constants_2_equivocation_challenge_scripts: BitcoinScriptList,
    ) -> str:
        return json.dumps(
            list(
                map(
                    lambda btc_scr: BitVMXBitcoinScriptsDTO.bitcoin_script_to_str(script=btc_scr),
                    constants_2_equivocation_challenge_scripts.script_list,
                )
            )
        )

    @field_serializer("wrong_init_value_1_challenge_script", when_used="always")
    def serialize_wrong_init_value_1_challenge_script(
        wrong_init_value_1_challenge_script: BitcoinScript,
    ) -> str:
        return BitVMXBitcoinScriptsDTO.bitcoin_script_to_str(
            script=wrong_init_value_1_challenge_script
        )

    @field_serializer("wrong_init_value_2_challenge_script", when_used="always")
    def serialize_wrong_init_value_2_challenge_script(
        wrong_init_value_2_challenge_script: BitcoinScript,
    ) -> str:
        return BitVMXBitcoinScriptsDTO.bitcoin_script_to_str(
            script=wrong_init_value_2_challenge_script
        )

    @field_serializer("hash_read_search_scripts", when_used="always")
    def serialize_hash_read_search_scripts(hash_read_search_scripts: List[BitcoinScript]) -> str:
        return json.dumps(
            list(
                map(
                    lambda btc_scr: BitVMXBitcoinScriptsDTO.bitcoin_script_to_str(script=btc_scr),
                    hash_read_search_scripts,
                )
            )
        )

    @field_serializer("choice_read_search_scripts", when_used="always")
    def serialize_choice_read_search_scripts(
        choice_read_search_scripts: List[BitcoinScript],
    ) -> str:
        return json.dumps(
            list(
                map(
                    lambda btc_scr: BitVMXBitcoinScriptsDTO.bitcoin_script_to_str(script=btc_scr),
                    choice_read_search_scripts,
                )
            )
        )

    @field_serializer("trigger_read_search_equivocation_scripts", when_used="always")
    def serialize_trigger_read_search_equivocation_scripts(
        trigger_read_search_equivocation_scripts: List[BitcoinScript],
    ) -> str:
        return json.dumps(
            list(
                map(
                    lambda btc_scr: BitVMXBitcoinScriptsDTO.bitcoin_script_to_str(script=btc_scr),
                    trigger_read_search_equivocation_scripts,
                )
            )
        )

    @field_serializer("read_trace_script", when_used="always")
    def serialize_read_trace_script(read_trace_script: BitcoinScript) -> str:
        return BitVMXBitcoinScriptsDTO.bitcoin_script_to_str(script=read_trace_script)

    @field_serializer("trigger_wrong_value_address_read_1_challenge_script", when_used="always")
    def serialize_trigger_wrong_value_address_read_1_challenge_script(
        trigger_wrong_value_address_read_1_challenge_script: BitcoinScript,
    ) -> str:
        return BitVMXBitcoinScriptsDTO.bitcoin_script_to_str(
            script=trigger_wrong_value_address_read_1_challenge_script
        )

    @field_serializer("trigger_wrong_value_address_read_2_challenge_script", when_used="always")
    def serialize_trigger_wrong_value_address_read_2_challenge_script(
        trigger_wrong_value_address_read_2_challenge_script: BitcoinScript,
    ) -> str:
        return BitVMXBitcoinScriptsDTO.bitcoin_script_to_str(
            script=trigger_wrong_value_address_read_2_challenge_script
        )

    @field_serializer("trigger_wrong_latter_step_1_challenge_script", when_used="always")
    def serialize_trigger_wrong_latter_step_1_challenge_script(
        trigger_wrong_latter_step_1_challenge_script: BitcoinScript,
    ) -> str:
        return BitVMXBitcoinScriptsDTO.bitcoin_script_to_str(
            script=trigger_wrong_latter_step_1_challenge_script
        )

    @field_serializer("trigger_wrong_latter_step_2_challenge_script", when_used="always")
    def serialize_trigger_wrong_latter_step_2_challenge_script(
        trigger_wrong_latter_step_2_challenge_script: BitcoinScript,
    ) -> str:
        return BitVMXBitcoinScriptsDTO.bitcoin_script_to_str(
            script=trigger_wrong_latter_step_2_challenge_script
        )

    @field_serializer("trigger_wrong_halt_step_challenge_script", when_used="always")
    def serialize_trigger_wrong_halt_step_challenge_script(
        trigger_wrong_halt_step_challenge_script: BitcoinScript,
    ) -> str:
        return BitVMXBitcoinScriptsDTO.bitcoin_script_to_str(
            script=trigger_wrong_halt_step_challenge_script
        )

    @field_serializer("trigger_no_halt_in_halt_step_challenge_script", when_used="always")
    def serialize_trigger_no_halt_in_halt_step_challenge_script(
        trigger_no_halt_in_halt_step_challenge_script: BitcoinScript,
    ) -> str:
        return BitVMXBitcoinScriptsDTO.bitcoin_script_to_str(
            script=trigger_no_halt_in_halt_step_challenge_script
        )

    @field_serializer("trigger_wrong_trace_step_script", when_used="always")
    def serialize_trigger_wrong_trace_step_script(
        trigger_wrong_trace_step_script: BitcoinScript,
    ) -> str:
        return BitVMXBitcoinScriptsDTO.bitcoin_script_to_str(script=trigger_wrong_trace_step_script)

    @field_serializer("trigger_wrong_read_trace_step_script", when_used="always")
    def serialize_trigger_wrong_read_trace_step_script(
        trigger_wrong_read_trace_step_script: BitcoinScript,
    ) -> str:
        return BitVMXBitcoinScriptsDTO.bitcoin_script_to_str(
            script=trigger_wrong_read_trace_step_script
        )

    @field_serializer("prover_timeout_script", when_used="always")
    def serialize_prover_timeout_script(prover_timeout_script: BitcoinScript) -> str:
        return BitVMXBitcoinScriptsDTO.bitcoin_script_to_str(script=prover_timeout_script)

    @field_serializer("verifier_timeout_script", when_used="always")
    def serialize_verifier_timeout_script(verifier_timeout_script: BitcoinScript) -> str:
        return BitVMXBitcoinScriptsDTO.bitcoin_script_to_str(script=verifier_timeout_script)
