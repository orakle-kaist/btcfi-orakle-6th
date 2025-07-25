#!/usr/bin/env python3
import json
import subprocess

# Bitcoin RPC configuration
RPC_HOST = "localhost"
RPC_PORT = 18443
RPC_USER = "test"
RPC_PASSWORD = "test"

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

def analyze_transaction(txid):
    """Analyze the BTCFi option registration transaction"""
    
    print(f"🔍 Analyzing BTCFi Transaction: {txid}")
    print("=" * 60)
    
    # Get transaction details
    tx_info = bitcoin_rpc("gettransaction", [txid])
    if not tx_info:
        print("❌ Failed to get transaction info")
        return
    
    print(f"Amount: {tx_info.get('amount', 'N/A')} BTC")
    print(f"Fee: {tx_info.get('fee', 'N/A')} BTC") 
    print(f"Confirmations: {tx_info.get('confirmations', 0)}")
    print(f"Block Hash: {tx_info.get('blockhash', 'Unconfirmed')}")
    print(f"Time: {tx_info.get('time', 'N/A')}")
    
    # Get raw transaction details using block hash
    block_hash = tx_info.get('blockhash')
    if block_hash:
        raw_tx = bitcoin_rpc("getrawtransaction", [txid, True, block_hash])
    else:
        raw_tx = bitcoin_rpc("getrawtransaction", [txid, True])
    if not raw_tx:
        print("❌ Failed to get raw transaction")
        return
        
    print(f"\\n📊 Transaction Details:")
    print(f"Version: {raw_tx.get('version', 'N/A')}")
    print(f"Size: {raw_tx.get('size', 'N/A')} bytes")
    print(f"Inputs: {len(raw_tx.get('vin', []))}")
    print(f"Outputs: {len(raw_tx.get('vout', []))}")
    
    # Analyze outputs
    print(f"\\n💰 Transaction Outputs:")
    for i, output in enumerate(raw_tx.get('vout', [])):
        print(f"  Output {i}:")
        print(f"    Value: {output.get('value', 0)} BTC")
        print(f"    Type: {output.get('scriptPubKey', {}).get('type', 'unknown')}")
        
        script_pub_key = output.get('scriptPubKey', {})
        if script_pub_key.get('type') == 'nulldata':
            # This is OP_RETURN data
            hex_data = script_pub_key.get('hex', '')
            if hex_data.startswith('6a'):  # OP_RETURN opcode
                try:
                    # Extract the data after OP_RETURN
                    data_length = int(hex_data[2:4], 16)
                    hex_payload = hex_data[4:4+(data_length*2)]
                    decoded_data = bytes.fromhex(hex_payload).decode('utf-8')
                    print(f"    OP_RETURN Data: {decoded_data}")
                    
                    # JSON 파싱 시도
                    import json
                    try:
                        option_json = json.loads(decoded_data)
                        print(f"\\n🎯 사용자 옵션 스키마:")
                        for key, value in option_json.items():
                            print(f"    {key}: {value}")
                        return option_json  # JSON 데이터 반환
                    except json.JSONDecodeError:
                        print(f"    (JSON이 아닌 텍스트 데이터)")
                        
                except Exception as e:
                    print(f"    OP_RETURN Hex: {hex_data}")
                    print(f"    Decode Error: {e}")
        
        addresses = script_pub_key.get('addresses', [])
        if addresses:
            print(f"    Address: {addresses[0]}")
    
    # Look for comment/memo in transaction
    comment = tx_info.get('comment', '')
    if comment:
        print(f"\\n📝 Transaction Comment: {comment}")
    
    print(f"\\n✅ BTCFi 옵션 트랜잭션 분석 완료!")
    print(f"OP_RETURN에서 사용자가 원하는 정확한 스키마가 추출되었습니다.")
    
    return True

if __name__ == "__main__":
    # Analyze the confirmed JSON transaction
    txid = "ff1fdd824308cf4814e139a49b419b40d5e3ed01dae7dcb884e30d7004572aae"
    analyze_transaction(txid)