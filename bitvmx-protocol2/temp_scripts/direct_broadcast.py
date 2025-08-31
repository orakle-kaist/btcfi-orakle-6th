#!/usr/bin/env python3
"""
직접 트랜잭션 생성 및 브로드캐스트
"""
import hashlib
import requests
from bitcoinutils.setup import setup
from bitcoinutils.transactions import Transaction, TxInput, TxOutput
from bitcoinutils.keys import PrivateKey, P2wpkhAddress
from bitcoinutils.script import Script

def main():
    setup('testnet')
    
    # Our funding UTXO
    funding_txid = "00c57240bf32c053bcc6f2ca37a45609064051ed7c10023a99af670db9beb24f"
    funding_vout = 0
    funding_amount = 149998922
    
    # Our key
    privkey_hex = "d8a1e1224e63135765bde9dc8a2c8e403eee8be73d3589d58c5ddbf9dce3fdf4"
    
    print("=" * 60)
    print("DIRECT TRANSACTION BROADCAST")
    print("=" * 60)
    
    # Convert private key
    privkey = PrivateKey.from_hexstring(privkey_hex)
    pubkey = privkey.get_public_key()
    address = pubkey.get_segwit_address()
    
    print(f"📊 Our address: {address.to_string()}")
    print(f"💰 Funding: {funding_amount:,} sats")
    
    # Create simple transaction
    tx_in = TxInput(funding_txid, funding_vout)
    
    # Output to ourselves minus fee
    fee = 500
    tx_out = TxOutput(funding_amount - fee, address.to_script_pub_key())
    
    # Create transaction
    tx = Transaction([tx_in], [tx_out], has_segwit=True)
    
    # Sign the transaction
    sig = privkey.sign_segwit_input(tx, 0, Script(['OP_DUP', 'OP_HASH160', pubkey.to_hash160(), 'OP_EQUALVERIFY', 'OP_CHECKSIG']), funding_amount)
    tx.witnesses = [[sig, pubkey.to_hex()]]
    
    # Get signed transaction hex
    signed_tx_hex = tx.serialize()
    
    print(f"\n📝 Transaction created:")
    print(f"   Size: {len(signed_tx_hex) // 2} bytes")
    print(f"   TXID: {tx.get_txid()}")
    
    # Broadcast
    print("\n📡 Broadcasting...")
    response = requests.post(
        "https://mutinynet.com/api/tx",
        data=signed_tx_hex,
        headers={'Content-Type': 'text/plain'},
        timeout=10
    )
    
    if response.status_code == 200:
        txid = response.text.strip()
        print(f"✅ SUCCESS!")
        print(f"   TXID: {txid}")
        print(f"   Explorer: https://mutinynet.com/tx/{txid}")
        return True
    else:
        print(f"❌ Failed: {response.status_code}")
        print(f"   Response: {response.text[:200]}")
        return False

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()