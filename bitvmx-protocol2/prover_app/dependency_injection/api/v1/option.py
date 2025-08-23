"""
옵션 API Dependency Injection

BitVMX Native Pre-sign Service를 실제로 연결합니다.
기존 BitVMX 내부 기능을 활용합니다.
"""

from bitcoinutils.keys import PrivateKey
from bitvmx_protocol_library.transaction_generation.services.bitvmx_native_presign_service import (
    BitVMXNativePresignService
)
from prover_app.domain.controllers.v1.setup.create_setup_controller import CreateSetupController
from prover_app.domain.controllers.v1.input.input_controller import InputController


class OptionRegisterViewControllers:
    """옵션 등록 - 기존 BitVMX Setup 컨트롤러 활용"""
    
    @staticmethod
    def v1():
        # 기존 Setup 컨트롤러 활용
        setup_controller = CreateSetupController()
        return setup_controller


class OptionPurchaseViewControllers:
    """옵션 구매 - BitVMX Native Pre-sign Service 활용"""
    
    @staticmethod
    def v1():
        # 운영자 키 (실제로는 환경변수에서)
        # Hex 형식의 private key 사용
        operator_key = PrivateKey(secret_exponent=int("d8a1e1224e63135765bde9dc8a2c8e403eee8be73d3589d58c5ddbf9dce3fdf4", 16))
        
        # BitVMX Native Pre-sign Service 인스턴스
        presign_service = BitVMXNativePresignService(operator_key)
        
        return presign_service


class OptionSettlementControllers:
    """옵션 정산 - BitVMX 실행 및 Pre-sign 처리"""
    
    @staticmethod
    def v1():
        # 기존 Input 컨트롤러로 정산 실행
        input_controller = InputController()
        return input_controller