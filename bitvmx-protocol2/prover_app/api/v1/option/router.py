"""
옵션 관련 API 라우터
"""

from typing import Dict, Any
from fastapi import APIRouter, HTTPException, Body
from pydantic import BaseModel

from prover_app.domain.controllers.v1.option.option_controller import OptionController
from prover_app.domain.controllers.v1.option.option_integration import (
    BitVMXOptionIntegration,
    prepare_option_setup,
    prepare_option_input,
    process_option_settlement
)

router = APIRouter(prefix="/option", tags=["Option"])

# 옵션 컨트롤러 인스턴스
option_controller = OptionController()
# BitVMX 통합 모듈
option_integration = BitVMXOptionIntegration()


class OptionProductRegistrationRequest(BaseModel):
    """옵션 상품 등록 요청"""
    option_type: str  # "CALL" or "PUT"
    strike_price: float  # USD
    expiry_timestamp: int  # Unix timestamp
    max_quantity: float
    premium_rate: float  # 0.01 = 1%


class OptionPurchaseRequest(BaseModel):
    """옵션 구매 요청"""
    product_id: str
    quantity: float
    buyer_address: str
    payment_txid: str
    setup_uuid: str


class OptionSettlementRequest(BaseModel):
    """옵션 정산 요청"""
    setup_uuid: str
    price_proof: Dict[str, Any]


class OptionInputRequest(BaseModel):
    """옵션 입력 데이터 생성 요청"""
    option_type: str  # "CALL" or "PUT"
    strike_price: float  # USD
    spot_price: float  # USD
    quantity: float


@router.post("/product/register")
async def register_option_product(
    request: OptionProductRegistrationRequest = Body()
) -> Dict[str, Any]:
    """
    옵션 상품 등록 (운영자)
    
    새로운 옵션 상품을 등록합니다.
    """
    try:
        result = await option_controller.register_option_product(
            option_type=request.option_type,
            strike_price=request.strike_price,
            expiry_timestamp=request.expiry_timestamp,
            max_quantity=request.max_quantity,
            premium_rate=request.premium_rate
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/purchase")
async def purchase_option(
    request: OptionPurchaseRequest = Body()
) -> Dict[str, Any]:
    """
    옵션 구매 (사용자)
    
    프리미엄을 지불하고 옵션을 구매합니다.
    BitVMX pre-sign을 받아 만기 시 자동 정산이 보장됩니다.
    """
    try:
        result = await option_controller.purchase_option(
            product_id=request.product_id,
            quantity=request.quantity,
            buyer_address=request.buyer_address,
            payment_txid=request.payment_txid,
            setup_uuid=request.setup_uuid
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/settle")
async def settle_option(
    request: OptionSettlementRequest = Body()
) -> Dict[str, Any]:
    """
    옵션 정산
    
    만기 시 옵션을 정산합니다.
    """
    try:
        result = await option_controller.execute_settlement(
            setup_uuid=request.setup_uuid,
            price_proof=request.price_proof
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/create-input")
async def create_option_input(
    request: OptionInputRequest = Body()
) -> Dict[str, Any]:
    """
    옵션 입력 데이터 생성 (BitVMX 통합)
    
    BitVMX Input 컨트롤러에서 직접 사용 가능한 hex 생성
    """
    try:
        # BitVMX 통합 모듈 사용
        input_hex = BitVMXOptionIntegration.create_option_input_hex(
            option_type=request.option_type,
            strike_price=request.strike_price,
            spot_price=request.spot_price,
            quantity=request.quantity
        )
        
        # 수익 계산
        payoff_sats = BitVMXOptionIntegration.calculate_payoff(input_hex)
        
        return {
            "input_hex": input_hex,
            "params": {
                "option_type": request.option_type,
                "strike_price": request.strike_price,
                "spot_price": request.spot_price,
                "quantity": request.quantity
            },
            "expected_payoff_sats": payoff_sats,
            "usage": "Use this input_hex with /api/v1/input endpoint"
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/calculate-payoff")
async def calculate_payoff(
    option_type: str,
    strike_price: float,
    spot_price: float,
    quantity: float
) -> Dict[str, Any]:
    """
    옵션 수익 계산
    
    주어진 파라미터로 옵션 만기 시 수익을 계산합니다.
    """
    try:
        from prover_app.domain.controllers.v1.option.option_controller import OptionType, OptionParameters
        
        option_params = OptionParameters(
            option_type=OptionType[option_type],
            strike_price=int(strike_price * 100),
            spot_price=int(spot_price * 100),
            quantity=int(quantity * 100),
            expiry_timestamp=0,  # Not needed for payoff calculation
            premium=0  # Not needed for payoff calculation
        )
        
        payoff_sats = option_controller.calculate_option_payoff(option_params)
        
        return {
            "payoff_sats": payoff_sats,
            "payoff_btc": payoff_sats / 100_000_000,
            "params": {
                "option_type": option_type,
                "strike_price": strike_price,
                "spot_price": spot_price,
                "quantity": quantity
            }
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))