from pydantic import BaseModel

class InputPostV1Input(BaseModel):
    setup_uuid: str
    input_hex: str

class InputPostV1Output(BaseModel):
    execution_trace_id: str
    message: str