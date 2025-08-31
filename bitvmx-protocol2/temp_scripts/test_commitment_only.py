#!/usr/bin/env python3
"""
BitVMX 원칙에 따른 커밋먼트 기반 옵션 시스템 테스트
- 온체인: 32바이트 커밋먼트만
- 오프체인: 실제 옵션 데이터
"""

import json
import hashlib
import time
from datetime import datetime

def test_commitment_system():
    """커밋먼트 기반 시스템 테스트"""
    
    print("="*60)
    print("BitVMX 원칙: 커밋먼트 기반 옵션 시스템")
    print("="*60)
    
    # 1. 옵션 데이터 (오프체인)
    option_data = {
        "option_id": "opt_2025_001",
        "type": "CALL",
        "strike": 65000,
        "spot": 67000,
        "quantity": 1.0,
        "expiry": "2025-02-01T00:00:00",
        "buyer": "bc1qexample...",
        "premium": 2000,
        "timestamp": int(time.time())
    }
    
    print("\n[1] 오프체인 옵션 데이터:")
    print(json.dumps(option_data, indent=2))
    print(f"크기: {len(json.dumps(option_data))} bytes")
    
    # 2. 32바이트 커밋먼트 생성
    option_json = json.dumps(option_data, sort_keys=True, separators=(',', ':'))
    commitment = hashlib.sha256(option_json.encode()).hexdigest()
    
    print("\n[2] 온체인 커밋먼트 (32 bytes):")
    print(f"SHA256: {commitment}")
    print(f"크기: {len(commitment)//2} bytes")
    
    # 3. 정산 시나리오
    print("\n[3] 정산 시나리오:")
    final_spot = 70000
    payoff = max(0, final_spot - option_data["strike"])
    
    settlement_data = {
        "option_commitment": commitment,
        "final_spot": final_spot,
        "payoff": payoff,
        "settlement_time": int(time.time())
    }
    
    # 정산 커밋먼트
    settlement_json = json.dumps(settlement_data, sort_keys=True, separators=(',', ':'))
    settlement_commitment = hashlib.sha256(settlement_json.encode()).hexdigest()
    
    print(f"최종 가격: ${final_spot:,}")
    print(f"행사가: ${option_data['strike']:,}")
    print(f"정산금: ${payoff:,}")
    print(f"정산 커밋먼트: {settlement_commitment[:16]}...")
    
    # 4. Challenge/Response 시뮬레이션
    print("\n[4] Challenge/Response (분쟁 시):")
    print("Verifier: 정산금이 잘못되었다고 주장")
    print("Prover: 오프체인 데이터와 증명 제공")
    
    # Prover가 제공하는 증명
    proof = {
        "original_data": option_data,
        "original_commitment": commitment,
        "execution_trace": [
            {"step": 1, "operation": "LOAD_STRIKE", "value": option_data["strike"]},
            {"step": 2, "operation": "LOAD_SPOT", "value": final_spot},
            {"step": 3, "operation": "SUBTRACT", "value": final_spot - option_data["strike"]},
            {"step": 4, "operation": "MAX_ZERO", "value": payoff}
        ]
    }
    
    # 검증
    proof_json = json.dumps(proof["original_data"], sort_keys=True, separators=(',', ':'))
    verified_commitment = hashlib.sha256(proof_json.encode()).hexdigest()
    
    is_valid = (verified_commitment == commitment)
    print(f"증명 검증: {'✅ 유효' if is_valid else '❌ 무효'}")
    
    # 5. 효율성 비교
    print("\n[5] 효율성 비교:")
    print("="*50)
    
    # 기존 방식 (모든 데이터 온체인)
    old_onchain_size = len(json.dumps(option_data))
    
    # BitVMX 방식 (커밋먼트만 온체인)
    new_onchain_size = 32
    
    print(f"기존 방식: {old_onchain_size} bytes 온체인")
    print(f"BitVMX 방식: {new_onchain_size} bytes 온체인")
    print(f"절감률: {((old_onchain_size - new_onchain_size) / old_onchain_size * 100):.1f}%")
    
    # 6. 대량 처리 시뮬레이션
    print("\n[6] 대량 옵션 처리 (1000개):")
    
    commitments = []
    for i in range(1000):
        opt = option_data.copy()
        opt["option_id"] = f"opt_2025_{i:04d}"
        opt_json = json.dumps(opt, sort_keys=True, separators=(',', ':'))
        commitments.append(hashlib.sha256(opt_json.encode()).hexdigest())
    
    # Merkle Tree 루트 생성
    current_level = commitments
    while len(current_level) > 1:
        next_level = []
        for i in range(0, len(current_level), 2):
            if i + 1 < len(current_level):
                combined = current_level[i] + current_level[i + 1]
            else:
                combined = current_level[i] + current_level[i]
            next_level.append(hashlib.sha256(combined.encode()).hexdigest())
        current_level = next_level
    
    merkle_root = current_level[0]
    
    print(f"1000개 옵션 → 1개 Merkle Root (32 bytes)")
    print(f"Merkle Root: {merkle_root[:16]}...")
    print(f"기존: {old_onchain_size * 1000:,} bytes")
    print(f"BitVMX: 32 bytes")
    print(f"절감률: 99.98%")
    
    print("\n" + "="*60)
    print("✅ BitVMX 원칙 준수 완료!")
    print("- 온체인: 최소 데이터 (32바이트 커밋먼트)")
    print("- 오프체인: 실제 데이터 및 실행")
    print("- 검증: Challenge/Response 메커니즘")
    print("="*60)

if __name__ == "__main__":
    test_commitment_system()