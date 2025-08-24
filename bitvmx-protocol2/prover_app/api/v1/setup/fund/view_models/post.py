from pydantic import BaseModel

class SetupFundPostV1Input(BaseModel):
    setup_uuid: str
    funding_tx_id: str
    funding_index: int
    funding_amount_of_satoshis: int

class SetupFundPostV1Output(BaseModel):
    message: str
