#!/usr/bin/env python3
"""BitVMX 챌린지-응답 자동화 시스템"""

import json
import time
import requests
import subprocess
from datetime import datetime
import os
import signal
import sys

class BitVMXAutomation:
    def __init__(self, txid=None, setup_uuid=None):
        # 실제 브로드캐스트된 트랜잭션
        self.funding_txid = txid or "8c5b24941f67125780d753328fe4a2b57c6f26b938186f4ac0190574a308eaf8"
        self.setup_uuid = setup_uuid or f"bitvmx-{int(time.time())}"
        self.verifier_url = "http://localhost:8080"
        self.prover_url = "http://localhost:8081"
        self.round_count = 0
        self.success_count = 0
        self.running = True
        
        signal.signal(signal.SIGINT, self.signal_handler)
    
    def signal_handler(self, sig, frame):
        print("\n⛔ 중지 신호 받음...")
        self.running = False
        self.show_summary()
        sys.exit(0)
    
    def health_check(self):
        """컨테이너 상태 확인"""
        print("🏥 시스템 헬스체크...")
        for name, port in [("Verifier", 8080), ("Prover", 8081)]:
            try:
                resp = requests.get(f"http://localhost:{port}/healthcheck", timeout=3)
                if resp.status_code == 200:
                    print(f"  ✅ {name}: 정상")
                else:
                    print(f"  ⚠️ {name}: 응답 코드 {resp.status_code}")
            except:
                print(f"  ❌ {name}: 연결 실패")
    
    def setup_protocol(self):
        """프로토콜 초기 설정"""
        setup_data = {
            "setup_uuid": self.setup_uuid,
            "network": "mutinynet",
            "funding_tx_id": self.funding_txid,
            "funding_index": 0,
            "funding_amount_of_satoshis": 95000,
            "step_fees_satoshis": 1000,
            "max_amount_of_steps": 1000,
            "amount_of_input_words": 10
        }
        
        url = f"{self.verifier_url}/api/v1/setup"
        try:
            resp = requests.post(url, json=setup_data, timeout=30)
            if resp.status_code == 200:
                print(f"✅ Setup 완료: {self.setup_uuid}")
                return True
            else:
                print(f"❌ Setup 실패: {resp.status_code}")
                return False
        except Exception as e:
            print(f"❌ Setup 오류: {e}")
            return False
    
    def run_challenge_response_loop(self):
        """챌린지-응답 루프 실행"""
        print("\n🎯 자동 챌린지-응답 시작")
        print("="*60)
        
        while self.running:
            self.round_count += 1
            print(f"\n🔄 라운드 {self.round_count}")
            
            # Next Step API 호출
            data = {"setup_uuid": self.setup_uuid}
            url = f"{self.verifier_url}/api/v1/next_step"
            
            try:
                resp = requests.post(url, json=data, timeout=10)
                
                if resp.status_code == 200:
                    print("  ✅ Verifier: 챌린지 생성")
                    
                    # Prover 응답
                    time.sleep(1)
                    prover_resp = requests.post(
                        f"{self.prover_url}/api/v1/next_step",
                        json=data,
                        timeout=10
                    )
                    
                    if prover_resp.status_code == 200:
                        print("  ✅ Prover: 응답 생성")
                        self.success_count += 1
                    else:
                        print(f"  ⚠️ Prover: {prover_resp.status_code}")
                    
                    print("  ✅ 라운드 완료")
                else:
                    print(f"  ❌ API 오류: {resp.status_code}")
            
            except Exception as e:
                print(f"  ❌ 오류: {e}")
            
            # 대기
            if self.running:
                time.sleep(5)
    
    def show_summary(self):
        """실행 요약 표시"""
        print("\n" + "="*60)
        print("📊 실행 요약")
        print("="*60)
        print(f"• 총 라운드: {self.round_count}")
        print(f"• 성공: {self.success_count}")
        print(f"• 성공률: {self.success_count/max(1, self.round_count)*100:.1f}%")
        print(f"• Setup UUID: {self.setup_uuid}")
        print(f"• Funding TX: {self.funding_txid}")
        print("="*60)
    
    def run(self):
        """메인 실행"""
        print("\n🚀 BitVMX 챌린지-응답 자동화")
        print("="*60)
        print(f"📍 Funding TX: {self.funding_txid[:32]}...")
        print(f"📍 Setup UUID: {self.setup_uuid}")
        print("="*60)
        
        # 1. 헬스체크
        self.health_check()
        
        # 2. Setup
        if not self.setup_protocol():
            print("Setup 실패로 종료")
            return
        
        # 3. 챌린지-응답 루프
        self.run_challenge_response_loop()
        
        # 4. 요약
        self.show_summary()

if __name__ == "__main__":
    import sys
    
    # 커맨드라인 인자 처리
    txid = sys.argv[1] if len(sys.argv) > 1 else None
    setup_uuid = sys.argv[2] if len(sys.argv) > 2 else None
    
    automation = BitVMXAutomation(txid, setup_uuid)
    automation.run()