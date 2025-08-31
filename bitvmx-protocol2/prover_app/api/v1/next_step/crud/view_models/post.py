from pydantic import BaseModel
from typing import Optional

class NextStepPostV1Input(BaseModel):
    setup_uuid: str
    force_resign: Optional[bool] = False
    regen_transactions: Optional[bool] = False  # Regenerate transactions from scratch

class NextStepPostV1Output(BaseModel):
    message: str
    next_step: str