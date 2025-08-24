from pydantic import BaseModel

class FundPostV1Input(BaseModel):
    setup_uuid: str
    funding_tx_id: str
    funding_index: int
    funding_amount_of_satoshis: int
    secret_origin_of_funds: str
    prover_destination_address: str

class FundPostV1Output(BaseModel):
    success: bool
    message: str