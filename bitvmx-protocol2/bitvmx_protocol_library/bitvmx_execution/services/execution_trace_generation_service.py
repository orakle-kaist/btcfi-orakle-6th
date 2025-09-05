from typing import Optional

from bitvmx_protocol_library.bitvmx_execution.services.bitvmx_wrapper import BitVMXWrapper


class ExecutionTraceGenerationService:

    @staticmethod
    def elf_file(option_type: Optional[str] = None, elf_file_name: Optional[str] = None):
        """
        옵션 타입 또는 직접 지정된 ELF 파일 반환
        - elf_file_name이 지정되면 우선 사용
        - option_type에 따라 적절한 ELF 선택
        - 실제 존재하는 파일을 우선적으로 사용
        """
        import os
        
        # If elf_file_name is directly provided, use it
        if elf_file_name:
            full_path = f"./execution_files/{elf_file_name}"
            if os.path.exists(full_path):
                print(f"[ELF] Using specified ELF file: {full_path}")
                return elf_file_name
            else:
                print(f"[ELF] Warning: Specified file {full_path} not found, trying alternatives...")
        
        # Map option types to their ELF files
        option_type_map = {
            "registration": ["option_registration_final.elf", "option_registration.elf"],
            "purchase": ["option_purchase_final.elf", "option_purchase.elf"],
            "settlement": ["option_settlement_final.elf", "option_settlement.elf"]
        }
        
        # Try option type specific files first
        if option_type and option_type in option_type_map:
            for candidate in option_type_map[option_type]:
                full_path = f"./execution_files/{candidate}"
                if os.path.exists(full_path):
                    print(f"[ELF] Using {option_type} ELF file: {full_path}")
                    return candidate
        
        # General fallback candidates
        fallback_candidates = [
            "option_registration_final.elf",
            "option_registration.elf",
            "program_fixed_exit.elf",
            "hello-world.elf"
        ]
        
        # Try to find an existing ELF file from fallbacks
        for candidate in fallback_candidates:
            full_path = f"./execution_files/{candidate}"
            if os.path.exists(full_path):
                print(f"[ELF] Using fallback ELF file: {full_path}")
                return candidate
        
        # Final fallback
        print(f"[ELF] Warning: No ELF file found, using default")
        return "program_fixed_exit.elf"

    # This can be computed on the fly to avoid storing it (it does not take that much time to generate it)
    @staticmethod
    def commitment_file(elf_file_name: Optional[str] = None):
        import os
        
        if not elf_file_name:
            elf_file_name = ExecutionTraceGenerationService.elf_file()
        
        # Map ELF files to their commitment files
        commitment_map = {
            "option_registration_final.elf": "instruction_commitment.txt",
            "option_registration.elf": "instruction_commitment.txt",
            "option_purchase_final.elf": "instruction_commitment.txt",
            "option_purchase.elf": "instruction_commitment.txt",
            "option_settlement_final.elf": "instruction_commitment.txt",
            "option_settlement.elf": "instruction_commitment.txt",
            "program_fixed_exit.elf": "program_fixed_exit_instruction_commitment_input.txt",
            "hello-world.elf": "instruction_commitment_input.txt",
            "btcfi_option_registration.elf": "instruction_commitment_option_registration.txt"
        }
        
        # Check if specific mapping exists
        if elf_file_name in commitment_map:
            commitment = commitment_map[elf_file_name]
            full_path = f"./execution_files/{commitment}"
            if os.path.exists(full_path):
                print(f"[COMMITMENT] Using specific commitment: {full_path}")
                return full_path
        
        # Fallback logic
        if elf_file_name == "zkverifier.elf":
            return "./execution_files/instruction_commitment_zk.txt"
        elif elf_file_name == "plainc.elf":
            return "./execution_files/instruction_commitment.txt"
        elif elf_file_name == "test_input.elf":
            return "./execution_files/instruction_commitment_input.txt"
        elif elf_file_name.startswith("btcfi_"):
            # Try to find any btcfi commitment
            candidates = [
                "btcfi_instruction_commitment_input.txt",
                "instruction_commitment_btcfi.txt",
                "instruction_commitment.txt"
            ]
            for candidate in candidates:
                full_path = f"./execution_files/{candidate}"
                if os.path.exists(full_path):
                    print(f"[COMMITMENT] Using BTCFi commitment: {full_path}")
                    return full_path
        elif elf_file_name.startswith("option_"):
            return "./execution_files/instruction_commitment.txt"
        
        # Default fallback
        return "./execution_files/instruction_commitment_input.txt"

    def __init__(self, base_path: str, option_type: Optional[str] = None, elf_file_name: Optional[str] = None):
        self.base_path = base_path
        self.option_type = option_type
        self.elf_file_name = self.elf_file(option_type, elf_file_name)
        self.bitvmx_wrapper = BitVMXWrapper(base_path)

    def __call__(self, setup_uuid: str, input_hex: Optional[str] = None):
        self.bitvmx_wrapper.generate_execution_checkpoints(
            setup_uuid=setup_uuid, elf_file=self.elf_file_name, input_hex=input_hex
        )
        # return self.execution_trace_parsing_service(
        #     self.base_path + protocol_dict["setup_uuid"] + "/execution_trace.csv", protocol_dict
        # )
