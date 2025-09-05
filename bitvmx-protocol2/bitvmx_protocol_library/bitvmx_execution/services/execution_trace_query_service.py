import os
import re
from typing import Optional

import pandas as pd

from bitvmx_protocol_library.bitvmx_execution.services.bitvmx_wrapper import BitVMXWrapper


class ExecutionTraceQueryService:

    def __init__(self, base_path: str):
        self.base_path = base_path
        self.hashes_checkpoint_interval = 1000000
        self.bitvmx_wrapper = BitVMXWrapper(base_path)

    def get_last_step(self, setup_uuid: str):
        directory = self.base_path + setup_uuid
        pattern = re.compile(r"^checkpoint\.\d+\.json$")
        
        print(f"[DEBUG TraceQuery] Getting last step from directory: {directory}")

        # List all files in the specified directory
        if not os.path.exists(directory):
            print(f"[ERROR TraceQuery] Directory does not exist: {directory}")
            raise Exception(f"Directory does not exist: {directory}")
            
        files = [f for f in os.listdir(directory) if os.path.isfile(os.path.join(directory, f))]
        print(f"[DEBUG TraceQuery] Found {len(files)} total files")

        # Filter files that match the pattern
        checkpoint_files = [f for f in files if pattern.match(f)]
        print(f"[DEBUG TraceQuery] Found {len(checkpoint_files)} checkpoint files")
        
        if not checkpoint_files:
            print(f"[ERROR TraceQuery] No checkpoint files found in {directory}")
            print(f"[ERROR TraceQuery] Available files: {files[:10]}..." if len(files) > 10 else f"{files}")
            raise Exception(f"No checkpoint files found in {directory}")
            
        checkpoint_indexes = list(map(lambda filename: int(filename[11:-5]), checkpoint_files))
        max_index = max(checkpoint_indexes)
        print(f"[DEBUG TraceQuery] Max checkpoint index: {max_index}")
        return max_index

    @staticmethod
    def trace_header():
        return [
            "read1_address",
            "read1_value",
            "read1_last_step",
            "read2_address",
            "read2_value",
            "read2_last_step",
            "read_pc_address",
            "read_pc_micro",
            "read_pc_opcode",
            "write_address",
            "write_value",
            "write_pc",
            "write_micro",
            "write_trace",
            "step_hash",
        ]

    def get_overflow_trace(
        self, setup_uuid: str, last_step: int, index: int, input_hex: Optional[str]
    ):
        assert index > last_step
        write_address_hex = "f" * 8
        write_value_hex = "f" * 8
        write_pc_hex = "f" * 8
        write_micro_hex = "f" * 2
        write_trace = write_address_hex + write_value_hex + write_pc_hex + write_micro_hex
        result = self.bitvmx_wrapper.get_execution_trace(
            setup_uuid=setup_uuid, index=last_step, input_hex=input_hex
        )
        step_hash = result.replace("\n", "").split(";")[-1]
        step_dict = {
            "read1_address": "f" * 8,
            "read1_value": "f" * 8,
            "read1_last_step": "f" * 8,
            "read2_address": "f" * 8,
            "read2_value": "f" * 8,
            "read2_last_step": "f" * 8,
            "read_pc_address": "f" * 8,
            "read_pc_micro": "f" * 2,
            "read_pc_opcode": "f" * 8,
            "write_address": "f" * 8,
            "write_value": "f" * 8,
            "write_pc": "f" * 8,
            "write_micro": "f" * 2,
            "write_trace": write_trace,
            "step_hash": step_hash,
        }
        return pd.DataFrame([step_dict]).iloc[0]

    def get_step_trace(self, setup_uuid: str, index: int, input_hex: Optional[str]):
        print(f"[DEBUG TraceQuery] Getting step trace for index {index}")
        last_step = self.get_last_step(setup_uuid=setup_uuid)
        headers = self.trace_header()
        if index > last_step:
            print(f"[DEBUG TraceQuery] Index {index} > last_step {last_step}, using overflow trace")
            trace = self.get_overflow_trace(
                setup_uuid=setup_uuid, last_step=last_step, index=index, input_hex=input_hex
            )
            return trace
        else:
            print(f"[DEBUG TraceQuery] Getting execution trace for index {index}")
            result = self.bitvmx_wrapper.get_execution_trace(
                setup_uuid=setup_uuid, index=index, input_hex=input_hex
            )
            print(f"[DEBUG TraceQuery] Raw trace result length: {len(result)}")
            print(f"[DEBUG TraceQuery] Raw trace preview: {result[:200]}..." if len(result) > 200 else f"{result}")
            return pd.DataFrame([result.replace("\n", "").split(";")], columns=headers).iloc[0]

    def __call__(self, setup_uuid: str, index: int, input_hex: Optional[str]):
        print(f"[DEBUG TraceQuery] ExecutionTraceQueryService called with index={index}, setup_uuid={setup_uuid}")
        trace = self.get_step_trace(setup_uuid=setup_uuid, index=index + 1, input_hex=input_hex)
        print(f"[DEBUG TraceQuery] Trace step_hash: {trace.get('step_hash', 'N/A') if hasattr(trace, 'get') else trace['step_hash']}")
        return trace
