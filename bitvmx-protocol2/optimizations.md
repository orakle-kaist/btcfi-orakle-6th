# BitVMX 최적화 전략

## 1. Lazy Transaction Generation
- Setup에서 모든 TX를 미리 만들지 않음
- 분쟁 발생 시에만 필요한 TX 생성
- 메모리 사용량 99% 감소

## 2. Checkpoint System  
- 100 steps마다 checkpoint
- 분쟁 시 가장 가까운 checkpoint부터 시작
- 검증 깊이 감소

## 3. Merkle Tree Optimization
- TX 자체 대신 TX 해시만 저장
- 필요 시 TX 재생성
- 메모리 90% 절약

## 4. Multi-level Compilation
```
BTCFi Logic (Python/JS)
    ↓
Simplified C (수동 최적화)
    ↓  
RISC-V Assembly (직접 작성)
    ↓
BitVMX Execution (<100 steps)
```

## 5. 실용적 구현 방향

### Option 1: 핵심 검증만
- 복잡한 계산: 오프체인
- BitVMX: 결과 검증만 (해시 체크)
- 목표: 50 steps 이내

### Option 2: 단계별 실행
- 전체 로직을 여러 작은 프로그램으로 분할
- 각 프로그램 <100 steps
- 순차적 실행 및 검증

### Option 3: Custom Opcodes
- 자주 쓰는 연산을 하나의 opcode로
- RISC-V 에뮬레이터 수정
- Step 수 대폭 감소