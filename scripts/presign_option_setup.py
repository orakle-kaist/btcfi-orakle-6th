#!/usr/bin/env python3
"""Pre-sign 기반 단방향 옵션 설정"""

import hashlib
import json
from typing import Dict, List, Tuple
import time

class PresignOptionProtocol:
    """
    BitVMX를 활용한 단방향 옵션 프로토콜
    - Pre-sign: 사전 서명된 트랜잭션으로 조건부 실행
    - 챌린지-응답: 잘못된 실행에 대한 검증
    """
    
    def __init__(self):
        self.option_params = {}
        self.presigned_txs = []
        self.challenge_proofs = []
    
    def create_option_contract(self, 
                              strike_price: int,
                              expiry_time: int,
                              premium: int,
                              underlying_asset: str) -> Dict:
        """
        단방향 옵션 컨트랙트 생성
        
        Args:
            strike_price: 행사가격 (sats)
            expiry_time: 만기 시간 (Unix timestamp)
            premium: 프리미엄 (sats)
            underlying_asset: 기초자산 (BTC, ETH 등)
        
        Returns:
            옵션 컨트랙트 파라미터
        """
        
        # 옵션 ID 생성
        option_id = hashlib.sha256(
            f"{strike_price}{expiry_time}{premium}{underlying_asset}{time.time()}".encode()
        ).hexdigest()[:16]
        
        contract = {
            "option_id": option_id,
            "type": "CALL",  # 단방향 콜옵션
            "strike_price": strike_price,
            "expiry_time": expiry_time,
            "premium": premium,
            "underlying_asset": underlying_asset,
            "created_at": int(time.time()),
            "state": "CREATED",
            
            # BitVMX 파라미터
            "bitvmx_params": {
                "max_steps": 1000,
                "challenge_period": 3600,  # 1시간
                "verification_bond": premium * 2,  # 프리미엄의 2배
            },
            
            # Pre-sign 트랜잭션 템플릿
            "presign_templates": {
                "exercise_tx": None,  # 행사 트랜잭션
                "expiry_tx": None,    # 만기 트랜잭션
                "challenge_tx": None,  # 챌린지 트랜잭션
                "response_tx": None    # 응답 트랜잭션
            }
        }
        
        self.option_params[option_id] = contract
        return contract
    
    def generate_presigned_transactions(self, option_id: str, 
                                       buyer_pubkey: str,
                                       seller_pubkey: str) -> List[Dict]:
        """
        Pre-sign 트랜잭션 생성
        
        Args:
            option_id: 옵션 ID
            buyer_pubkey: 구매자 공개키
            seller_pubkey: 판매자 공개키
        
        Returns:
            사전 서명된 트랜잭션 리스트
        """
        
        if option_id not in self.option_params:
            raise ValueError(f"Option {option_id} not found")
        
        contract = self.option_params[option_id]
        presigned_txs = []
        
        # 1. 행사 트랜잭션 (Exercise Transaction)
        exercise_tx = {
            "type": "EXERCISE",
            "option_id": option_id,
            "inputs": [
                {
                    "type": "option_funding",
                    "amount": contract["strike_price"] + contract["premium"]
                }
            ],
            "outputs": [
                {
                    "to": buyer_pubkey,
                    "amount": contract["strike_price"],
                    "condition": f"price >= {contract['strike_price']} AND time < {contract['expiry_time']}"
                }
            ],
            "locktime": contract["expiry_time"],
            "presigned": False
        }
        presigned_txs.append(exercise_tx)
        
        # 2. 만기 트랜잭션 (Expiry Transaction)
        expiry_tx = {
            "type": "EXPIRY",
            "option_id": option_id,
            "inputs": [
                {
                    "type": "option_funding",
                    "amount": contract["premium"]
                }
            ],
            "outputs": [
                {
                    "to": seller_pubkey,
                    "amount": contract["premium"],
                    "condition": f"time >= {contract['expiry_time']}"
                }
            ],
            "locktime": contract["expiry_time"],
            "presigned": False
        }
        presigned_txs.append(expiry_tx)
        
        # 3. 챌린지 트랜잭션 (Challenge Transaction)
        challenge_tx = {
            "type": "CHALLENGE",
            "option_id": option_id,
            "inputs": [
                {
                    "type": "verification_bond",
                    "amount": contract["bitvmx_params"]["verification_bond"]
                }
            ],
            "outputs": [
                {
                    "to": "bitvmx_escrow",
                    "amount": contract["bitvmx_params"]["verification_bond"],
                    "condition": "valid_challenge_proof"
                }
            ],
            "challenge_data": {
                "challenger": buyer_pubkey,
                "challenged": seller_pubkey,
                "claim": "incorrect_price_oracle"
            },
            "presigned": False
        }
        presigned_txs.append(challenge_tx)
        
        # 4. 응답 트랜잭션 (Response Transaction)
        response_tx = {
            "type": "RESPONSE",
            "option_id": option_id,
            "inputs": [
                {
                    "type": "challenge_escrow",
                    "amount": contract["bitvmx_params"]["verification_bond"]
                }
            ],
            "outputs": [
                {
                    "to": seller_pubkey,
                    "amount": contract["bitvmx_params"]["verification_bond"],
                    "condition": "valid_response_proof"
                }
            ],
            "response_data": {
                "responder": seller_pubkey,
                "proof": "price_oracle_proof"
            },
            "presigned": False
        }
        presigned_txs.append(response_tx)
        
        self.presigned_txs.extend(presigned_txs)
        return presigned_txs
    
    def create_challenge_proof(self, option_id: str, 
                              claim_type: str,
                              evidence: Dict) -> Dict:
        """
        챌린지 증명 생성
        
        Args:
            option_id: 옵션 ID
            claim_type: 클레임 유형 (incorrect_price, early_exercise 등)
            evidence: 증거 데이터
        
        Returns:
            챌린지 증명
        """
        
        proof = {
            "option_id": option_id,
            "claim_type": claim_type,
            "evidence": evidence,
            "timestamp": int(time.time()),
            "proof_hash": hashlib.sha256(
                json.dumps(evidence, sort_keys=True).encode()
            ).hexdigest(),
            
            # BitVMX 검증 파라미터
            "bitvmx_verification": {
                "computation_trace": [],  # 계산 추적
                "merkle_proofs": [],      # 머클 증명
                "witness_data": []         # 증인 데이터
            }
        }
        
        self.challenge_proofs.append(proof)
        return proof
    
    def verify_option_execution(self, option_id: str, 
                               execution_data: Dict) -> Tuple[bool, str]:
        """
        옵션 실행 검증
        
        Args:
            option_id: 옵션 ID
            execution_data: 실행 데이터
        
        Returns:
            (검증 결과, 메시지)
        """
        
        if option_id not in self.option_params:
            return False, "Option not found"
        
        contract = self.option_params[option_id]
        
        # 1. 시간 검증
        current_time = int(time.time())
        if current_time >= contract["expiry_time"]:
            return False, "Option expired"
        
        # 2. 가격 검증 (오라클 데이터 필요)
        claimed_price = execution_data.get("oracle_price", 0)
        if claimed_price < contract["strike_price"]:
            return False, f"Price {claimed_price} below strike {contract['strike_price']}"
        
        # 3. 서명 검증
        if not execution_data.get("buyer_signature"):
            return False, "Missing buyer signature"
        
        # 4. BitVMX 검증
        # 실제 구현에서는 BitVMX 프로토콜로 검증
        
        return True, "Valid execution"
    
    def get_option_state(self, option_id: str) -> Dict:
        """옵션 상태 조회"""
        if option_id not in self.option_params:
            return {"error": "Option not found"}
        
        contract = self.option_params[option_id]
        current_time = int(time.time())
        
        # 상태 업데이트
        if current_time >= contract["expiry_time"]:
            contract["state"] = "EXPIRED"
        elif contract["state"] == "CREATED":
            contract["state"] = "ACTIVE"
        
        return {
            "option_id": option_id,
            "state": contract["state"],
            "strike_price": contract["strike_price"],
            "expiry_time": contract["expiry_time"],
            "time_to_expiry": max(0, contract["expiry_time"] - current_time),
            "premium": contract["premium"],
            "underlying_asset": contract["underlying_asset"],
            "presigned_txs": len([tx for tx in self.presigned_txs if tx["option_id"] == option_id]),
            "challenges": len([p for p in self.challenge_proofs if p["option_id"] == option_id])
        }


# 사용 예시
if __name__ == "__main__":
    protocol = PresignOptionProtocol()
    
    # 1. 옵션 생성
    option = protocol.create_option_contract(
        strike_price=50000,  # 50,000 sats
        expiry_time=int(time.time()) + 86400,  # 24시간 후
        premium=1000,  # 1,000 sats
        underlying_asset="BTC/USD"
    )
    
    print("✅ 옵션 생성:")
    print(json.dumps(option, indent=2))
    
    # 2. Pre-sign 트랜잭션 생성
    presigned = protocol.generate_presigned_transactions(
        option["option_id"],
        "02buyer_pubkey_example",
        "02seller_pubkey_example"
    )
    
    print("\n✅ Pre-signed 트랜잭션:")
    for tx in presigned:
        print(f"  - {tx['type']}: {len(json.dumps(tx))} bytes")
    
    # 3. 옵션 상태 확인
    state = protocol.get_option_state(option["option_id"])
    print("\n✅ 옵션 상태:")
    print(json.dumps(state, indent=2))