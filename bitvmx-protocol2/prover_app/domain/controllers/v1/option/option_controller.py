"""
BitVMX 옵션 컨트롤러
옵션 등록, 실행, 정산을 관리하는 컨트롤러
"""

from typing import Dict, Any, Optional
from dataclasses import dataclass
from enum import Enum
import struct
import hashlib
import json
import uuid
from datetime import datetime

try:
    from bitcoinutils.setup import setup
    from bitcoinutils.keys import PrivateKey
    from bitcoinutils.transactions import Transaction, TxInput, TxOutput
    from bitcoinutils.script import Script
except ImportError:
    # bitcoinutils not installed, will use basic implementation
    pass

try:
    from bitvmx_protocol_library.bitvmx_execution.services.execution_trace_generation_service import (
        ExecutionTraceGenerationService
    )
except ImportError:
    ExecutionTraceGenerationService = None


class OptionType(Enum):
    """옵션 타입"""
    CALL = 0
    PUT = 1


@dataclass
class OptionParameters:
    """옵션 파라미터"""
    option_type: OptionType
    strike_price: int  # USD * 100 (cents)
    spot_price: int    # USD * 100 (cents)
    quantity: int      # unit * 100
    expiry_timestamp: int
    premium: int       # satoshis


class OptionController:
    """
    BitVMX 옵션 컨트롤러
    옵션 등록, 실행, 정산 로직을 처리
    """
    
    def __init__(self):
        """컨트롤러 초기화"""
        if ExecutionTraceGenerationService:
            try:
                self.execution_trace_service = ExecutionTraceGenerationService("prover_files/")
            except:
                self.execution_trace_service = None
        else:
            self.execution_trace_service = None
        
        try:
            setup("testnet")  # MutinyNet은 testnet 기반
        except:
            pass  # bitcoinutils not available
        
    def create_option_input_hex(
        self,
        option_type: OptionType,
        strike_price: float,
        spot_price: float,
        quantity: float
    ) -> str:
        """
        옵션 파라미터를 BitVMX 입력 hex로 변환
        
        Args:
            option_type: CALL 또는 PUT
            strike_price: 행사가 (USD)
            spot_price: 현물가 (USD)
            quantity: 수량
            
        Returns:
            16진수 문자열 (32바이트)
        """
        # USD를 cents로 변환 (정수 연산)
        strike_cents = int(strike_price * 100)
        spot_cents = int(spot_price * 100)
        quantity_units = int(quantity * 100)
        
        # 32비트 정수 4개로 패킹
        data = struct.pack(
            '<IIII',  # Little-endian 4개 unsigned int
            option_type.value,
            strike_cents,
            spot_cents,
            quantity_units
        )
        
        return data.hex()
    
    def calculate_option_payoff(
        self,
        option_params: OptionParameters
    ) -> int:
        """
        옵션 만기 시 수익 계산
        
        Args:
            option_params: 옵션 파라미터
            
        Returns:
            수익 (satoshis)
        """
        strike = option_params.strike_price / 100  # cents to USD
        spot = option_params.spot_price / 100
        qty = option_params.quantity / 100
        
        if option_params.option_type == OptionType.CALL:
            # Call option: max(S - K, 0) * quantity
            payoff_usd = max(spot - strike, 0) * qty
        else:
            # Put option: max(K - S, 0) * quantity
            payoff_usd = max(strike - spot, 0) * qty
        
        # USD to BTC conversion (예시: 1 BTC = $50,000)
        btc_price = 50000
        payoff_btc = payoff_usd / btc_price
        payoff_sats = int(payoff_btc * 100_000_000)
        
        return payoff_sats
    
    def create_option_registration_tx(
        self,
        option_params: OptionParameters,
        funding_txid: str,
        funding_vout: int,
        prover_address: str,
        verifier_address: str
    ) -> Dict[str, Any]:
        """
        옵션 등록 트랜잭션 생성
        
        Args:
            option_params: 옵션 파라미터
            funding_txid: 자금 트랜잭션 ID
            funding_vout: 자금 출력 인덱스
            prover_address: Prover 주소
            verifier_address: Verifier 주소
            
        Returns:
            트랜잭션 정보 딕셔너리
        """
        # 옵션 데이터 JSON
        option_data = {
            "type": "BTCFI_OPTION",
            "version": 1,
            "option_type": option_params.option_type.name,
            "strike": option_params.strike_price,
            "expiry": option_params.expiry_timestamp,
            "quantity": option_params.quantity,
            "premium": option_params.premium
        }
        
        # 데이터를 OP_RETURN에 포함
        op_return_data = json.dumps(option_data).encode()[:80]  # 최대 80바이트
        
        # 트랜잭션 구성
        tx_info = {
            "inputs": [{
                "txid": funding_txid,
                "vout": funding_vout
            }],
            "outputs": [
                {
                    "address": prover_address,
                    "value": option_params.premium,
                    "type": "premium_payment"
                },
                {
                    "script": f"OP_RETURN {op_return_data.hex()}",
                    "value": 0,
                    "type": "option_data"
                }
            ],
            "option_data": option_data
        }
        
        return tx_info
    
    def verify_option_execution(
        self,
        option_params: OptionParameters,
        execution_trace: bytes,
        witness_data: Dict[str, Any]
    ) -> bool:
        """
        옵션 실행 검증
        
        Args:
            option_params: 옵션 파라미터
            execution_trace: 실행 트레이스
            witness_data: 증명 데이터
            
        Returns:
            검증 성공 여부
        """
        # 실행 트레이스 해시 계산
        trace_hash = hashlib.sha256(execution_trace).digest()
        
        # 예상 결과 계산
        expected_payoff = self.calculate_option_payoff(option_params)
        
        # 증명 데이터 검증
        if witness_data.get("trace_hash") != trace_hash.hex():
            return False
        
        if witness_data.get("payoff") != expected_payoff:
            return False
        
        # 만기 시간 검증
        if datetime.now().timestamp() < option_params.expiry_timestamp:
            return False
        
        return True
    
    def generate_settlement_script(
        self,
        option_params: OptionParameters,
        prover_pubkey: str,
        verifier_pubkey: str
    ) -> str:
        """
        옵션 정산 스크립트 생성
        
        Args:
            option_params: 옵션 파라미터
            prover_pubkey: Prover 공개키
            verifier_pubkey: Verifier 공개키
            
        Returns:
            Bitcoin Script
        """
        # 정산 조건 스크립트
        # IF: 만기 후 올바른 가격 증명 제출 시 -> Prover가 수익 획득
        # ELSE: 챌린지 또는 타임아웃 -> Verifier가 자금 회수
        
        script = f"""
        OP_IF
            # 만기 체크
            {option_params.expiry_timestamp} OP_CHECKLOCKTIMEVERIFY OP_DROP
            
            # 가격 증명 검증
            OP_DUP OP_HASH256
            # 예상 해시와 비교
            
            # Prover 서명 검증
            {prover_pubkey} OP_CHECKSIG
        OP_ELSE
            # Verifier 서명 검증 (챌린지/타임아웃)
            {verifier_pubkey} OP_CHECKSIG
        OP_ENDIF
        """
        
        return script.strip()
    
    async def register_option_product(
        self,
        option_type: str,
        strike_price: float,
        expiry_timestamp: int,
        max_quantity: float,
        premium_rate: float
    ) -> Dict[str, Any]:
        """
        옵션 상품 등록 (운영자)
        
        Args:
            option_type: "CALL" 또는 "PUT"
            strike_price: 행사가 (USD)
            expiry_timestamp: 만기 시간 (Unix timestamp)
            max_quantity: 최대 판매 수량
            premium_rate: 프리미엄 비율 (0.01 = 1%)
            
        Returns:
            상품 등록 결과
        """
        # 상품 ID 생성
        product_id = str(uuid.uuid4())
        
        # Black-Scholes로 프리미엄 계산 (실제로는 calculation 모듈 사용)
        current_price = 52000  # Oracle에서 가져올 예정
        base_premium = int(current_price * premium_rate * 100_000_000 / current_price)  # in sats
        
        # 상품 정보 저장 (실제로는 DB에)
        product_info = {
            "product_id": product_id,
            "option_type": option_type,
            "strike_price": strike_price,
            "expiry_timestamp": expiry_timestamp,
            "max_quantity": max_quantity,
            "available_quantity": max_quantity,
            "base_premium_sats": base_premium,
            "current_spot": current_price,
            "status": "active",
            "created_at": datetime.now().isoformat()
        }
        
        return product_info
    
    async def purchase_option(
        self,
        product_id: str,
        quantity: float,
        buyer_address: str,
        payment_txid: str,
        setup_uuid: str
    ) -> Dict[str, Any]:
        """
        옵션 구매 (사용자)
        
        Args:
            product_id: 상품 ID
            quantity: 구매 수량
            buyer_address: 구매자 주소
            payment_txid: 프리미엄 지불 트랜잭션
            setup_uuid: BitVMX setup UUID
            
        Returns:
            구매 결과 및 pre-sign 정보
        """
        # 상품 정보 조회 (실제로는 DB에서)
        # 여기서는 예시 데이터 사용
        product_info = {
            "option_type": "CALL",
            "strike_price": 50000,
            "expiry_timestamp": 1735689600,
            "base_premium_sats": 1000000
        }
        
        # 프리미엄 계산
        total_premium = int(product_info["base_premium_sats"] * quantity)
        
        # 현재 가격
        current_price = 52000
        
        # BitVMX pre-sign 생성을 위한 입력 데이터
        input_hex = self.create_option_input_hex(
            OptionType[product_info["option_type"]],
            product_info["strike_price"],
            current_price,
            quantity
        )
        
        # 구매 정보
        purchase_info = {
            "purchase_id": str(uuid.uuid4()),
            "product_id": product_id,
            "buyer_address": buyer_address,
            "quantity": quantity,
            "premium_paid": total_premium,
            "payment_txid": payment_txid,
            "setup_uuid": setup_uuid,
            "input_hex": input_hex,
            "strike_price": product_info["strike_price"],
            "current_spot": current_price,
            "expiry": product_info["expiry_timestamp"],
            "status": "purchased",
            "purchased_at": datetime.now().isoformat()
        }
        
        return purchase_info
    
    async def execute_settlement(
        self,
        setup_uuid: str,
        price_proof: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        옵션 정산 실행
        
        Args:
            setup_uuid: BitVMX setup UUID
            price_proof: 가격 증명 데이터
            
        Returns:
            정산 결과
        """
        # 정산 로직 구현
        # 1. 가격 증명 검증
        # 2. 수익 계산
        # 3. 트랜잭션 생성
        # 4. 브로드캐스트
        
        return {
            "setup_uuid": setup_uuid,
            "settlement_tx": "txid_placeholder",
            "payoff_sats": 0,
            "status": "settled"
        }