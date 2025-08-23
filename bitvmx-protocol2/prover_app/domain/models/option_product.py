"""
Option Product 모델 - 등록된 옵션 상품 관리
"""

from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from enum import Enum
from pydantic import BaseModel, Field
import json


class OptionType(str, Enum):
    CALL = "CALL"
    PUT = "PUT"


class OptionStatus(str, Enum):
    ACTIVE = "ACTIVE"  # 활성 상품
    EXPIRED = "EXPIRED"  # 만기
    SETTLED = "SETTLED"  # 정산완료
    CANCELLED = "CANCELLED"  # 취소


class OptionProduct(BaseModel):
    """옵션 상품 정보"""
    product_id: str = Field(description="옵션 상품 ID")
    setup_uuid: str = Field(description="BitVMX Setup UUID")
    option_type: OptionType
    strike_price: float = Field(description="행사가격 (USD)")
    expiry_date: datetime = Field(description="만기일")
    premium_btc: float = Field(description="프리미엄 (BTC)")
    quantity: float = Field(description="수량")
    status: OptionStatus = OptionStatus.ACTIVE
    created_at: datetime = Field(default_factory=datetime.now)
    pool_size_btc: float = Field(description="풀 사이즈 (BTC)")
    
    # Greeks
    delta: Optional[float] = None
    gamma: Optional[float] = None
    theta: Optional[float] = None
    vega: Optional[float] = None
    
    # Settlement info
    settlement_price: Optional[float] = None
    settlement_txid: Optional[str] = None
    settlement_date: Optional[datetime] = None
    
    def is_itm(self, spot_price: float) -> bool:
        """ITM(In The Money) 여부 확인"""
        if self.option_type == OptionType.CALL:
            return spot_price > self.strike_price
        else:  # PUT
            return spot_price < self.strike_price
    
    def calculate_payoff(self, spot_price: float) -> float:
        """만기 시 수익 계산 (BTC)"""
        if self.option_type == OptionType.CALL:
            payoff_usd = max(0, spot_price - self.strike_price) * self.quantity
        else:  # PUT
            payoff_usd = max(0, self.strike_price - spot_price) * self.quantity
        
        # USD to BTC conversion (spot_price 기준)
        payoff_btc = payoff_usd / spot_price if spot_price > 0 else 0
        return payoff_btc
    
    def to_dict(self) -> Dict[str, Any]:
        """Dictionary 변환"""
        return {
            "product_id": self.product_id,
            "setup_uuid": self.setup_uuid,
            "option_type": self.option_type.value,
            "strike_price": self.strike_price,
            "expiry_date": self.expiry_date.isoformat(),
            "premium_btc": self.premium_btc,
            "quantity": self.quantity,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "pool_size_btc": self.pool_size_btc,
            "greeks": {
                "delta": self.delta,
                "gamma": self.gamma,
                "theta": self.theta,
                "vega": self.vega
            },
            "settlement": {
                "price": self.settlement_price,
                "txid": self.settlement_txid,
                "date": self.settlement_date.isoformat() if self.settlement_date else None
            }
        }


class OptionPurchase(BaseModel):
    """옵션 구매 정보"""
    purchase_id: str = Field(description="구매 ID")
    product_id: str = Field(description="옵션 상품 ID")
    buyer_address: str = Field(description="구매자 주소")
    purchase_date: datetime = Field(default_factory=datetime.now)
    premium_paid_btc: float = Field(description="지불한 프리미엄")
    presign_graph: Dict[str, Any] = Field(description="Pre-sign 트랜잭션 그래프")
    status: str = Field(default="ACTIVE")
    settlement_claimed: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "purchase_id": self.purchase_id,
            "product_id": self.product_id,
            "buyer_address": self.buyer_address,
            "purchase_date": self.purchase_date.isoformat(),
            "premium_paid_btc": self.premium_paid_btc,
            "presign_graph": self.presign_graph,
            "status": self.status,
            "settlement_claimed": self.settlement_claimed
        }


class OptionPool(BaseModel):
    """옵션 유동성 풀 상태"""
    pool_id: str = Field(description="풀 ID")
    setup_uuid: str = Field(description="BitVMX Setup UUID")
    total_size_btc: float = Field(description="전체 풀 사이즈")
    available_btc: float = Field(description="사용 가능한 BTC")
    locked_btc: float = Field(description="옵션에 Lock된 BTC")
    
    # Pool delta management
    net_delta: float = Field(default=0.0, description="Net Delta")
    target_delta: float = Field(default=0.0, description="Target Delta (0 for neutral)")
    
    # Active options
    active_options: List[str] = Field(default_factory=list, description="활성 옵션 상품 ID 리스트")
    
    # Statistics
    total_premium_collected: float = Field(default=0.0)
    total_payouts: float = Field(default=0.0)
    created_at: datetime = Field(default_factory=datetime.now)
    last_updated: datetime = Field(default_factory=datetime.now)
    
    def update_delta(self, options: List[OptionProduct], spot_price: float):
        """풀의 Net Delta 업데이트"""
        self.net_delta = sum(
            opt.delta * opt.quantity for opt in options 
            if opt.status == OptionStatus.ACTIVE and opt.delta
        )
        self.last_updated = datetime.now()
    
    def add_option(self, product_id: str, premium_btc: float, locked_amount: float):
        """옵션 추가"""
        self.active_options.append(product_id)
        self.total_premium_collected += premium_btc
        self.available_btc -= locked_amount
        self.locked_btc += locked_amount
        self.last_updated = datetime.now()
    
    def settle_option(self, product_id: str, payout_btc: float):
        """옵션 정산"""
        if product_id in self.active_options:
            self.active_options.remove(product_id)
        self.total_payouts += payout_btc
        self.locked_btc -= payout_btc  # Unlock funds
        if payout_btc == 0:  # OTM - return funds to pool
            self.available_btc += self.locked_btc
        self.last_updated = datetime.now()
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "pool_id": self.pool_id,
            "setup_uuid": self.setup_uuid,
            "total_size_btc": self.total_size_btc,
            "available_btc": self.available_btc,
            "locked_btc": self.locked_btc,
            "net_delta": self.net_delta,
            "target_delta": self.target_delta,
            "active_options": self.active_options,
            "statistics": {
                "total_premium_collected": self.total_premium_collected,
                "total_payouts": self.total_payouts,
                "profit": self.total_premium_collected - self.total_payouts
            },
            "created_at": self.created_at.isoformat(),
            "last_updated": self.last_updated.isoformat()
        }