"""
옵션 API View Models
"""

from typing import Dict, Any, Optional
from pydantic import BaseModel


class OptionRegisterInput(BaseModel):
    """옵션 상품 등록 입력"""
    option_type: str  # "CALL" or "PUT"
    strike_price: float  # USD
    expiry_timestamp: int  # Unix timestamp
    max_quantity: float
    premium_rate: float  # 0.01 = 1%


class OptionRegisterOutput(BaseModel):
    """옵션 상품 등록 출력"""
    product_id: str
    option_type: str
    strike_price: float
    expiry_timestamp: int
    max_quantity: float
    available_quantity: float
    base_premium_sats: int
    current_spot: float
    status: str
    created_at: str


class OptionPurchaseInput(BaseModel):
    """옵션 구매 입력"""
    product_id: str
    quantity: float
    buyer_address: str
    payment_txid: str
    setup_uuid: str


class OptionPurchaseOutput(BaseModel):
    """옵션 구매 출력"""
    purchase_id: str
    product_id: str
    buyer_address: str
    quantity: float
    premium_paid: int
    payment_txid: str
    setup_uuid: str
    input_hex: str
    strike_price: float
    current_spot: float
    expiry: int
    status: str
    purchased_at: str