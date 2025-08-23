from typing import Optional

from bitvmx_protocol_library.bitvmx_execution.services.bitvmx_wrapper import BitVMXWrapper


class ExecutionTraceGenerationService:

    @staticmethod
    def elf_file(option_type: Optional[str] = None):
        """
        옵션 타입에 따라 적절한 ELF 파일 반환
        """
        if option_type == "registration":
            return "option_registration.elf"
        elif option_type == "purchase":
            return "option_purchase.elf"
        elif option_type == "settlement":
            return "option_settlement.elf"
        else:
            # 기본값
            return "test_input.elf"

    # This can be computed on the fly to avoid storing it (it does not take that much time to generate it)
    @staticmethod
    def commitment_file(elf_file_name: Optional[str] = None):
        if not elf_file_name:
            elf_file_name = ExecutionTraceGenerationService.elf_file()
            
        if elf_file_name == "zkverifier.elf":
            return "./execution_files/instruction_commitment_zk.txt"
        elif elf_file_name == "plainc.elf":
            return "./execution_files/instruction_commitment.txt"
        elif elf_file_name == "test_input.elf":
            return "./execution_files/instruction_commitment_input.txt"
        elif elf_file_name.startswith("option_"):
            # 옵션 관련 ELF 파일들은 공통 commitment 사용
            return "./execution_files/instruction_commitment.txt"
        else:
            return "./execution_files/instruction_commitment_input.txt"

    def __init__(self, base_path: str, option_type: Optional[str] = None):
        self.base_path = base_path
        self.option_type = option_type
        self.elf_file_name = self.elf_file(option_type)
        self.bitvmx_wrapper = BitVMXWrapper(base_path)

    def __call__(self, setup_uuid: str, input_hex: Optional[str] = None):
        self.bitvmx_wrapper.generate_execution_checkpoints(
            setup_uuid=setup_uuid, elf_file=self.elf_file_name, input_hex=input_hex
        )
        # return self.execution_trace_parsing_service(
        #     self.base_path + protocol_dict["setup_uuid"] + "/execution_trace.csv", protocol_dict
        # )
