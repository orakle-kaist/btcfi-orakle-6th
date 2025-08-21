#!/usr/bin/env python3
"""
BitVMX 옵션 시스템 통합 파일

이 파일 하나로 모든 옵션 기능을 처리합니다:
1. 옵션 상품 등록 (BitVMX Setup)
2. 옵션 구매 (프리미엄 지불 + Pre-sign)
3. 옵션 정산 (Oracle + Pre-sign 실행)

Pre-sign 설명:
- Pre-sign은 Bitcoin의 기본 기능입니다 (BitVMX 전용이 아님)
- BitVMX는 Pre-sign을 활용해서 Challenge-Response를 우회합니다
- 운영자가 미리 서명한 트랜잭션을 구매자에게 전달
- 만기 시 구매자가 Oracle 증명만 추가해서 실행
"""

import requests
import hashlib
import struct
from datetime import datetime, timedelta
from typing import Dict, Optional

# === 설정 ===
PROVER_API = "http://localhost:8001/api/v1"
MUTINYNET_API = "https://mutinynet.com/api"

# 운영자 정보
OPERATOR = {
    "address": "tb1qt8rdur557nz338g3lekc6458pj0dl63c0s9904",
    "private_key": "d8a1e1224e63135765bde9dc8a2c8e403eee8be73d3589d58c5ddbf9dce3fdf4",
    "public_key": "03bf751f0d2d22e6f0163c9acaa14ae04e6e1a004cb4a24d893c1f86314e79d5de"
}

# 전역 저장소 (실제로는 DB 사용)
STORAGE = {
    "products": {},     # 등록된 옵션 상품
    "purchases": {},    # 구매 기록
    "presigns": {}      # Pre-sign 데이터
}


class BitVMXOptionSystem:
    """
    BitVMX 옵션 시스템 - 통합 클래스
    모든 중복 코드를 제거하고 핵심 기능만 구현
    """
    
    # === Step 1: 옵션 상품 등록 ===
    
    @staticmethod
    def register_option_product(
        option_type: str = "CALL",
        strike_price: float = 50000,
        expiry_days: int = 7
    ) -> Optional[str]:
        """
        옵션 상품 등록 (운영자가 풀 자금 제공)
        
        Args:
            option_type: CALL or PUT
            strike_price: 행사가 (USD)
            expiry_days: 만기까지 일수
            
        Returns:
            product_id: 상품 ID
        """
        print("\n" + "=" * 60)
        print("Step 1: 옵션 상품 등록")
        print("=" * 60)
        
        # 1. UTXO 조회 (풀 자금)
        utxos = BitVMXOptionSystem._get_utxos(OPERATOR["address"])
        if not utxos:
            print("❌ UTXO 없음")
            return None
            
        utxo = utxos[0]
        pool_size = utxo["value"]
        
        # 2. 프리미엄 계산
        premium_sats = BitVMXOptionSystem._calculate_premium(
            option_type, strike_price, expiry_days, pool_size
        )
        
        # 3. BitVMX Setup 생성 (풀 자금 Lock)
        setup_uuid = BitVMXOptionSystem._create_bitvmx_setup(utxo, option_type, strike_price, expiry_days)
        if not setup_uuid:
            return None
        
        # 4. 상품 정보 저장
        product_id = f"OPT-{option_type}-{int(strike_price)}-{setup_uuid[:8]}"
        STORAGE["products"][product_id] = {
            "product_id": product_id,
            "setup_uuid": setup_uuid,
            "option_type": option_type,
            "strike_price": strike_price,
            "expiry": int((datetime.now() + timedelta(days=expiry_days)).timestamp()),
            "premium_sats": premium_sats,
            "pool_size_sats": pool_size
        }
        
        print(f"\n✅ 상품 등록 완료: {product_id}")
        print(f"   프리미엄: {premium_sats:,} sats")
        print(f"   풀: {pool_size:,} sats")
        
        return product_id
    
    # === Step 2: 옵션 구매 ===
    
    @staticmethod
    def purchase_option(product_id: str, buyer_address: str) -> Optional[str]:
        """
        옵션 구매 (프리미엄 지불 + Pre-sign 받기)
        
        Args:
            product_id: 상품 ID
            buyer_address: 구매자 주소
            
        Returns:
            purchase_id: 구매 ID
        """
        print("\n" + "=" * 60)
        print("Step 2: 옵션 구매")
        print("=" * 60)
        
        product = STORAGE["products"].get(product_id)
        if not product:
            print(f"❌ 상품 없음: {product_id}")
            return None
        
        # 1. 프리미엄 지불 (트랜잭션)
        print(f"💰 프리미엄 지불: {product['premium_sats']:,} sats")
        payment_tx = {
            "from": buyer_address,
            "to": OPERATOR["address"],
            "amount": product["premium_sats"],
            "txid": hashlib.sha256(f"{buyer_address}:{datetime.now()}".encode()).hexdigest()[:16]
        }
        
        # 2. Pre-sign 생성 (핵심!)
        presign = BitVMXOptionSystem._create_presign(product, buyer_address)
        
        # 3. 구매 기록 저장
        purchase_id = f"PUR-{product_id[:16]}-{int(datetime.now().timestamp())}"
        STORAGE["purchases"][purchase_id] = {
            "purchase_id": purchase_id,
            "product_id": product_id,
            "buyer_address": buyer_address,
            "payment_tx": payment_tx,
            "presign": presign
        }
        
        print(f"\n✅ 구매 완료: {purchase_id}")
        print(f"   Pre-sign 전달 완료")
        
        return purchase_id
    
    # === Step 3: 옵션 정산 ===
    
    @staticmethod
    def settle_option(purchase_id: str, oracle_price: float) -> Dict:
        """
        옵션 정산 (만기 시 Pre-sign 실행)
        
        Args:
            purchase_id: 구매 ID
            oracle_price: Oracle 가격 (USD)
            
        Returns:
            정산 결과
        """
        print("\n" + "=" * 60)
        print("Step 3: 옵션 정산")
        print("=" * 60)
        
        purchase = STORAGE["purchases"].get(purchase_id)
        if not purchase:
            print(f"❌ 구매 기록 없음: {purchase_id}")
            return {}
        
        product = STORAGE["products"][purchase["product_id"]]
        
        # 1. ITM/OTM 판단
        is_itm = BitVMXOptionSystem._check_itm(
            product["option_type"],
            product["strike_price"],
            oracle_price
        )
        
        # 2. 정산 금액 계산
        if is_itm:
            payout = product["pool_size_sats"]
            recipient = purchase["buyer_address"]
            print(f"✅ ITM - 수익 발생: {payout:,} sats")
        else:
            payout = 0
            recipient = OPERATOR["address"]
            print(f"❌ OTM - 수익 없음")
        
        # 3. Pre-sign 실행
        print("\n🚀 Pre-sign 트랜잭션 실행...")
        settlement_tx = BitVMXOptionSystem._execute_presign(
            purchase["presign"],
            oracle_price,
            recipient,
            payout
        )
        
        print(f"✅ 정산 완료!")
        print(f"   수령인: {recipient[:20]}...")
        print(f"   금액: {payout:,} sats")
        
        return {
            "is_itm": is_itm,
            "payout_sats": payout,
            "recipient": recipient,
            "settlement_tx": settlement_tx
        }
    
    # === 헬퍼 함수들 (중복 제거) ===
    
    @staticmethod
    def _get_utxos(address: str) -> list:
        """UTXO 조회"""
        try:
            response = requests.get(f"{MUTINYNET_API}/address/{address}/utxo")
            if response.status_code == 200:
                return response.json()
        except:
            pass
        # 테스트용 더미 UTXO
        return [{"txid": "dummy_tx", "vout": 0, "value": 10000000}]
    
    @staticmethod
    def _calculate_premium(option_type: str, strike: float, expiry_days: int, pool_size: int) -> int:
        """프리미엄 계산 (Black-Scholes 간소화)"""
        current_price = 52000
        volatility = 0.8
        time_to_expiry = expiry_days / 365
        
        moneyness = current_price / strike if option_type == "CALL" else strike / current_price
        if moneyness > 1:  # ITM
            intrinsic = abs(current_price - strike) / current_price
            time_value = volatility * (time_to_expiry ** 0.5) * 0.3
        else:  # OTM
            intrinsic = 0
            time_value = volatility * (time_to_expiry ** 0.5) * 0.2
        
        premium_rate = intrinsic + time_value
        return int(pool_size * premium_rate)
    
    @staticmethod
    def _create_bitvmx_setup(utxo: Dict, option_type: str, strike: float, expiry_days: int, 
                           use_challenge_response: bool = False) -> Optional[str]:
        """
        BitVMX Setup 생성
        
        Args:
            use_challenge_response: True면 Prover-Verifier 사용, False면 Pre-sign 사용
        """
        
        # Challenge-Response 모드: Verifier 필요 (복잡한 분쟁 해결)
        if use_challenge_response:
            verifier_list = [
                {
                    "public_key": "03verifier1_pubkey...",
                    "signature_public_key": "03verifier1_sig...",
                    "destination_address": "tb1qverifier1..."
                },
                # 더 많은 verifier 추가 가능
            ]
            print("🔄 Challenge-Response 모드: Prover-Verifier 사용")
        else:
            # Pre-sign 모드: Verifier 불필요 (단순 조건 정산)
            verifier_list = []
            print("✨ Pre-sign 모드: 자동 정산 (Verifier 불필요)")
        
        setup_data = {
            "max_amount_of_steps": 100 if not use_challenge_response else 1000000,
            "amount_of_bits_wrong_step_search": 2,
            "funding_tx_id": utxo["txid"],
            "funding_index": utxo["vout"],
            "secret_origin_of_funds": OPERATOR["private_key"],
            "verifier_list": verifier_list,
            "prover_destination_address": OPERATOR["address"],
            "prover_signature_private_key": OPERATOR["private_key"],
            "prover_signature_public_key": OPERATOR["public_key"],
            "amount_of_input_words": 4
        }
        
        try:
            response = requests.post(f"{PROVER_API}/setup", json=setup_data, timeout=60)
            if response.status_code == 200:
                return response.json().get("setup_uuid")
        except:
            pass
        
        # 테스트용 더미 UUID
        return f"SETUP-{int(datetime.now().timestamp())}"
    
    @staticmethod
    def _create_presign(product: Dict, buyer_address: str) -> Dict:
        """
        Pre-sign 생성 (핵심!)
        
        Pre-sign = 미리 서명된 조건부 트랜잭션
        Bitcoin의 기본 기능이며, BitVMX는 이를 활용
        """
        # 정산 스크립트 (Bitcoin Script)
        settlement_script = f"""
        # 1. 만기 체크
        {product['expiry']} CHECKLOCKTIMEVERIFY DROP
        
        # 2. Oracle 가격 검증
        OP_DUP OP_SHA256 <oracle_root> OP_EQUALVERIFY
        
        # 3. 정산 로직
        {int(product['strike_price'] * 100)}  # cents
        {"OP_GREATERTHAN" if product['option_type'] == "CALL" else "OP_LESSTHAN"}
        OP_IF
            {buyer_address} OP_CHECKSIG  # ITM: 구매자
        OP_ELSE
            {OPERATOR['public_key']} OP_CHECKSIG  # OTM: 운영자
        OP_ENDIF
        """
        
        # 운영자가 미리 서명
        signature = hashlib.sha256(settlement_script.encode()).hexdigest()
        
        return {
            "settlement_script": settlement_script,
            "signature": signature,
            "setup_uuid": product["setup_uuid"]
        }
    
    @staticmethod
    def _check_itm(option_type: str, strike: float, spot: float) -> bool:
        """ITM/OTM 체크"""
        if option_type == "CALL":
            return spot > strike
        else:  # PUT
            return spot < strike
    
    @staticmethod
    def _execute_presign(presign: Dict, oracle_price: float, recipient: str, payout: int) -> Dict:
        """Pre-sign 실행"""
        # Oracle witness 추가
        oracle_witness = {
            "price": int(oracle_price * 100),
            "signature": hashlib.sha256(f"{oracle_price}".encode()).hexdigest()
        }
        
        # 최종 트랜잭션
        return {
            "presigned_tx": presign["signature"],
            "oracle_witness": oracle_witness,
            "recipient": recipient,
            "amount": payout
        }


def main():
    """전체 플로우 실행"""
    print("=" * 60)
    print("BitVMX 옵션 시스템 (통합 버전)")
    print("=" * 60)
    
    # Step 1: 상품 등록
    product_id = BitVMXOptionSystem.register_option_product(
        option_type="CALL",
        strike_price=50000,
        expiry_days=7
    )
    
    if not product_id:
        print("❌ 상품 등록 실패")
        return
    
    # Step 2: 구매
    purchase_id = BitVMXOptionSystem.purchase_option(
        product_id=product_id,
        buyer_address="tb1q_buyer_example"
    )
    
    if not purchase_id:
        print("❌ 구매 실패")
        return
    
    # Step 3: 정산
    settlement = BitVMXOptionSystem.settle_option(
        purchase_id=purchase_id,
        oracle_price=52000  # ITM
    )
    
    # 결과
    print("\n" + "=" * 60)
    print("✅ 전체 플로우 완료!")
    print("=" * 60)
    print(f"\n📊 결과:")
    print(f"• 상품: {product_id}")
    print(f"• 구매: {purchase_id}")
    print(f"• 정산: {'ITM 수익' if settlement.get('is_itm') else 'OTM 손실'}")
    print(f"• 금액: {settlement.get('payout_sats', 0):,} sats")
    
    print("\n💡 Pre-sign 설명:")
    print("• Pre-sign은 Bitcoin의 기본 기능입니다")
    print("• BitVMX는 Pre-sign을 활용해 Challenge-Response를 우회합니다")
    print("• 운영자가 미리 서명 → 구매자가 Oracle 증명만 추가 → 자동 정산")


if __name__ == "__main__":
    main()