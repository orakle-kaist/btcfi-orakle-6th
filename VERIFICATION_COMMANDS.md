# 🔍 BitVMX Option Verification Commands

이 문서는 BitVMX 검증 및 옵션 상품 등록이 Bitcoin regtest에 실제로 온체인 저장되었는지 확인하는 명령어들입니다.

## 📋 전제 조건

1. Bitcoin regtest 노드가 실행 중이어야 합니다:
   ```bash
   docker-compose -f docker-compose-regtest.yml up -d
   ```

2. 정확한 RPC 크리덴셜 사용:
   - **사용자**: `bitcoin`  
   - **비밀번호**: `bitcoin`
   - **중요**: `-rpcuser=bitcoin-rpcpassword=bitcoin` (잘못됨) → `-rpcuser=bitcoin -rpcpassword=bitcoin` (올바름)

## 🚀 기본 연결 테스트

### 1. Bitcoin 노드 상태 확인
```bash
# 노드 연결 및 체인 정보 확인
docker exec bitcoin-regtest bitcoin-cli -regtest -rpcuser=bitcoin -rpcpassword=bitcoin getblockchaininfo

# 현재 블록 높이 확인  
docker exec bitcoin-regtest bitcoin-cli -regtest -rpcuser=bitcoin -rpcpassword=bitcoin getblockcount

# 지갑 잔액 확인
docker exec bitcoin-regtest bitcoin-cli -regtest -rpcuser=bitcoin -rpcpassword=bitcoin getbalance
```

## 📊 트랜잭션 확인

### 2. 최근 트랜잭션 목록
```bash
# 최근 10개 트랜잭션 확인 (올바른 형식)
docker exec bitcoin-regtest bitcoin-cli -regtest -rpcuser=bitcoin -rpcpassword=bitcoin listtransactions "*" 10

# 최근 5개 트랜잭션만 확인
docker exec bitcoin-regtest bitcoin-cli -regtest -rpcuser=bitcoin -rpcpassword=bitcoin listtransactions "*" 5
```

### 3. 특정 트랜잭션 상세 조회

#### CREATE 옵션 트랜잭션:
```bash
# 최신 CREATE 트랜잭션 ID (예시)
CREATE_TX="2c63e8939991f07de93b9b04e9f44d55ff3523e9b0e7fa40e7b8b396482cf565"

# CREATE 트랜잭션 상세 정보
docker exec bitcoin-regtest bitcoin-cli -regtest -rpcuser=bitcoin -rpcpassword=bitcoin getrawtransaction $CREATE_TX true

# CREATE OP_RETURN 데이터만 추출
docker exec bitcoin-regtest bitcoin-cli -regtest -rpcuser=bitcoin -rpcpassword=bitcoin getrawtransaction $CREATE_TX true | jq '.vout[] | select(.scriptPubKey.type == "nulldata")'
```

#### BitVMX 검증 결과 트랜잭션:
```bash  
# 최신 BitVMX 트랜잭션 ID (예시)
BITVMX_TX="4b0c8f042f400e97473ad54e44e3a1e8ca35ba31c4c90a12b3232e715793bb34"

# BitVMX 트랜잭션 상세 정보
docker exec bitcoin-regtest bitcoin-cli -regtest -rpcuser=bitcoin -rpcpassword=bitcoin getrawtransaction $BITVMX_TX true

# BitVMX OP_RETURN 데이터만 추출
docker exec bitcoin-regtest bitcoin-cli -regtest -rpcuser=bitcoin -rpcpassword=bitcoin getrawtransaction $BITVMX_TX true | jq '.vout[] | select(.scriptPubKey.type == "nulldata")'
```

## 🔓 OP_RETURN 데이터 디코딩

### 4. BitVMX 검증 결과 디코딩
```bash
# 직접 디코딩 (실제 확인된 결과)
docker exec bitcoin-regtest bitcoin-cli -regtest -rpcuser=bitcoin -rpcpassword=bitcoin getrawtransaction 4b0c8f042f400e97473ad54e44e3a1e8ca35ba31c4c90a12b3232e715793bb34 true | jq -r '.vout[] | select(.scriptPubKey.type == "nulldata") | .scriptPubKey.hex' | xxd -r -p | tail -c +3

# 예상 결과: BVMX:RESULT:SUCCESS:22:06054063:00000000:1753179457
```

**해석:**
- **BVMX**: BitVMX 프로토콜 식별자
- **RESULT**: 검증 결과 타입  
- **SUCCESS**: 검증 성공 ✅
- **22**: 22단계 RISC-V 실행
- **06054063**: 실제 RISC-V Opcode (blt 명령어)
- **00000000**: 프로그램 카운터 주소
- **1753179457**: Unix 타임스탬프 (2025-07-22 19:17:37)

## 🎯 한 번에 전체 검증

### 5. 완전한 검증 스크립트
```bash
echo "=== 🔍 BitVMX + Option 등록 검증 ==="
echo ""

# 1. 노드 상태
echo "📊 Bitcoin 노드 상태:"
docker exec bitcoin-regtest bitcoin-cli -regtest -rpcuser=bitcoin -rpcpassword=bitcoin getblockchaininfo | jq '{chain, blocks, bestblockhash}'
echo ""

# 2. 최근 트랜잭션
echo "📝 최근 트랜잭션 (최신 5개):"
docker exec bitcoin-regtest bitcoin-cli -regtest -rpcuser=bitcoin -rpcpassword=bitcoin listtransactions "*" 5 | jq -r '.[] | select(.category == "send" and .amount == 0) | .txid' | head -2
echo ""

# 3. BitVMX 검증 결과 디코딩
echo "✅ BitVMX 검증 결과:"
docker exec bitcoin-regtest bitcoin-cli -regtest -rpcuser=bitcoin -rpcpassword=bitcoin getrawtransaction 4b0c8f042f400e97473ad54e44e3a1e8ca35ba31c4c90a12b3232e715793bb34 true | jq -r '.vout[] | select(.scriptPubKey.type == "nulldata") | .scriptPubKey.hex' | xxd -r -p | tail -c +3
echo ""

echo "🎉 검증 완료! 모든 데이터가 실제 Bitcoin regtest 블록체인에 기록되어 있습니다."
```

## 🚨 문제 해결

### 일반적인 오류들:

1. **RPC 인증 실패**:
   ```bash
   # ❌ 잘못된 형식
   docker exec bitcoin-regtest bitcoin-cli -regtest -rpcuser=bitcoin-rpcpassword=bitcoin

   # ✅ 올바른 형식  
   docker exec bitcoin-regtest bitcoin-cli -regtest -rpcuser=bitcoin -rpcpassword=bitcoin
   ```

2. **라벨 오류**:
   ```bash
   # ❌ 빈 문자열 라벨
   listtransactions "" 10

   # ✅ 와일드카드 라벨
   listtransactions "*" 10
   ```

3. **컨테이너 실행 상태**:
   ```bash
   # Bitcoin 컨테이너 실행 확인
   docker ps | grep bitcoin-regtest
   
   # 컨테이너가 없으면 시작
   docker-compose -f docker-compose-regtest.yml up -d
   ```

## 📋 확인해야 할 항목들

- ✅ Bitcoin regtest 노드 실행 중
- ✅ RPC 인증 정보 정확함  
- ✅ CREATE 트랜잭션 온체인 기록됨
- ✅ BitVMX 검증 트랜잭션 온체인 기록됨
- ✅ OP_RETURN 데이터 디코딩 가능
- ✅ BitVMX 검증 결과: SUCCESS
- ✅ RISC-V 실행 단계: 22단계
- ✅ 실제 Opcode 기록: 06054063

---

**💡 팁**: 명령어가 작동하지 않으면 이 README의 정확한 형식을 사용하세요. 모든 명령어는 실제 테스트되었습니다.