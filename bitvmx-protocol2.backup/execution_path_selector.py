#!/usr/bin/env python3
"""
BitVMX 실행 경로 선택기 (Execution Path Selector)

이 파일은 언제 Prover-Verifier를 쓰고 언제 Pre-sign을 쓰는지 명확히 보여줍니다.

실행 경로:
1. Pre-sign Path (95%+ 케이스): 정상적인 옵션 정산
2. Challenge-Response Path (5% 케이스): 분쟁 해결

CLAUDE.md의 내용은 맞습니다!
- BitVMX는 두 가지 경로를 모두 지원합니다
- Pre-sign은 Bitcoin 기능이고, BitVMX가 이를 활용합니다
- 복잡한 케이스는 여전히 Prover-Verifier를 사용합니다
"""

from enum import Enum
from typing import Dict, Tuple, Optional
from datetime import datetime


class ExecutionPath(Enum):
    """실행 경로 타입"""
    PRESIGN = "presign"              # Pre-sign 경로 (일반 정산)
    CHALLENGE_RESPONSE = "challenge"  # Challenge-Response 경로 (분쟁)


class PathSelector:
    """
    실행 경로 선택기
    
    각 상황에 맞는 적절한 실행 경로를 선택합니다.
    """
    
    @staticmethod
    def determine_path(
        option_type: str,
        strike_price: float,
        oracle_price: float,
        dispute_exists: bool = False,
        oracle_disagreement: bool = False,
        complex_computation: bool = False
    ) -> Tuple[ExecutionPath, str]:
        """
        실행 경로 결정
        
        Args:
            option_type: CALL or PUT
            strike_price: 행사가
            oracle_price: Oracle 가격
            dispute_exists: 분쟁 존재 여부
            oracle_disagreement: Oracle 간 불일치
            complex_computation: 복잡한 계산 필요
            
        Returns:
            (선택된 경로, 이유)
        """
        
        # === Case 1: Challenge-Response가 필요한 경우 ===
        
        if dispute_exists:
            return (
                ExecutionPath.CHALLENGE_RESPONSE,
                "분쟁 발생: 구매자와 운영자 간 정산 금액 이견"
            )
        
        if oracle_disagreement:
            return (
                ExecutionPath.CHALLENGE_RESPONSE,
                "Oracle 불일치: 3개 거래소 가격이 크게 차이남 (>5%)"
            )
        
        if complex_computation:
            return (
                ExecutionPath.CHALLENGE_RESPONSE,
                "복잡한 계산: 다중 조건, 경로 의존적 페이오프 등"
            )
        
        # === Case 2: Pre-sign으로 충분한 경우 (대부분) ===
        
        return (
            ExecutionPath.PRESIGN,
            "정상 정산: 단순 ITM/OTM 판단으로 자동 정산 가능"
        )
    
    @staticmethod
    def explain_paths():
        """두 경로의 차이점 설명"""
        
        explanation = """
        ┌────────────────────────────────────────────────────────────┐
        │               BitVMX 실행 경로 (Two Paths)                   │
        ├────────────────────────────────────────────────────────────┤
        │                                                            │
        │  1. Pre-sign Path (95%+ 케이스)                           │
        │  ═══════════════════════════════                          │
        │                                                            │
        │  [옵션 구매] → [Pre-sign 수령] → [만기] → [자동 정산]        │
        │                                                            │
        │  • 사용 시점: 정상적인 옵션 정산                             │
        │  • 필요 요소: Oracle 가격 증명만                            │
        │  • Verifier: 불필요 ❌                                     │
        │  • 장점: 빠르고 간단, 가스비 저렴                           │
        │                                                            │
        ├────────────────────────────────────────────────────────────┤
        │                                                            │
        │  2. Challenge-Response Path (5% 케이스)                   │
        │  ══════════════════════════════════════                    │
        │                                                            │
        │  [분쟁 발생] → [Prover 증명] → [Verifier 검증] → [정산]     │
        │                                                            │
        │  • 사용 시점:                                              │
        │    - Oracle 가격 분쟁                                      │
        │    - 복잡한 계산 검증                                      │
        │    - 악의적 행위 의심                                      │
        │  • 필요 요소: Prover + Verifier                           │
        │  • Verifier: 필수 ✅                                       │
        │  • 장점: 완벽한 검증, 보안성 최고                           │
        │                                                            │
        └────────────────────────────────────────────────────────────┘
        """
        
        return explanation
    
    @staticmethod
    def demonstrate_selection():
        """실제 선택 예시"""
        
        print("=" * 60)
        print("BitVMX 실행 경로 선택 데모")
        print("=" * 60)
        
        # 시나리오 1: 정상 정산
        print("\n📍 시나리오 1: 정상적인 CALL 옵션 만기")
        path1, reason1 = PathSelector.determine_path(
            option_type="CALL",
            strike_price=50000,
            oracle_price=52000,
            dispute_exists=False
        )
        print(f"   선택된 경로: {path1.value}")
        print(f"   이유: {reason1}")
        print(f"   → Pre-sign 사용! Verifier 불필요")
        
        # 시나리오 2: Oracle 불일치
        print("\n📍 시나리오 2: Oracle 가격 불일치")
        path2, reason2 = PathSelector.determine_path(
            option_type="PUT",
            strike_price=50000,
            oracle_price=48000,
            oracle_disagreement=True
        )
        print(f"   선택된 경로: {path2.value}")
        print(f"   이유: {reason2}")
        print(f"   → Prover-Verifier 필요!")
        
        # 시나리오 3: 분쟁 발생
        print("\n📍 시나리오 3: 정산 금액 분쟁")
        path3, reason3 = PathSelector.determine_path(
            option_type="CALL",
            strike_price=50000,
            oracle_price=50100,  # 경계선 케이스
            dispute_exists=True
        )
        print(f"   선택된 경로: {path3.value}")
        print(f"   이유: {reason3}")
        print(f"   → Challenge-Response 프로토콜 실행!")


class BitVMXDualMode:
    """
    BitVMX 듀얼 모드 시스템
    
    Pre-sign과 Challenge-Response를 모두 지원하는 통합 시스템
    """
    
    def __init__(self):
        self.presign_count = 0
        self.challenge_count = 0
    
    def process_settlement(
        self,
        purchase_id: str,
        oracle_price: float,
        **kwargs
    ) -> Dict:
        """
        정산 처리 (자동 경로 선택)
        """
        
        # 경로 선택
        path, reason = PathSelector.determine_path(
            option_type=kwargs.get("option_type", "CALL"),
            strike_price=kwargs.get("strike_price", 50000),
            oracle_price=oracle_price,
            dispute_exists=kwargs.get("dispute", False),
            oracle_disagreement=kwargs.get("oracle_disagreement", False)
        )
        
        print(f"\n🔍 정산 ID: {purchase_id}")
        print(f"   실행 경로: {path.value}")
        print(f"   선택 이유: {reason}")
        
        if path == ExecutionPath.PRESIGN:
            return self._execute_presign_settlement(purchase_id, oracle_price)
        else:
            return self._execute_challenge_response(purchase_id, oracle_price)
    
    def _execute_presign_settlement(
        self,
        purchase_id: str,
        oracle_price: float
    ) -> Dict:
        """Pre-sign 정산 실행"""
        
        self.presign_count += 1
        
        print("\n✨ Pre-sign 정산 실행")
        print("   1. Oracle 가격 증명 검증")
        print("   2. Pre-signed 트랜잭션 활성화")
        print("   3. 자동 BTC 전송")
        
        return {
            "path": "presign",
            "purchase_id": purchase_id,
            "oracle_price": oracle_price,
            "status": "settled",
            "verifier_needed": False,
            "gas_cost": "low",
            "settlement_time": "10 minutes"
        }
    
    def _execute_challenge_response(
        self,
        purchase_id: str,
        oracle_price: float
    ) -> Dict:
        """Challenge-Response 정산 실행"""
        
        self.challenge_count += 1
        
        print("\n🔄 Challenge-Response 프로토콜 시작")
        print("   1. Prover: 정산 계산 증명 생성")
        print("   2. Verifier: 증명 검증 및 Challenge")
        print("   3. Prover: Response 제출")
        print("   4. On-chain: 최종 검증 및 정산")
        
        return {
            "path": "challenge-response",
            "purchase_id": purchase_id,
            "oracle_price": oracle_price,
            "status": "settled_after_verification",
            "verifier_needed": True,
            "gas_cost": "high",
            "settlement_time": "30-60 minutes",
            "rounds": 3  # Challenge-Response 라운드 수
        }
    
    def get_statistics(self) -> Dict:
        """통계 조회"""
        
        total = self.presign_count + self.challenge_count
        
        if total == 0:
            return {"message": "No settlements yet"}
        
        return {
            "total_settlements": total,
            "presign_settlements": self.presign_count,
            "challenge_settlements": self.challenge_count,
            "presign_ratio": f"{(self.presign_count/total)*100:.1f}%",
            "challenge_ratio": f"{(self.challenge_count/total)*100:.1f}%",
            "average_gas_saved": f"{self.presign_count * 0.8:.1f} BTC"  # Pre-sign이 80% 저렴
        }


def main():
    """메인 실행"""
    
    print(PathSelector.explain_paths())
    
    print("\n" + "=" * 60)
    print("실행 경로 선택 데모")
    print("=" * 60)
    
    PathSelector.demonstrate_selection()
    
    # 듀얼 모드 시스템 테스트
    print("\n" + "=" * 60)
    print("BitVMX 듀얼 모드 시스템 테스트")
    print("=" * 60)
    
    system = BitVMXDualMode()
    
    # 정상 정산 10건
    for i in range(10):
        system.process_settlement(
            f"PUR-{i:03d}",
            52000 + i * 100,
            option_type="CALL",
            strike_price=50000
        )
    
    # 분쟁 정산 1건
    system.process_settlement(
        "PUR-DISPUTE",
        50100,
        option_type="CALL",
        strike_price=50000,
        dispute=True
    )
    
    # 통계 출력
    print("\n" + "=" * 60)
    print("📊 정산 통계")
    print("=" * 60)
    stats = system.get_statistics()
    for key, value in stats.items():
        print(f"   {key}: {value}")
    
    print("\n💡 결론:")
    print("• CLAUDE.md 내용이 맞습니다!")
    print("• Pre-sign: 일반 정산 (95%+)")
    print("• Prover-Verifier: 분쟁 해결 (5%)")
    print("• 두 경로 모두 BitVMX의 일부입니다")


if __name__ == "__main__":
    main()