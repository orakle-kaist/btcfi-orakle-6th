import json
import os

from bitvmx_protocol_library.bitvmx_protocol_definition.entities.bitvmx_protocol_setup_properties_dto import (
    BitVMXProtocolSetupPropertiesDTO,
)
from prover_app.domain.persistences.interfaces.bitvmx_protocol_setup_properties_dto_persistence_interface import (
    BitVMXProtocolSetupPropertiesDTOPersistenceInterface,
)


class BitVMXProtocolSetupPropertiesDTOJsonPersistence(
    BitVMXProtocolSetupPropertiesDTOPersistenceInterface
):

    def __init__(self, base_path: str):
        self.base_path = base_path
        self.file_name = "bitvmx_protocol_setup_properties_dto.json"

    def create(
        self,
        bitvmx_protocol_setup_properties_dto: BitVMXProtocolSetupPropertiesDTO,
    ) -> bool:
        folder_path = f"{self.base_path}/{bitvmx_protocol_setup_properties_dto.setup_uuid}"
        if not os.path.exists(folder_path):
            os.makedirs(folder_path)
        with open(f"{folder_path}/{self.file_name}", "w") as file:
            json.dump(bitvmx_protocol_setup_properties_dto.model_dump(), file)
        return True

    def get(self, setup_uuid: str) -> BitVMXProtocolSetupPropertiesDTO:
        """Load DTO, with backward-compatible fallback between directories.

        Historically, DTOs were written under `verifier_files/`. We now store
        them under `prover_files/` to keep all prover artifacts together.
        This loader first tries the configured base_path and then falls back to
        the alternate directory to remain compatible with existing setups.
        """
        primary_path = f"{self.base_path}/{setup_uuid}/{self.file_name}"
        alt_base = "verifier_files" if self.base_path == "prover_files" else "prover_files"
        alt_path = f"{alt_base}/{setup_uuid}/{self.file_name}"

        if os.path.exists(primary_path):
            path = primary_path
        elif os.path.exists(alt_path):
            path = alt_path
        else:
            # Raise FileNotFoundError to preserve previous behavior
            path = primary_path  # for message
        with open(path, "r") as file:
            json_data = json.load(file)
        return BitVMXProtocolSetupPropertiesDTO(**json_data)

    def update(
        self,
        bitvmx_protocol_setup_properties_dto: BitVMXProtocolSetupPropertiesDTO,
    ) -> bool:
        """Persist an updated DTO to disk.

        The setup controller updates fields like funding_tx_id/index after
        creating/broadcasting the generated funding transaction. Without this
        method, those updates are lost and subsequent steps (e.g. next_step)
        operate on stale data, causing broadcasts to be skipped.
        """
        folder_path = f"{self.base_path}/{bitvmx_protocol_setup_properties_dto.setup_uuid}"
        if not os.path.exists(folder_path):
            os.makedirs(folder_path)
        file_path = f"{folder_path}/{self.file_name}"
        with open(file_path, "w") as file:
            json.dump(bitvmx_protocol_setup_properties_dto.model_dump(), file)
        return True
