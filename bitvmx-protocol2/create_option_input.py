#!/usr/bin/env python3
"""
BTCFi Option Registration Input Generator for BitVMX
실제 상용 서비스를 위한 옵션 등록 입력 데이터 생성
"""

import struct
import hashlib
import time
from typing import List

class BTCFiOptionInput:
    """BitVMX 호환 옵션 입력 구조체"""
    
    def __init__(self):
        self.option_type = 0        # 0=Call, 1=Put
        self.strike_price = 0       # USD cents
        self.quantity = 0           # satoshis
        self.premium = 0            # satoshis
        self.expiry_timestamp = 0   # Unix timestamp
        self.current_btc_price = 0  # Oracle BTC price in cents
        self.issuer_hash = b'\x00' * 32  # SHA256 hash of issuer
        self.oracle_count = 0       # Number of oracle sources
        self.oracle_hashes = []     # Up to 5 oracle hashes (8 bytes each)

def create_realistic_call_option() -> BTCFiOptionInput:
    """현실적인 Call 옵션 생성"""
    option = BTCFiOptionInput()
    
    # Call 옵션 설정
    option.option_type = 0  # Call
    option.strike_price = 5300000  # $53,000 (USD cents)
    option.quantity = 10000000     # 0.1 BTC (satoshis)
    option.premium = 200000        # 0.002 BTC premium (satoshis)
    option.expiry_timestamp = int(time.time()) + (7 * 24 * 3600)  # 7일 후
    option.current_btc_price = 5200000  # $52,000 현재 BTC 가격
    
    # 발행자 해시 생성 (실제 발행자 주소)
    issuer_address = "bc1qxy2kgdygjrsqtzq2n0yrf2493p83kkfjhx0wlh"
    option.issuer_hash = hashlib.sha256(issuer_address.encode()).digest()
    
    # Oracle 소스 (3개)
    option.oracle_count = 3
    oracle_sources = ["binance_btcusdt", "coinbase_btcusd", "kraken_xbtusd"]
    
    for oracle in oracle_sources:
        oracle_hash = hashlib.sha256(oracle.encode()).digest()[:8]  # 8 bytes
        option.oracle_hashes.append(oracle_hash)
    
    # 빈 oracle 슬롯 채우기 (최대 5개)
    while len(option.oracle_hashes) < 5:
        option.oracle_hashes.append(b'\x00' * 8)
    
    return option

def encode_option_input(option: BTCFiOptionInput) -> bytes:
    """BitVMX가 이해할 수 있는 바이너리 형태로 인코딩"""
    
    # 구조체 패킹 (little endian)
    data = bytearray()
    
    # uint32_t option_type
    data.extend(struct.pack('<I', option.option_type))
    
    # uint64_t strike_price
    data.extend(struct.pack('<Q', option.strike_price))
    
    # uint64_t quantity
    data.extend(struct.pack('<Q', option.quantity))
    
    # uint64_t premium
    data.extend(struct.pack('<Q', option.premium))
    
    # uint64_t expiry_timestamp
    data.extend(struct.pack('<Q', option.expiry_timestamp))
    
    # uint64_t current_btc_price (추가됨)
    data.extend(struct.pack('<Q', option.current_btc_price))
    
    # uint8_t issuer_hash[32]
    data.extend(option.issuer_hash)
    
    # uint32_t oracle_count
    data.extend(struct.pack('<I', option.oracle_count))
    
    # uint8_t oracle_hashes[5][8]
    for oracle_hash in option.oracle_hashes:
        data.extend(oracle_hash)
    
    return bytes(data)

def create_input_file():
    """실제 옵션 등록 입력 파일 생성"""
    
    print("=== BTCFi 실제 옵션 상품 등록 입력 생성 ===")
    
    # Call 옵션 생성
    call_option = create_realistic_call_option()
    
    print(f"옵션 타입: {'Call' if call_option.option_type == 0 else 'Put'}")
    print(f"행사가: ${call_option.strike_price / 100:,.2f}")
    print(f"수량: {call_option.quantity / 100_000_000:.8f} BTC")
    print(f"프리미엄: {call_option.premium / 100_000_000:.8f} BTC")
    print(f"만료일: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(call_option.expiry_timestamp))}")
    print(f"현재 BTC 가격: ${call_option.current_btc_price / 100:,.2f}")
    print(f"Oracle 수: {call_option.oracle_count}")
    print(f"발행자 해시: {call_option.issuer_hash.hex()}")
    
    # 바이너리 인코딩
    encoded_data = encode_option_input(call_option)
    
    print(f"\n인코딩된 데이터 크기: {len(encoded_data)} bytes")
    print(f"데이터 미리보기: {encoded_data[:32].hex()}...")
    
    # 파일 저장
    input_file = "/Users/seongsu/project/blockchain/orakle/btcfi-orakle-6th/bitvmx-protocol2/option_input.bin"
    with open(input_file, 'wb') as f:
        f.write(encoded_data)
    
    print(f"\n✅ 입력 파일 생성 완료: {input_file}")
    
    # 검증용 정보 출력
    print("\n=== 검증용 정보 ===")
    print(f"입력 데이터 SHA256: {hashlib.sha256(encoded_data).hexdigest()}")
    
    return input_file, call_option

if __name__ == "__main__":
    create_input_file()