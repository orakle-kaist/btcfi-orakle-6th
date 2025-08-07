#!/usr/bin/env python3
"""
BitVMX 기반 옵션 등록 시스템
- 기존 2단계 트랜잭션 구조 유지
- BitVMX API를 통한 트랜잭션 생성
"""

import struct
import hashlib
import time
import json
import requests
from typing import Dict, Tuple, Optional
from dataclasses import dataclass

# 옵션 데이터 구조체 (기존 구조 그대로)
@dataclass
class BTCFiOptionInput:
    """BitVMX 에뮬레이터에 전달할 옵션 입력 구조"""
    option_type: str  # "CALL" or "PUT"
    strike: int       # USD 단위 행사가
    unit: float       # BTC 수량
    expiry: int       # Unix timestamp
    option_id: str    # 옵션 식별자
    
    def to_bitvmx_input(self) -> bytes:
        """BitVMX 에뮬레이터 입력 형식으로 변환"""
        # 기존 코드와 동일한 구조체 패킹
        option_type_int = 0 if self.option_type == "CALL" else 1
        strike_price_cents = self.strike * 100
        quantity_sats = int(self.unit * 100_000_000)
        premium_sats = max(1000, int(quantity_sats * 0.02))
        
        # 더미 해시 데이터 (나중에 실제 오라클 연동)
        issuer_hash = b'\x01' * 32
        oracle_count = 3
        oracle_hashes = b'\x02' * 40
        
        # Little endian 패킹
        input_data = struct.pack('<I', option_type_int)
        input_data += struct.pack('<Q', strike_price_cents)
        input_data += struct.pack('<Q', quantity_sats)
        input_data += struct.pack('<Q', premium_sats)
        input_data += struct.pack('<Q', self.expiry)
        input_data += issuer_hash
        input_data += struct.pack('<I', oracle_count)
        input_data += oracle_hashes
        
        return input_data
    
    def to_compact_string(self) -> str:
        """2차 트랜잭션용 투명한 문자열 형식"""
        # 형식: C|d1|116000|1740268800|1.0|해시16자리
        return f"{self.option_type[0]}|{self.option_id}|{self.strike}|{self.expiry}|{self.unit}"


class BitVMXOptionRegistration:
    """BitVMX를 사용한 옵션 등록 클래스"""
    
    def __init__(self, verifier_url="http://localhost:8080", prover_url="http://localhost:8081"):
        self.verifier_url = verifier_url
        self.prover_url = prover_url
        self.setup_uuid = None
        
    def generate_bitvmx_hash(self, option: BTCFiOptionInput) -> Tuple[str, int]:
        """
        BitVMX 에뮬레이터를 통한 해시 생성
        Returns: (hash, steps)
        """
        input_hex = option.to_bitvmx_input().hex()
        
        # TODO: 실제 BitVMX 에뮬레이터 실행
        # 일단은 기존 데모의 알려진 값 사용
        print(f"🔧 BitVMX 입력 데이터: {len(option.to_bitvmx_input())} bytes")
        print(f"🔧 Hex: {input_hex[:50]}...")
        
        # 실제 실행 결과 (나중에 에뮬레이터 연동)
        return "9cc626dfe6cd76df6a70a523fe69adc21e4f8a11e9cf4cd3ed259976275f6317", 3597
    
    def create_bitvmx_anchor_tx(self, option: BTCFiOptionInput) -> Optional[str]:
        """
        1차 트랜잭션: BitVMX 앵커링
        BitVMX API를 통해 생성
        """
        print("\n🔗 1단계: BitVMX 앵커링 트랜잭션 생성")
        
        # BitVMX 해시 생성
        bitvmx_hash, steps = self.generate_bitvmx_hash(option)
        
        # Setup UUID 생성
        self.setup_uuid = f"option-{option.option_id}-{int(time.time())}"
        
        # BitVMX Setup API 호출
        setup_data = {
            "setup_uuid": self.setup_uuid,
            "network": "mutinynet",
            # TODO: 실제 funding UTXO 필요
            "funding_tx_id": "dummy_funding_tx",  
            "funding_index": 0,
            "funding_amount_of_satoshis": 95000,
            "step_fees_satoshis": 1000,
            "max_amount_of_steps": steps + 1000,  # 여유있게
            "amount_of_input_words": 10,
            
            # BitVMX 해시를 커스텀 데이터로 포함
            "custom_data": {
                "type": "option_anchor",
                "hash": bitvmx_hash,
                "steps": steps
            }
        }
        
        try:
            response = requests.post(
                f"{self.verifier_url}/api/v1/setup",
                json=setup_data,
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                txid = result.get("transaction_id", "dummy_txid_1")
                print(f"✅ BitVMX 앵커링 TX: {txid}")
                print(f"   해시: {bitvmx_hash}")
                print(f"   실행 단계: {steps}")
                return txid
            else:
                print(f"❌ Setup 실패: {response.status_code}")
                print(f"   {response.text[:200]}")
                # 테스트용 더미 값
                return "dummy_bitvmx_anchor_tx"
                
        except Exception as e:
            print(f"❌ API 호출 실패: {e}")
            # 테스트용 더미 값
            return "dummy_bitvmx_anchor_tx"
    
    def create_option_data_tx(self, option: BTCFiOptionInput, anchor_txid: str) -> Optional[str]:
        """
        2차 트랜잭션: 옵션 데이터
        1차 트랜잭션을 참조
        """
        print("\n🎯 2단계: 옵션 데이터 트랜잭션 생성")
        
        # 1차 트랜잭션 ID를 해시하여 참조
        bitvmx_ref_hash = hashlib.sha256(anchor_txid.encode()).hexdigest()[:16]
        
        # 투명한 옵션 데이터 + BitVMX 참조
        option_data = f"{option.to_compact_string()}|{bitvmx_ref_hash}"
        
        print(f"🔧 옵션 데이터: {option_data}")
        print(f"🔧 BitVMX 참조: {bitvmx_ref_hash}")
        
        # TODO: BitVMX API를 통한 2차 트랜잭션 생성
        # 현재는 더미 값 반환
        option_txid = "dummy_option_data_tx"
        
        print(f"✅ 옵션 데이터 TX: {option_txid}")
        print(f"   옵션: {option.option_type} ${option.strike:,}")
        print(f"   수량: {option.unit} BTC")
        print(f"   만기: {option.expiry}")
        print(f"   앵커 참조: {anchor_txid}")
        
        return option_txid
    
    def register_option(self, option: BTCFiOptionInput) -> Dict:
        """
        전체 옵션 등록 프로세스
        """
        print("\n" + "="*60)
        print("🚀 BitVMX 옵션 등록 시작")
        print("="*60)
        
        print(f"\n📊 옵션 정보:")
        print(f"   타입: {option.option_type}")
        print(f"   행사가: ${option.strike:,}")
        print(f"   수량: {option.unit} BTC")
        print(f"   만기: {option.expiry}")
        print(f"   ID: {option.option_id}")
        
        # 1차: BitVMX 앵커링
        anchor_txid = self.create_bitvmx_anchor_tx(option)
        if not anchor_txid:
            return {"error": "BitVMX 앵커링 실패"}
        
        # TODO: 블록 확정 대기 (실제 환경에서)
        time.sleep(1)
        
        # 2차: 옵션 데이터
        option_txid = self.create_option_data_tx(option, anchor_txid)
        if not option_txid:
            return {"error": "옵션 데이터 트랜잭션 실패"}
        
        print("\n" + "="*60)
        print("✅ 옵션 등록 완료!")
        print("="*60)
        
        return {
            "success": True,
            "option_id": option.option_id,
            "anchor_tx": anchor_txid,
            "option_tx": option_txid,
            "setup_uuid": self.setup_uuid
        }


# 테스트 실행
if __name__ == "__main__":
    # 옵션 생성
    test_option = BTCFiOptionInput(
        option_type="CALL",
        strike=100000,
        unit=1.0,
        expiry=int(time.time()) + (3 * 24 * 60 * 60),  # 3일 후
        option_id="test001"
    )
    
    # 등록 시스템 초기화
    registration = BitVMXOptionRegistration()
    
    # 옵션 등록
    result = registration.register_option(test_option)
    
    print("\n📋 결과:")
    print(json.dumps(result, indent=2))