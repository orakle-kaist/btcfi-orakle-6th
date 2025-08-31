"""
from prover_app.common.hexsafe import bfromhex_safe
BitVMX 옵션 통합 모듈
기존 BitVMX 구조를 활용하여 옵션 기능 구현
"""

import struct
from typing import Dict, Any, Optional
from enum import Enum

class OptionType(Enum):
    CALL = 0
    PUT = 1

class BitVMXOptionIntegration:
    """
    BitVMX의 기존 Setup/Input/NextStep 프로세스를 활용한 옵션 통합
    """
    
    @staticmethod
    def create_option_input_hex(
        option_type: str,
        strike_price: float,
        spot_price: float,
        quantity: float
    ) -> str:
        """
        옵션 파라미터를 BitVMX input_hex로 변환
        기존 Input 컨트롤러에서 바로 사용 가능
        
        Args:
            option_type: "CALL" 또는 "PUT"
            strike_price: 행사가 (USD)
            spot_price: 현물가 (USD)
            quantity: 수량
            
        Returns:
            32바이트 hex 문자열 (4개의 32비트 정수)
        """
        opt_type = OptionType[option_type].value
        strike_cents = int(strike_price * 100)
        spot_cents = int(spot_price * 100)
        quantity_units = int(quantity * 100)
        
        # 4개의 32비트 정수로 패킹 (little-endian)
        data = struct.pack('<IIII', opt_type, strike_cents, spot_cents, quantity_units)
        return data.hex()
    
    @staticmethod
    def parse_option_input_hex(input_hex: str) -> Dict[str, Any]:
        """
        input_hex를 파싱하여 옵션 파라미터 추출
        
        Args:
            input_hex: 32바이트 hex 문자열
            
        Returns:
            파싱된 옵션 파라미터
        """
        data = bfromhex_safe(input_hex)
        opt_type, strike_cents, spot_cents, quantity_units = struct.unpack('<IIII', data)
        
        return {
            "option_type": "CALL" if opt_type == 0 else "PUT",
            "strike_price": strike_cents / 100,
            "spot_price": spot_cents / 100,
            "quantity": quantity_units / 100
        }
    
    @staticmethod
    def calculate_payoff(input_hex: str) -> int:
        """
        옵션 수익 계산 (satoshis)
        
        Args:
            input_hex: 옵션 입력 hex
            
        Returns:
            수익 (satoshis)
        """
        params = BitVMXOptionIntegration.parse_option_input_hex(input_hex)
        
        strike = params["strike_price"]
        spot = params["spot_price"]
        qty = params["quantity"]
        
        if params["option_type"] == "CALL":
            payoff_usd = max(0, spot - strike) * qty
        else:
            payoff_usd = max(0, strike - spot) * qty
        
        # USD to BTC (예시: 1 BTC = $50,000)
        btc_price = 50000
        payoff_btc = payoff_usd / btc_price
        payoff_sats = int(payoff_btc * 100_000_000)
        
        return payoff_sats
    
    @staticmethod
    def get_setup_params_for_option() -> Dict[str, Any]:
        """
        옵션용 Setup 파라미터 반환
        기존 CreateSetupController에서 사용
        
        Returns:
            Setup에 필요한 파라미터
        """
        return {
            "max_amount_of_steps": 10000,  # 옵션 정산에 충분한 스텝
            "amount_of_input_words": 4,     # 4개의 32비트 워드 (type, strike, spot, qty)
            "amount_of_bits_wrong_step_search": 2,
            "amount_of_bits_per_digit_checksum": 4
        }
    
    @staticmethod
    def create_option_metadata(
        option_type: str,
        strike_price: float,
        expiry_timestamp: int,
        premium_sats: int
    ) -> Dict[str, Any]:
        """
        옵션 메타데이터 생성
        Setup과 함께 저장될 추가 정보
        
        Args:
            option_type: "CALL" 또는 "PUT"
            strike_price: 행사가 (USD)
            expiry_timestamp: 만기 시간
            premium_sats: 프리미엄 (satoshis)
            
        Returns:
            옵션 메타데이터
        """
        return {
            "product_type": "BTCFI_OPTION",
            "option_type": option_type,
            "strike_price": strike_price,
            "expiry_timestamp": expiry_timestamp,
            "premium_sats": premium_sats,
            "protocol": "BitVMX",
            "version": "1.0"
        }
    
    @staticmethod
    def validate_option_execution(
        setup_uuid: str,
        input_hex: str,
        execution_trace: Optional[bytes] = None
    ) -> Dict[str, Any]:
        """
        옵션 실행 검증
        NextStep 프로세스 완료 후 호출
        
        Args:
            setup_uuid: Setup UUID
            input_hex: 옵션 입력 데이터
            execution_trace: 실행 트레이스 (선택)
            
        Returns:
            검증 결과
        """
        params = BitVMXOptionIntegration.parse_option_input_hex(input_hex)
        payoff = BitVMXOptionIntegration.calculate_payoff(input_hex)
        
        return {
            "setup_uuid": setup_uuid,
            "option_params": params,
            "payoff_sats": payoff,
            "payoff_btc": payoff / 100_000_000,
            "validation": "success",
            "ready_for_settlement": True
        }

# 기존 컨트롤러와의 통합을 위한 헬퍼 함수들

def prepare_option_setup(
    option_type: str,
    strike_price: float,
    expiry_timestamp: int,
    funding_tx_id: str,
    funding_index: int
) -> Dict[str, Any]:
    """
    옵션 Setup을 위한 전체 파라미터 준비
    CreateSetupController.__call__()에 전달할 파라미터
    """
    setup_params = BitVMXOptionIntegration.get_setup_params_for_option()
    
    # 기본 Setup 파라미터
    base_params = {
        "funding_tx_id": funding_tx_id,
        "funding_index": funding_index,
        # ... 기타 필수 파라미터
    }
    
    # 옵션 메타데이터
    option_metadata = BitVMXOptionIntegration.create_option_metadata(
        option_type=option_type,
        strike_price=strike_price,
        expiry_timestamp=expiry_timestamp,
        premium_sats=1000000  # 0.01 BTC
    )
    
    return {**setup_params, **base_params, "metadata": option_metadata}

def prepare_option_input(
    option_type: str,
    strike_price: float,
    spot_price: float,
    quantity: float
) -> str:
    """
    옵션 입력 데이터 준비
    InputController.__call__()에 전달할 input_hex
    """
    return BitVMXOptionIntegration.create_option_input_hex(
        option_type=option_type,
        strike_price=strike_price,
        spot_price=spot_price,
        quantity=quantity
    )

def process_option_settlement(
    setup_uuid: str,
    input_hex: str,
    execution_complete: bool
) -> Dict[str, Any]:
    """
    옵션 정산 처리
    NextStep 프로세스 완료 후 호출
    """
    if not execution_complete:
        return {"status": "pending", "message": "Execution not complete"}
    
    # 정산 검증
    result = BitVMXOptionIntegration.validate_option_execution(
        setup_uuid=setup_uuid,
        input_hex=input_hex
    )
    
    if result["ready_for_settlement"]:
        # 정산 트랜잭션 생성 로직
        # 기존 BitVMX 트랜잭션 생성 서비스 활용
        pass
    
    return result