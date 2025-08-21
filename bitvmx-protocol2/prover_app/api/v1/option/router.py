"""
옵션 관련 API 라우터
"""

from typing import Dict, Any, Annotated
from fastapi import APIRouter, HTTPException, Body
from pydantic import BaseModel

from prover_app.api.v1.option.crud.v1.view_models import (
    OptionRegisterInput,
    OptionPurchaseInput
)
from prover_app.dependency_injection.api.v1.option import (
    OptionRegisterViewControllers,
    OptionPurchaseViewControllers
)
from prover_app.domain.controllers.v1.option.option_integration import (
    BitVMXOptionIntegration
)

router = APIRouter(prefix="/option", tags=["Option"])


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


@router.post("/register")
async def register_option_product(
    option_type: str = "CALL",
    strike_price: float = 50000,
    expiry_days: int = 7,
    funding_amount_btc: float = 0.01
):
    """
    옵션 상품 등록 - BitVMX Setup 활용
    
    기존 BitVMX Setup 프로세스를 사용하여 옵션 풀 자금을 Lock합니다.
    """
    from prover_app.api.v1.setup.crud.v1.view_models.post import SetupPostV1Input
    from prover_app.dependency_injection.api.v1.setup import SetupPostViewControllers
    
    # BitVMX Setup 입력 생성
    setup_input = SetupPostV1Input(
        max_amount_of_steps=100,  # Pre-sign은 간단하므로 적게
        amount_of_bits_wrong_step_search=2,
        funding_tx_id="dummy_funding_tx",  # 실제로는 UTXO 조회 필요
        funding_index=0,
        funding_amount_of_satoshis=int(funding_amount_btc * 100_000_000),
        secret_origin_of_funds="cVdte9ei2xsVjB8YvySNSkHpEQJ5VHhTjq5BvkBytbgNrWNgz4Xq",
        verifier_list=[],  # Pre-sign이므로 Verifier 불필요
        prover_destination_address="tb1qt8rdur557nz338g3lekc6458pj0dl63c0s9904",
        prover_signature_private_key="d8a1e1224e63135765bde9dc8a2c8e403eee8be73d3589d58c5ddbf9dce3fdf4",
        prover_signature_public_key="03bf751f0d2d22e6f0163c9acaa14ae04e6e1a004cb4a24d893c1f86314e79d5de",
        amount_of_input_words=4  # 옵션 파라미터용
    )
    
    # 기존 Setup 컨트롤러 사용
    view_controller = SetupPostViewControllers.v1()
    setup_result = await view_controller(setup_post_view_input=setup_input)
    
    # 옵션 메타데이터 추가
    return {
        "setup_uuid": setup_result.get("setup_uuid"),
        "option_type": option_type,
        "strike_price": strike_price,
        "expiry_days": expiry_days,
        "pool_size_btc": funding_amount_btc,
        "message": "Option product registered using BitVMX Setup"
    }


@router.post("/purchase")
async def purchase_option(
    setup_uuid: str,
    buyer_address: str,
    option_type: str = "CALL",
    strike_price: float = 50000
):
    """
    옵션 구매 - BitVMX Native Pre-sign 활용
    
    프리미엄을 지불하고 Pre-sign 트랜잭션을 받습니다.
    기존 bitvmx_native_presign_service를 사용합니다.
    """
    from datetime import datetime, timedelta
    from prover_app.dependency_injection.persistences.bitvmx_protocol_setup_properties_dto_persistences import (
        BitVMXProtocolSetupPropertiesDtoPersistences
    )
    
    # Setup 정보 조회
    setup_persistence = BitVMXProtocolSetupPropertiesDtoPersistences.v1()
    setup_dto = await setup_persistence.load(setup_uuid)
    
    if not setup_dto:
        raise HTTPException(status_code=404, detail="Setup not found")
    
    # Pre-sign Service 가져오기
    presign_service = OptionPurchaseViewControllers.v1()
    
    # Pre-sign 트랜잭션 그래프 생성
    expiry_timestamp = int((datetime.now() + timedelta(days=7)).timestamp())
    
    presign_graph = presign_service.create_option_settlement_graph(
        bitvmx_protocol_setup_properties_dto=setup_dto,
        option_type=option_type,
        strike_price=int(strike_price * 100),  # cents
        expiry_timestamp=expiry_timestamp,
        buyer_address=buyer_address
    )
    
    return {
        "purchase_id": f"PUR-{setup_uuid[:8]}-{int(datetime.now().timestamp())}",
        "setup_uuid": setup_uuid,
        "presign_graph": presign_graph,
        "message": "Pre-signed transactions delivered using BitVMX native presign service"
    }


@router.post("/settle")
async def settle_option(
    setup_uuid: str,
    oracle_price: float,
    presign_graph: Dict[str, Any]
) -> Dict[str, Any]:
    """
    옵션 정산 - BitVMX Pre-sign 실행
    
    Oracle 가격으로 Pre-sign 트랜잭션을 실행합니다.
    기존 BitVMX Input 실행 메커니즘을 활용합니다.
    """
    from prover_app.dependency_injection.api.v1.option import OptionPurchaseViewControllers
    
    # Pre-sign Service 가져오기
    presign_service = OptionPurchaseViewControllers.v1()
    
    # Oracle 증명 생성 (실제로는 Oracle Node에서)
    oracle_proof = {
        "price": int(oracle_price * 100),
        "signature": "oracle_signature_placeholder",
        "merkle_root": "merkle_root_placeholder"
    }
    
    # Pre-sign 정산 실행
    settlement_txid = presign_service.execute_presigned_settlement(
        presign_graph=presign_graph,
        oracle_price=int(oracle_price * 100),
        oracle_proof=oracle_proof
    )
    
    # ITM/OTM 판단
    option_type = presign_graph["option_params"]["type"]
    strike_price = presign_graph["option_params"]["strike"] / 100
    is_itm = (oracle_price > strike_price) if option_type == "CALL" else (oracle_price < strike_price)
    
    return {
        "settlement_txid": settlement_txid,
        "oracle_price": oracle_price,
        "is_itm": is_itm,
        "message": "Settlement executed using BitVMX native presign"
    }


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
        from prover_app.domain.controllers.v1.option.option_controller import OptionType, OptionParameters, OptionController
        
        option_controller = OptionController()
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