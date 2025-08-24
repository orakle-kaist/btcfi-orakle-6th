from pydantic import BaseModel
from typing import Dict, Any


class SignaturesPostV1Input(BaseModel):
    setup_uuid: str
    prover_signatures_dto: Dict[str, Any]  # Added for signature exchange


class SignaturesPostV1Output(BaseModel):
    verifier_signatures_dto: Any  # BitVMXVerifierSignaturesDTO