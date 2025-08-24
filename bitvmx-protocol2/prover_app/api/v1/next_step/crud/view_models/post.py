from pydantic import BaseModel

class NextStepPostV1Input(BaseModel):
    setup_uuid: str

class NextStepPostV1Output(BaseModel):
    message: str
    next_step: str