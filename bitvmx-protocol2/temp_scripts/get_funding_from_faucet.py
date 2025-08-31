#!/usr/bin/env python3

import requests
import json
import time

def get_funds_from_faucet():
    """Get funds from Mutinynet faucet to create source UTXO"""
    
    # Our control address
    address = "tb1qd28npep0s8frcm3y7dxqajkcy2m40eysplyr9v"
    amount = 100000000  # 1 BTC in satoshis
    
    url = "https://faucet.mutinynet.com/api/onchain"
    headers = {
        "Accept": "*/*",
        "Content-Type": "application/json",
        "Origin": "https://faucet.mutinynet.com",
        "Referer": "https://faucet.mutinynet.com/",
    }
    
    data = {
        "sats": amount,
        "address": address
    }
    
    print(f"Requesting {amount/100000000:.8f} BTC from faucet...")
    print(f"Destination: {address}")
    
    try:
        response = requests.post(url, headers=headers, json=data)
        
        if response.status_code == 200:
            result = response.json()
            txid = result.get('txid')
            print(f"\n✅ Faucet request successful!")
            print(f"TX ID: {txid}")
            print(f"Explorer: https://mutinynet.com/tx/{txid}")
            
            # Wait a bit for transaction to propagate
            print("\n⏳ Waiting for transaction to propagate...")
            time.sleep(5)
            
            # Get transaction details to find our output
            tx_url = f"https://mutinynet.com/api/tx/{txid}"
            tx_response = requests.get(tx_url)
            
            if tx_response.status_code == 200:
                tx_data = tx_response.json()
                
                # Find our output
                for idx, vout in enumerate(tx_data.get('vout', [])):
                    if vout.get('scriptpubkey_address') == address:
                        print(f"\n📋 New UTXO created:")
                        print(f"   TXID: {txid}")
                        print(f"   Index: {idx}")
                        print(f"   Amount: {vout['value']} satoshis")
                        print(f"   Address: {address}")
                        
                        return {
                            'txid': txid,
                            'index': idx,
                            'amount': vout['value'],
                            'address': address
                        }
            
            return {'txid': txid}
            
        else:
            print(f"❌ Faucet request failed: {response.text}")
            return None
            
    except Exception as e:
        print(f"❌ Error: {e}")
        return None

if __name__ == "__main__":
    result = get_funds_from_faucet()
    if result:
        print("\n✅ Ready to use this UTXO for creating Taproot funding TX")