"""
옵션 View Controller
"""

from typing import Dict, Any
from prover_app.api.v1.option.crud.v1.view_models import (
    OptionRegisterInput,
    OptionRegisterOutput,
    OptionPurchaseInput,
    OptionPurchaseOutput
)
from prover_app.domain.controllers.v1.option.option_controller import OptionController


class OptionRegisterViewController:
    """옵션 상품 등록 View Controller"""
    
    def __init__(self):
        self.option_controller = OptionController()
    
    async def __call__(
        self,
        register_input: OptionRegisterInput
    ) -> OptionRegisterOutput:
        """옵션 상품 등록"""
        result = await self.option_controller.register_option_product(
            option_type=register_input.option_type,
            strike_price=register_input.strike_price,
            expiry_timestamp=register_input.expiry_timestamp,
            max_quantity=register_input.max_quantity,
            premium_rate=register_input.premium_rate
        )
        
        return OptionRegisterOutput(**result)


class OptionPurchaseViewController:
    """옵션 구매 View Controller"""
    
    def __init__(self):
        self.option_controller = OptionController()
    
    async def __call__(
        self,
        purchase_input: OptionPurchaseInput
    ) -> OptionPurchaseOutput:
        """옵션 구매"""
        result = await self.option_controller.purchase_option(
            product_id=purchase_input.product_id,
            quantity=purchase_input.quantity,
            buyer_address=purchase_input.buyer_address,
            payment_txid=purchase_input.payment_txid,
            setup_uuid=purchase_input.setup_uuid
        )
        
        return OptionPurchaseOutput(**result)