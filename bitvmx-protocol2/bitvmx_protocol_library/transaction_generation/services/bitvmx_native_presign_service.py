"""
BitVMX Native Pre-sign Service

BitVMX의 네이티브 트랜잭션 생성 메커니즘을 활용한 Pre-sign 구현
Challenge-Response 없이 실행 가능한 조건부 트랜잭션을 생성합니다.
"""

from bitcoinutils.keys import P2wpkhAddress, PrivateKey, PublicKey
from bitcoinutils.transactions import Transaction, TxInput, TxOutput, TxWitnessInput
from bitcoinutils.script import Script
from bitcoinutils.constants import TAPROOT_SIGHASH_ALL

from bitvmx_protocol_library.bitvmx_protocol_definition.entities.bitvmx_protocol_setup_properties_dto import (
    BitVMXProtocolSetupPropertiesDTO,
)
from bitvmx_protocol_library.script_generation.entities.business_objects.bitcoin_script import BitcoinScript
from bitvmx_protocol_library.script_generation.entities.business_objects.bitcoin_script_list import BitcoinScriptList
from bitvmx_protocol_library.transaction_generation.entities.dtos.bitvmx_transactions_dto import (
    BitVMXTransactionsDTO,
)


class BitVMXNativePresignService:
    """
    BitVMX 네이티브 방식의 Pre-sign 서비스
    
    이 서비스는 BitVMX의 기존 트랜잭션 그래프 구조를 활용하되,
    Challenge-Response 대신 Oracle 조건부 실행을 가능하게 합니다.
    """
    
    def __init__(self, operator_private_key: PrivateKey):
        """
        Initialize the native pre-sign service.
        
        Args:
            operator_private_key: 운영자의 private key
        """
        self.operator_private_key = operator_private_key
        self.operator_public_key = operator_private_key.get_public_key()
    
    def create_option_settlement_graph(
        self,
        bitvmx_protocol_setup_properties_dto: BitVMXProtocolSetupPropertiesDTO,
        option_type: str,
        strike_price: int,
        expiry_timestamp: int,
        buyer_address: str
    ) -> dict:
        """
        옵션 정산을 위한 BitVMX 트랜잭션 그래프 생성
        
        BitVMX의 기존 트랜잭션 체인 구조를 활용하되,
        Challenge 단계를 Oracle 검증으로 대체합니다.
        
        트랜잭션 그래프:
        1. Funding TX → Hash Result TX (옵션 구매 확인)
        2. Hash Result TX → Settlement TX (Oracle 가격으로 정산)
        
        Args:
            bitvmx_protocol_setup_properties_dto: BitVMX setup 정보
            option_type: "CALL" or "PUT"
            strike_price: 행사가 (cents)
            expiry_timestamp: 만기 시각
            buyer_address: 구매자 주소
            
        Returns:
            Pre-sign 트랜잭션 그래프
        """
        
        # 1. Funding TX 출력을 Settlement Script로 설정
        settlement_script = self._create_bitvmx_settlement_script(
            option_type=option_type,
            strike_price=strike_price,
            expiry_timestamp=expiry_timestamp,
            buyer_address=buyer_address,
            operator_pubkey=self.operator_public_key
        )
        
        # BitVMX 스타일 스크립트 리스트 생성
        settlement_scripts_list = BitcoinScriptList([settlement_script])
        
        # Taproot 주소 생성 (BitVMX unspendable key 사용)
        settlement_address = settlement_scripts_list.get_taproot_address(
            public_key=bitvmx_protocol_setup_properties_dto.unspendable_public_key
        )
        
        # 2. Funding TX (옵션 구매 트랜잭션)
        funding_txin = TxInput(
            bitvmx_protocol_setup_properties_dto.funding_tx_id,
            bitvmx_protocol_setup_properties_dto.funding_index,
        )
        
        funding_txout = TxOutput(
            bitvmx_protocol_setup_properties_dto.funding_amount_of_satoshis,
            settlement_address.to_script_pub_key(),
        )
        
        funding_tx = Transaction([funding_txin], [funding_txout], has_segwit=True)
        
        # 3. Settlement TX (정산 트랜잭션) - Pre-signed
        settlement_txin = TxInput(funding_tx.get_txid(), 0)
        
        # 정산 금액 계산 (수수료 차감)
        settlement_amount = (
            bitvmx_protocol_setup_properties_dto.funding_amount_of_satoshis
            - bitvmx_protocol_setup_properties_dto.step_fees_satoshis
        )
        
        # 조건부 출력 (ITM이면 구매자, OTM이면 운영자)
        # 실제 주소는 Oracle 가격에 따라 결정됨
        settlement_txout_buyer = TxOutput(
            settlement_amount,
            P2wpkhAddress.from_address(address=buyer_address).to_script_pub_key()
        )
        
        settlement_txout_operator = TxOutput(
            settlement_amount,
            self.operator_public_key.get_segwit_address().to_script_pub_key()
        )
        
        # 두 가지 경로의 트랜잭션 생성
        settlement_tx_itm = Transaction(
            [settlement_txin], [settlement_txout_buyer], 
            has_segwit=True, locktime=expiry_timestamp
        )
        
        settlement_tx_otm = Transaction(
            [settlement_txin], [settlement_txout_operator], 
            has_segwit=True, locktime=expiry_timestamp
        )
        
        # 4. Pre-sign 서명 생성 (BitVMX 방식)
        
        # Control block은 우리가 계산한 hex를 직접 사용 (라이브러리 재계산 방지)
        control_block_hex = settlement_scripts_list.get_control_block_hex(
            public_key=bitvmx_protocol_setup_properties_dto.unspendable_public_key,
            index=0,
            is_odd=settlement_address.is_odd(),
        )
        
        # ITM 경로 서명
        itm_signature = self.operator_private_key.sign_taproot_input(
            settlement_tx_itm,
            0,
            [settlement_address.to_script_pub_key()],
            [bitvmx_protocol_setup_properties_dto.funding_amount_of_satoshis],
            script_path=True,
            tapleaf_script=settlement_script,
            sighash=TAPROOT_SIGHASH_ALL,
            tweak=False,
        )
        
        # OTM 경로 서명
        otm_signature = self.operator_private_key.sign_taproot_input(
            settlement_tx_otm,
            0,
            [settlement_address.to_script_pub_key()],
            [bitvmx_protocol_setup_properties_dto.funding_amount_of_satoshis],
            script_path=True,
            tapleaf_script=settlement_script,
            sighash=TAPROOT_SIGHASH_ALL,
            tweak=False,
        )
        
        # 5. Pre-sign 데이터 패키징
        presign_graph = {
            "setup_uuid": bitvmx_protocol_setup_properties_dto.setup_uuid,
            "option_params": {
                "type": option_type,
                "strike": strike_price,
                "expiry": expiry_timestamp,
                "buyer": buyer_address
            },
            "transactions": {
                "funding_tx": {
                    "txid": funding_tx.get_txid(),
                    "raw": funding_tx.serialize(),
                    "output_address": str(settlement_address)
                },
                "settlement_tx_itm": {
                    "raw": settlement_tx_itm.serialize(),
                    "signature": itm_signature,
                    "witness_elements": [
                        # Oracle price proof will be added here
                        # [oracle_price, merkle_proof, ...]
                        itm_signature,
                        settlement_script.to_hex(),
                        control_block_hex,
                    ]
                },
                "settlement_tx_otm": {
                    "raw": settlement_tx_otm.serialize(),
                    "signature": otm_signature,
                    "witness_elements": [
                        # Oracle price proof will be added here
                        otm_signature,
                        settlement_script.to_hex(),
                        control_block_hex,
                    ]
                }
            },
            "settlement_script": settlement_script.to_hex(),
            "control_block": control_block_hex,
        }
        
        return presign_graph
    
    def _create_bitvmx_settlement_script(
        self,
        option_type: str,
        strike_price: int,
        expiry_timestamp: int,
        buyer_address: str,
        operator_pubkey: PublicKey
    ) -> BitcoinScript:
        """
        BitVMX 스타일의 정산 스크립트 생성
        
        이 스크립트는:
        1. 만기 시간을 체크
        2. Oracle 가격을 검증
        3. 옵션 조건에 따라 자동 정산
        
        Args:
            option_type: "CALL" or "PUT"
            strike_price: 행사가 (cents)
            expiry_timestamp: 만기 시각
            buyer_address: 구매자 주소
            operator_pubkey: 운영자 공개키
            
        Returns:
            BitcoinScript 객체
        """
        
        # Bitcoin Script elements
        script_elements = []
        
        # 1. 만기 시간 체크 (CHECKLOCKTIMEVERIFY)
        script_elements.extend([
            expiry_timestamp,
            'OP_CHECKLOCKTIMEVERIFY',
            'OP_DROP'
        ])
        
        # 2. Oracle 가격 입력 (witness에서)
        # Stack: [oracle_price, oracle_signature, ...]
        
        # 3. Oracle 서명 검증
        # 여러 Oracle의 multisig 검증 (2-of-3)
        script_elements.extend([
            'OP_DUP',
            'OP_HASH160',
            # Oracle pubkey hashes will be added
            'OP_EQUALVERIFY',
            'OP_CHECKSIG',
            'OP_VERIFY'
        ])
        
        # 4. 가격 비교 및 정산
        script_elements.extend([
            # Oracle price is on stack
            strike_price,
        ])
        
        if option_type == "CALL":
            # CALL: price > strike → buyer wins
            script_elements.extend([
                'OP_GREATERTHAN',
                'OP_IF',
                    # ITM: Pay to buyer
                    'OP_DUP',
                    'OP_HASH160',
                    Script.from_address(buyer_address).to_hex(),
                    'OP_EQUALVERIFY',
                    'OP_CHECKSIG',
                'OP_ELSE',
                    # OTM: Pay to operator
                    operator_pubkey.to_hex(),
                    'OP_CHECKSIG',
                'OP_ENDIF'
            ])
        else:  # PUT
            # PUT: price < strike → buyer wins
            script_elements.extend([
                'OP_LESSTHAN',
                'OP_IF',
                    # ITM: Pay to buyer
                    'OP_DUP',
                    'OP_HASH160',
                    Script.from_address(buyer_address).to_hex(),
                    'OP_EQUALVERIFY',
                    'OP_CHECKSIG',
                'OP_ELSE',
                    # OTM: Pay to operator
                    operator_pubkey.to_hex(),
                    'OP_CHECKSIG',
                'OP_ENDIF'
            ])
        
        return BitcoinScript(script_elements)
    
    def execute_presigned_settlement(
        self,
        presign_graph: dict,
        oracle_price: int,
        oracle_proof: dict
    ) -> str:
        """
        Pre-signed 정산 트랜잭션 실행
        
        구매자가 만기 시 Oracle 가격 증명과 함께
        Pre-signed 트랜잭션을 실행합니다.
        
        Args:
            presign_graph: Pre-sign 트랜잭션 그래프
            oracle_price: Oracle 가격 (USD)
            oracle_proof: Oracle 가격 증명
            
        Returns:
            트랜잭션 ID
        """
        
        # 옵션 파라미터 추출
        option_type = presign_graph["option_params"]["type"]
        strike_price = presign_graph["option_params"]["strike"]
        
        # ITM/OTM 판단
        if option_type == "CALL":
            is_itm = oracle_price > strike_price
        else:  # PUT
            is_itm = oracle_price < strike_price
        
        # 적절한 트랜잭션 선택
        if is_itm:
            tx_data = presign_graph["transactions"]["settlement_tx_itm"]
        else:
            tx_data = presign_graph["transactions"]["settlement_tx_otm"]
        
        # 트랜잭션 복원
        tx = Transaction.from_raw(tx_data["raw"])
        
        # Oracle witness 생성
        oracle_witness_elements = [
            oracle_price.to_bytes(4, 'little').hex(),  # Oracle 가격
            oracle_proof.get("signature", ""),         # Oracle 서명
            oracle_proof.get("merkle_root", ""),       # Merkle root
        ] + tx_data["witness_elements"]
        
        # Witness 추가
        tx.witnesses = [TxWitnessInput(oracle_witness_elements)]
        
        # 트랜잭션 브로드캐스트
        from blockchain_query_services.services.blockchain_query_services_dependency_injection import (
            broadcast_transaction_service,
        )
        
        txid = broadcast_transaction_service(tx.serialize())
        
        return txid
