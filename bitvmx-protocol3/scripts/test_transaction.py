#!/usr/bin/env python3
"""
트랜잭션 테스트 스크립트
팀원들이 쉽게 테스트할 수 있도록 준비된 스크립트
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from domain.option.create_real_tx import main

if __name__ == "__main__":
    print("\n" + "="*60)
    print("🧪 BitVMX 옵션 등록 트랜잭션 테스트")
    print("="*60)
    print("\n⚠️  주의사항:")
    print("1. .env 파일에 PRIVATE_KEY와 ADDRESS를 설정하세요")
    print("2. MutinyNet에 충분한 잔액이 있는지 확인하세요")
    print("3. 사용할 UTXO를 create_real_tx.py에서 수정하세요")
    print("\n시작하려면 Enter를 누르세요 (취소: Ctrl+C)")
    
    try:
        input()
        main()
    except KeyboardInterrupt:
        print("\n\n❌ 테스트 취소됨")
    except Exception as e:
        print(f"\n\n❌ 오류 발생: {e}")
        print("\n💡 문제 해결:")
        print("1. UTXO가 올바른지 확인")
        print("2. 프라이빗 키가 주소와 일치하는지 확인")
        print("3. 네트워크 연결 확인")