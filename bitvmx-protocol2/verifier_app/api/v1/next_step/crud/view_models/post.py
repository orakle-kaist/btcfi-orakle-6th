from pydantic import BaseModel


class NextStepPostV1Input(BaseModel):
    setup_id: str


class NextStepPostV1Output(BaseModel):
    next_step: str