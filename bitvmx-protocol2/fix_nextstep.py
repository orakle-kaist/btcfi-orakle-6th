#!/usr/bin/env python3
"""
Next Step 트랜잭션 복구 스크립트
새로운 UTXO를 사용하여 BitVMX Next Step을 진행합니다.
"""

import json
import requests
import sys

def get_latest_utxo(address):
    """최신 UTXO 가져오기"""
    response = requests.get(f"https://mutinynet.com/api/address/{address}/utxo")
    if response.status_code == 200:
        utxos = response.json()
        if utxos:
            # 가장 큰 UTXO 선택
            largest = max(utxos, key=lambda x: x['value'])
            print(f"Found UTXO: {largest['txid']}:{largest['vout']}")
            print(f"Amount: {largest['value']} sats")
            return largest['txid'], largest['vout'], largest['value']
    return None, None, None

def trigger_next_step(setup_uuid):
    """Next Step 트랜잭션 트리거"""
    url = "http://localhost:8001/api/v1/next_step"
    headers = {"Content-Type": "application/json"}
    data = {"setup_uuid": setup_uuid}
    
    response = requests.post(url, headers=headers, json=data)
    return response

def main():
    address = "tb1qt8rdur557nz338g3lekc6458pj0dl63c0s9904"
    setup_uuid = "de15532d-2201-43ba-af2a-912cfd54248c"
    
    print(f"Checking UTXOs for {address}...")
    txid, vout, amount = get_latest_utxo(address)
    
    if not txid:
        print("No UTXOs available!")
        return 1
    
    print(f"\nTriggering Next Step for Setup: {setup_uuid}")
    response = trigger_next_step(setup_uuid)
    
    if response.status_code == 200:
        print("Next Step triggered successfully!")
        print(response.json())
    else:
        print(f"Failed: {response.status_code}")
        print(response.text)
    
    return 0

if __name__ == "__main__":
    sys.exit(main())