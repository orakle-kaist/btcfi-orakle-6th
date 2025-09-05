"""
Generate Option Pre-sign Service

BitVMX의 정석 구조를 따라 옵션 정산을 위한 Pre-sign 트랜잭션을 생성합니다.
기존 GenerateSignaturesService와 동일한 패턴을 사용하되,
옵션 정산 조건을 추가합니다.
"""

from bitcoinutils.constants import TAPROOT_SIGHASH_ALL
from bitcoinutils.transactions import Transaction, TxWitnessInput
from bitcoinutils.utils import ControlBlock

from bitvmx_protocol_library.bitvmx_protocol_definition.entities.bitvmx_protocol_setup_properties_dto import (
    BitVMXProtocolSetupPropertiesDTO,
)
from bitvmx_protocol_library.script_generation.entities.business_objects.bitcoin_script import BitcoinScript
from bitvmx_protocol_library.script_generation.entities.business_objects.bitcoin_script_list import BitcoinScriptList


class GenerateOptionPresignService:
    """
    BitVMX 정석 구조를 사용한 옵션 Pre-sign 생성 서비스
    
    이 서비스는 옵션 구매 시점에 만기 정산을 위한 조건부 트랜잭션을
    미리 생성하고 서명합니다.
    """
    
    def __init__(self, operator_private_key, unspendable_public_key):
        """
        Initialize the pre-sign generation service.
        
        Args:
            operator_private_key: 운영자의 private key (서명용)
            unspendable_public_key: BitVMX unspendable public key
        """
        self.operator_private_key = operator_private_key
        self.unspendable_public_key = unspendable_public_key
    
    def create_option_settlement_script(
        self,
        option_type: str,
        strike_price: int,
        expiry_timestamp: int,
        buyer_address: str
    ) -> BitcoinScript:
        """
        옵션 정산 스크립트 생성 (BitVMX 스타일)
        
        Args:
            option_type: "CALL" or "PUT"
            strike_price: 행사가 (cents)
            expiry_timestamp: 만기 시각 (Unix timestamp)
            buyer_address: 구매자 주소
            
        Returns:
            BitcoinScript 객체
        """
        # BitVMX 스타일로 스크립트 생성
        script_elements = [
            # 1. 만기 시간 체크
            "OP_DUP",
            expiry_timestamp,
            "OP_CHECKLOCKTIMEVERIFY",
            "OP_DROP",
            
            # 2. Oracle 가격 입력 (witness에서)
            # Stack: [oracle_price]
            
            # 3. 가격 검증을 위한 commitment 체크
            # BitVMX의 hash commitment 패턴 사용
            "OP_DUP",
            "OP_SHA256",
            # Oracle price commitment will be added here
            "OP_EQUALVERIFY",
            
            # 4. 옵션 정산 로직
            strike_price,
        ]
        
        if option_type == "CALL":
            # CALL: price > strike이면 구매자에게
            script_elements.extend([
                "OP_GREATERTHAN",
                "OP_IF",
                    # 구매자에게 지급
                    buyer_address,
                    "OP_CHECKSIG",
                "OP_ELSE",
                    # 운영자 회수
                    self.operator_private_key.get_public_key().to_hex(),
                    "OP_CHECKSIG",
                "OP_ENDIF"
            ])
        else:  # PUT
            # PUT: price < strike이면 구매자에게
            script_elements.extend([
                "OP_LESSTHAN",
                "OP_IF",
                    # 구매자에게 지급
                    buyer_address,
                    "OP_CHECKSIG",
                "OP_ELSE",
                    # 운영자 회수
                    self.operator_private_key.get_public_key().to_hex(),
                    "OP_CHECKSIG",
                "OP_ENDIF"
            ])
        
        return BitcoinScript(script_elements)
    
    def generate_presign_for_option(
        self,
        bitvmx_protocol_setup_properties_dto: BitVMXProtocolSetupPropertiesDTO,
        option_type: str,
        strike_price: int,
        expiry_timestamp: int,
        buyer_address: str,
        premium_sats: int
    ) -> dict:
        """
        옵션 Pre-sign 생성 (BitVMX 정석 방식)
        
        Args:
            bitvmx_protocol_setup_properties_dto: BitVMX setup 정보
            option_type: "CALL" or "PUT"
            strike_price: 행사가 (USD)
            expiry_timestamp: 만기 시각
            buyer_address: 구매자 주소
            premium_sats: 프리미엄 (satoshis)
            
        Returns:
            Pre-sign 데이터 딕셔너리
        """
        # 1. 정산 스크립트 생성
        settlement_script = self.create_option_settlement_script(
            option_type=option_type,
            strike_price=strike_price * 100,  # USD to cents
            expiry_timestamp=expiry_timestamp,
            buyer_address=buyer_address
        )
        
        # 2. BitVMX 스타일 스크립트 리스트 생성
        settlement_scripts_list = BitcoinScriptList([settlement_script])
        
        # 3. Taproot 주소 생성
        settlement_address = settlement_scripts_list.get_taproot_address(
            public_key=self.unspendable_public_key
        )
        
        # 4. 정산 트랜잭션 생성
        # Input: 옵션 풀의 UTXO
        # Output: 정산 조건에 따라 구매자 또는 운영자에게
        settlement_tx = Transaction(
            inputs=[],  # Will be filled with pool UTXO
            outputs=[],  # Will be filled based on settlement
            locktime=expiry_timestamp,
            version=2
        )
        
        # 5. 풀 자금에서 지출할 금액 계산
        funding_amount = bitvmx_protocol_setup_properties_dto.funding_amount_of_satoshis
        settlement_amount = funding_amount - bitvmx_protocol_setup_properties_dto.step_fees_satoshis
        
        # 6. Pre-sign 서명 생성 (BitVMX 방식)
        presign_signature = self.operator_private_key.sign_taproot_input(
            settlement_tx,
            0,
            [settlement_address.to_script_pub_key()],
            [settlement_amount],
            script_path=True,
            tapleaf_script=settlement_script,
            sighash=TAPROOT_SIGHASH_ALL,
            tweak=False,
        )
        
        # 7. Control block 생성
        # Use precomputed control block from our script list to avoid library recomputation
        control_block_hex = settlement_scripts_list.get_control_block_hex(
            public_key=self.unspendable_public_key,
            index=0,
            is_odd=settlement_address.is_odd(),
        )
        
        # 8. Witness 구성
        settlement_witness = TxWitnessInput([
            presign_signature,
            settlement_script.to_hex(),
            control_block_hex,
        ])
        
        # 9. Pre-sign 데이터 패키징
        presign_data = {
            "setup_uuid": bitvmx_protocol_setup_properties_dto.setup_uuid,
            "option_type": option_type,
            "strike_price": strike_price,
            "expiry_timestamp": expiry_timestamp,
            "buyer_address": buyer_address,
            "premium_sats": premium_sats,
            "settlement_script_hex": settlement_script.to_hex(),
            "settlement_address": str(settlement_address),
            "presign_signature": presign_signature,
            "control_block_hex": control_block_hex,
            "settlement_witness": settlement_witness.to_list(),
            "funding_amount": funding_amount,
            "settlement_amount": settlement_amount,
        }
        
        return presign_data
    
    def create_settlement_transaction_with_oracle(
        self,
        presign_data: dict,
        oracle_price: int,
        oracle_proof: dict,
        pool_utxo: dict
    ) -> Transaction:
        """
        Oracle 가격을 사용하여 정산 트랜잭션 완성
        
        Args:
            presign_data: Pre-sign 데이터
            oracle_price: Oracle 가격 (USD)
            oracle_proof: Oracle 가격 증명
            pool_utxo: 풀의 UTXO 정보
            
        Returns:
            완성된 정산 트랜잭션
        """
        from bitcoinutils.transactions import TxInput, TxOutput
        from bitcoinutils.script import Script
        
        # 1. 정산 여부 확인
        option_type = presign_data["option_type"]
        strike_price = presign_data["strike_price"]
        
        if option_type == "CALL":
            is_itm = oracle_price > strike_price
        else:  # PUT
            is_itm = oracle_price < strike_price
        
        # 2. 트랜잭션 입력 생성
        tx_input = TxInput(
            txid=pool_utxo["txid"],
            vout=pool_utxo["vout"],
            script_sig=Script(),  # Witness transaction이므로 비움
            sequence=0xFFFFFFFE  # Enable CHECKLOCKTIMEVERIFY
        )
        
        # 3. 트랜잭션 출력 생성
        if is_itm:
            # ITM: 구매자에게 지급
            recipient_address = presign_data["buyer_address"]
        else:
            # OTM: 운영자 회수
            recipient_address = self.operator_private_key.get_public_key().get_address()
        
        tx_output = TxOutput(
            value=presign_data["settlement_amount"],
            script_pubkey=Script.from_address(recipient_address)
        )
        
        # 4. 트랜잭션 생성
        settlement_tx = Transaction(
            inputs=[tx_input],
            outputs=[tx_output],
            locktime=presign_data["expiry_timestamp"],
            version=2
        )
        
        # 5. Oracle witness 추가
        oracle_witness_elements = [
            oracle_price.to_bytes(4, 'little').hex(),  # Oracle 가격
            oracle_proof["merkle_root"],  # Merkle root
            oracle_proof["merkle_path"],  # Merkle path
        ] + presign_data["settlement_witness"]
        
        settlement_tx.witnesses.append(
            TxWitnessInput(oracle_witness_elements)
        )
        
        return settlement_tx
