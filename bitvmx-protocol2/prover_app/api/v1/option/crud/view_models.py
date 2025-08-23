from pydantic import BaseModel
from typing import Optional

class OptionRegisterInput(BaseModel):
    option_type: str  # "CALL" or "PUT"
    strike_price: float
    expiry_timestamp: int
    premium_sats: int

class OptionPurchaseInput(BaseModel):
    option_id: str
    quantity: float