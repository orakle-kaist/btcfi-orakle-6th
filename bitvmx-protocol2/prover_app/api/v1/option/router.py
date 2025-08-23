"""
옵션 관련 API 라우터
"""

from typing import Dict, Any, List, Optional
from fastapi import APIRouter, HTTPException, Body
from pydantic import BaseModel
from datetime import datetime, timedelta
import uuid
import os
import httpx

from prover_app.api.v1.option.crud.view_models import (
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
from prover_app.domain.models.option_product import (
    OptionProduct, OptionPurchase, OptionPool, OptionType, OptionStatus
)
from prover_app.persistences.option_storage import OptionStorage

router = APIRouter(prefix="/option", tags=["Option"])

# 옵션 저장소 초기화
option_storage = OptionStorage()

# Docker 서비스 URL
PROVER_URL = os.getenv("BITVMX_PROVER_URL", "http://localhost:8001")
VERIFIER_URL = os.getenv("BITVMX_VERIFIER_URL", "http://localhost:8080")


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
    setup_uuid: str,  # 기존 Setup UUID 사용
    option_type: str = "CALL",
    strike_price: float = 50000,
    expiry_days: int = 7,
    quantity: float = 1.0,
    premium_btc: float = 0.001
):
    """
    옵션 상품 등록 - 기존 Setup 사용
    
    이미 생성된 BitVMX Setup을 사용하여 옵션 상품을 등록합니다.
    Setup은 한 번만 생성하고 여러 옵션 상품을 등록할 수 있습니다.
    """
    try:
        # 풀 정보 확인 또는 생성
        pool = await option_storage.get_pool_by_setup(setup_uuid)
        if not pool:
            # 새 풀 생성
            pool = OptionPool(
                pool_id=f"POOL-{setup_uuid[:8]}",
                setup_uuid=setup_uuid,
                total_size_btc=1.39,  # 기존 Setup에서 사용한 금액
                available_btc=1.39,
                locked_btc=0.0
            )
            await option_storage.save_pool(pool)
        
        # 옵션 상품 생성
        product_id = f"OPT-{uuid.uuid4().hex[:8]}"
        expiry_date = datetime.now() + timedelta(days=expiry_days)
        
        product = OptionProduct(
            product_id=product_id,
            setup_uuid=setup_uuid,
            option_type=OptionType[option_type],
            strike_price=strike_price,
            expiry_date=expiry_date,
            premium_btc=premium_btc,
            quantity=quantity,
            pool_size_btc=pool.total_size_btc
        )
        
        # 저장
        await option_storage.save_product(product)
        
        # 풀 업데이트
        locked_amount = quantity * 0.1  # 예: 수량의 10%를 담보로 Lock
        pool.add_option(product_id, premium_btc, locked_amount)
        await option_storage.save_pool(pool)
        
        return {
            "product_id": product_id,
            "setup_uuid": setup_uuid,
            "option_type": option_type,
            "strike_price": strike_price,
            "expiry_date": expiry_date.isoformat(),
            "premium_btc": premium_btc,
            "quantity": quantity,
            "pool_available_btc": pool.available_btc,
            "message": "Option product registered successfully"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/purchase")
async def purchase_option(
    product_id: str,
    buyer_address: str
):
    """
    옵션 구매 - BitVMX Native Pre-sign 활용
    
    프리미엄을 지불하고 Pre-sign 트랜잭션을 받습니다.
    """
    try:
        # 옵션 상품 조회
        product = await option_storage.get_product(product_id)
        if not product:
            raise HTTPException(status_code=404, detail="Product not found")
        
        if product.status != OptionStatus.ACTIVE:
            raise HTTPException(status_code=400, detail="Product is not active")
        
        # Docker Prover에서 Setup 정보 조회
        async with httpx.AsyncClient() as client:
            # Input 제출하여 옵션 구매 기록
            input_data = {
                "setup_uuid": product.setup_uuid,
                "input_hex": BitVMXOptionIntegration.create_option_input_hex(
                    option_type=product.option_type.value,
                    strike_price=product.strike_price,
                    spot_price=product.strike_price,  # 구매 시점 가격
                    quantity=product.quantity
                )
            }
            
            response = await client.post(
                f"{PROVER_URL}/api/v1/input",
                json=input_data,
                timeout=10.0
            )
            
            if response.status_code != 200:
                raise HTTPException(status_code=500, detail="Failed to submit purchase to BitVMX")
        
        # Pre-sign 트랜잭션 그래프 생성 (실제로는 BitVMX Pre-sign 서비스 사용)
        # 여기서는 시뮬레이션
        presign_graph = {
            "option_params": {
                "type": product.option_type.value,
                "strike": int(product.strike_price * 100),
                "expiry": product.expiry_date.timestamp(),
                "quantity": product.quantity
            },
            "settlement_scripts": {
                "itm_script": f"OP_IF <price_proof> OP_CHECKSIG OP_ENDIF",
                "otm_script": f"OP_ELSE OP_RETURN OP_ENDIF"
            },
            "buyer_address": buyer_address
        }
        
        # 구매 정보 저장
        purchase_id = f"PUR-{uuid.uuid4().hex[:8]}"
        purchase = OptionPurchase(
            purchase_id=purchase_id,
            product_id=product_id,
            buyer_address=buyer_address,
            premium_paid_btc=product.premium_btc,
            presign_graph=presign_graph
        )
        await option_storage.save_purchase(purchase)
        
        return {
            "purchase_id": purchase_id,
            "product_id": product_id,
            "premium_btc": product.premium_btc,
            "expiry_date": product.expiry_date.isoformat(),
            "presign_graph": presign_graph,
            "message": "Option purchased successfully with Pre-sign guarantee"
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/settle")
async def settle_option(
    purchase_id: str,
    oracle_price: float
) -> Dict[str, Any]:
    """
    옵션 정산 - BitVMX Pre-sign 실행
    
    Oracle 가격으로 Pre-sign 트랜잭션을 실행합니다.
    """
    try:
        # 구매 정보 조회
        purchase = await option_storage.get_purchase(purchase_id)
        if not purchase:
            raise HTTPException(status_code=404, detail="Purchase not found")
        
        # 옵션 상품 조회
        product = await option_storage.get_product(purchase.product_id)
        if not product:
            raise HTTPException(status_code=404, detail="Product not found")
        
        # 만기 확인
        if datetime.now() < product.expiry_date:
            raise HTTPException(status_code=400, detail="Option has not expired yet")
        
        # ITM/OTM 판단 및 수익 계산
        is_itm = product.is_itm(oracle_price)
        payoff_btc = product.calculate_payoff(oracle_price) if is_itm else 0
        
        # BitVMX Input 실행 (실제 정산)
        input_hex = BitVMXOptionIntegration.create_option_input_hex(
            option_type=product.option_type.value,
            strike_price=product.strike_price,
            spot_price=oracle_price,
            quantity=product.quantity
        )
        
        # Docker Prover에 정산 제출
        async with httpx.AsyncClient() as client:
            input_data = {
                "setup_uuid": product.setup_uuid,
                "input_hex": input_hex
            }
            
            response = await client.post(
                f"{PROVER_URL}/api/v1/input",
                json=input_data,
                timeout=10.0
            )
            
            if response.status_code == 200:
                # Next Step 트리거
                next_step_response = await client.post(
                    f"{PROVER_URL}/api/v1/next_step",
                    json={"setup_uuid": product.setup_uuid},
                    timeout=30.0
                )
        
        # 정산 트랜잭션 ID (실제로는 BitVMX에서 생성)
        settlement_txid = f"settle-{uuid.uuid4().hex[:16]}"
        
        # 상품 상태 업데이트
        await option_storage.update_product_status(
            product.product_id,
            OptionStatus.SETTLED,
            settlement_price=oracle_price,
            settlement_txid=settlement_txid
        )
        
        # 구매 정보 업데이트
        purchase.settlement_claimed = True
        purchase.status = "SETTLED"
        await option_storage.save_purchase(purchase)
        
        # 풀 업데이트
        pool = await option_storage.get_pool_by_setup(product.setup_uuid)
        if pool:
            pool.settle_option(product.product_id, payoff_btc)
            await option_storage.save_pool(pool)
        
        return {
            "settlement_txid": settlement_txid,
            "purchase_id": purchase_id,
            "product_id": product.product_id,
            "oracle_price": oracle_price,
            "strike_price": product.strike_price,
            "is_itm": is_itm,
            "payoff_btc": payoff_btc,
            "input_hex": input_hex,
            "message": f"Settlement executed: {'ITM' if is_itm else 'OTM'} - {payoff_btc:.8f} BTC payout"
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


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