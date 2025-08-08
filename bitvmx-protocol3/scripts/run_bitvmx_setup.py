#!/usr/bin/env python3
"""
BitVMX Setup 실행 스크립트
완전한 Prover-Verifier 프로토콜 실행
"""

import sys
import os
import time
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from domain.option.bitvmx_setup import BitVMXSetupManager
from domain.option.create_real_tx import create_option_registration_tx

def run_full_bitvmx_setup():
    """
    완전한 BitVMX Setup 실행
    """
    print("\n" + "="*60)
    print("🚀 BitVMX 완전 통합 시스템 시작")
    print("="*60)
    
    # 1. BitVMX Setup Manager 초기화
    setup_manager = BitVMXSetupManager()
    
    # 2. 옵션 데이터 준비
    option_data = {
        'type': 'CALL',
        'strike': 122000,  # $122K
        'expiry': int(time.time()) + (3 * 24 * 60 * 60),  # 3일 후
        'unit': 0.01,  # 0.01 BTC
        'id': f'bitvmx_opt_{int(time.time())}'
    }
    
    print(f"\n📋 옵션 정보:")
    print(f"  타입: {option_data['type']}")
    print(f"  행사가: ${option_data['strike']:,}")
    print(f"  수량: {option_data['unit']} BTC")
    print(f"  ID: {option_data['id']}")
    
    # 3. BitVMX Setup 실행
    print("\n" + "-"*60)
    print("BitVMX Setup 프로세스 시작...")
    print("-"*60)
    
    setup_result = setup_manager.create_full_setup(option_data)
    
    print("\n" + "-"*60)
    print("BitVMX Setup 결과:")
    print("-"*60)
    print(f"  Setup UUID: {setup_result['setup_uuid']}")
    print(f"  Prover UUID: {setup_result['prover_uuid']}")
    print(f"  네트워크: {setup_result['network']}")
    print(f"  소요 시간: {setup_result['elapsed_time']:.2f}초")
    
    # 4. 실제 트랜잭션 생성 및 브로드캐스트
    print("\n" + "-"*60)
    print("실제 트랜잭션 생성 및 브로드캐스트...")
    print("-"*60)
    
    try:
        tx_hex, option_result = create_option_registration_tx()
        print("\n✅ 트랜잭션 생성 성공!")
        print(f"  옵션 ID: {option_result['id']}")
        print(f"  타입: {option_result['type']}")
        print(f"  행사가: ${option_result['strike']:,}")
        
        # 브로드캐스트는 create_real_tx.py의 main()에서 처리
        from domain.option.create_real_tx import broadcast_transaction
        success = broadcast_transaction(tx_hex)
        
        if success:
            print("\n🎉 전체 프로세스 완료!")
            print("  1. BitVMX Setup ✅")
            print("  2. 트랜잭션 생성 ✅")
            print("  3. 브로드캐스트 ✅")
        else:
            print("\n⚠️ 브로드캐스트 실패 (트랜잭션은 생성됨)")
            
    except Exception as e:
        print(f"\n❌ 트랜잭션 생성 오류: {e}")
    
    print("\n" + "="*60)
    print("BitVMX 통합 시스템 종료")
    print("="*60)

if __name__ == "__main__":
    print("\n" + "="*60)
    print("🎯 BitVMX 프로토콜 - 완전 통합 테스트")
    print("="*60)
    print("\n이 스크립트는:")
    print("1. Prover/Verifier 키 교환")
    print("2. Bitcoin 스크립트 생성")
    print("3. 트랜잭션 구성")
    print("4. 실제 MutinyNet 브로드캐스트")
    print("\n시작하려면 Enter (취소: Ctrl+C)")
    
    try:
        input()
        run_full_bitvmx_setup()
    except KeyboardInterrupt:
        print("\n\n❌ 취소됨")
    except Exception as e:
        print(f"\n\n❌ 오류: {e}")
        import traceback
        traceback.print_exc()