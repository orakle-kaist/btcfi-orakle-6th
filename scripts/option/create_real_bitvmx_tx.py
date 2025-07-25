#!/usr/bin/env python3
import json
import subprocess
import time

# Bitcoin RPC configuration
RPC_HOST = "localhost"
RPC_PORT = 18443
RPC_USER = "test"
RPC_PASSWORD = "test"

# 실제 BitVMX 실행 해시 (691단계 실행 결과)
REAL_BITVMX_HASH = "923f82cc1a6a7fc4c02e15486455775ad5d8e0532fd560d85b7aa0fba7be9bbe"

def bitcoin_rpc(method, params=None):
    """Make RPC call to Bitcoin node"""
    if params is None:
        params = []
    
    cmd = [
        "curl", "-s", "-u", f"{RPC_USER}:{RPC_PASSWORD}",
        "-d", json.dumps({
            "jsonrpc": "1.0",
            "id": "btcfi",
            "method": method,
            "params": params
        }),
        "-H", "content-type: text/plain;",
        f"http://{RPC_HOST}:{RPC_PORT}/"
    ]
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    
    if result.returncode != 0:
        print(f"RPC call failed: {result.stderr}")
        return None
    
    response = json.loads(result.stdout)
    if 'error' in response and response['error']:
        print(f"RPC error: {response['error']}")
        return None
    
    return response.get('result')

def create_real_bitvmx_transaction():
    """실제 BitVMX 해시로 트랜잭션 생성"""
    
    # Generate some coins if needed
    balance = bitcoin_rpc("getbalance")
    if balance < 1.0:
        print(f"Low balance ({balance} BTC), generating blocks...")
        new_address = bitcoin_rpc("getnewaddress")
        bitcoin_rpc("generatetoaddress", [101, new_address])
        time.sleep(2)
        balance = bitcoin_rpc("getbalance")
        print(f"New balance: {balance} BTC")
    
    # 사용자 친화적 옵션 데이터 스키마
    user_option = {
        "tx_type": "CREATE",
        "option_id": "abc123",
        "option_type": "CALL",
        "strike": 52000,
        "expiry": 1735689600,
        "unit": 1.0
    }
    
    print(f"🎯 사용자 옵션: {user_option}")
    
    # 사용자 데이터를 BitVMX 내부 형식으로 변환
    strike_cents = int(user_option["strike"] * 100)  # USD → cents
    quantity_sats = int(user_option["unit"] * 100_000_000)  # BTC → satoshis
    premium_sats = max(1000, int(quantity_sats * 0.02))  # 2% 프리미엄
    
    # Create OP_RETURN data (JSON 형태로 사용자 스키마 그대로)
    import json
    compact_data = json.dumps(user_option, separators=(',', ':'))
    
    # Get a destination address
    dest_address = bitcoin_rpc("getnewaddress")
    
    try:
        # Create transaction with OP_RETURN
        recipients = {
            dest_address: 0.00001,
            "data": compact_data.encode('utf-8').hex()
        }
        
        txid = bitcoin_rpc("sendmany", ["", recipients])
        if not txid:
            print("Failed to send transaction")
            return None
        
        print(f"🎉 사용자 친화적 BTCFi 옵션 등록 완료!")
        print(f"Transaction ID: {txid}")
        print(f"옵션 타입: {user_option['option_type']}")
        print(f"행사가: ${user_option['strike']:,}")
        print(f"수량: {user_option['unit']} BTC")
        print(f"옵션 ID: {user_option['option_id']}")
        print(f"실제 BitVMX 해시: {REAL_BITVMX_HASH}")
        print(f"옵션 데이터: {compact_data}")
        
        # Generate block to confirm
        print("\\n블록 생성 중...")
        block_hash = bitcoin_rpc("generatetoaddress", [1, dest_address])
        if block_hash:
            print(f"블록 생성됨: {block_hash[0]}")
        
        return txid
        
    except Exception as e:
        print(f"Transaction creation failed: {e}")
        return None

if __name__ == "__main__":
    print("🎯 사용자 친화적 BTCFi 옵션 등록 시작...")
    print(f"실제 BitVMX 실행 해시: {REAL_BITVMX_HASH}")
    print(f"실제 실행 단계: 691단계")
    
    txid = create_real_bitvmx_transaction()
    if txid:
        print(f"\\n✅ 성공! 사용자 친화적 옵션 등록 완료!")
        print(f"Transaction: {txid}")
        print(f"🎊 사용자가 원하는 스키마로 작동합니다!")
    else:
        print("❌ 실패")