#!/usr/bin/env python3

import hashlib
from bitcoinutils.setup import setup
from bitcoinutils.keys import PrivateKey, P2wpkhAddress
from bitcoinutils.transactions import Transaction, TxInput, TxOutput, TxWitnessInput
from bitcoinutils.script import Script

def create_funding_tx():
    # 테스트넷 설정
    setup('testnet')
    
    # 개인키
    priv_key_hex = "d8a1e1224e63135765bde9dc8a2c8e403eee8be73d3589d58c5ddbf9dce3fdf4"
    priv_key = PrivateKey(secret_exponent=int(priv_key_hex, 16))
    pub_key = priv_key.get_public_key()
    
    # 우리 주소 생성 (P2WPKH)
    p2wpkh_addr = P2wpkhAddress.from_witness_program(pub_key.get_witness_program())
    our_address_str = "tb1qt8rdur557nz338g3lekc6458pj0dl63c0s9904"
    
    print(f"Generated address: {p2wpkh_addr.to_string()}")
    print(f"Expected address: {our_address_str}")
    
    # UTXO 정보
    prev_txid = "5e10ac0775e392386aeae9848a98d76f13663666aadec37ae8f61be1b56435d7"
    prev_vout = 0
    prev_value = 1179983810  # sats
    
    # 새 funding 금액 (2.6 BTC)
    funding_amount = 260000000  # sats
    fee = 10000  # 수수료
    change_amount = prev_value - funding_amount - fee
    
    # Input 생성 (P2WPKH)
    tx_input = TxInput(prev_txid, prev_vout)
    
    # Output 생성
    # Funding output
    tx_output_funding = TxOutput(funding_amount, p2wpkh_addr.to_script_pub_key())
    
    # Change output
    tx_output_change = TxOutput(change_amount, p2wpkh_addr.to_script_pub_key())
    
    # 트랜잭션 생성
    tx = Transaction([tx_input], [tx_output_funding, tx_output_change], has_segwit=True)
    
    # Witness 서명
    sig = priv_key.sign_segwit_input(tx, 0, p2wpkh_addr.to_script_pub_key(), prev_value)
    witness = TxWitnessInput([sig, pub_key.to_hex()])
    tx.witnesses = [witness]
    
    print(f"\nNew Funding Transaction:")
    print(f"TXID: {tx.get_txid()}")
    print(f"Raw TX: {tx.serialize()}")
    print(f"Funding Output: {our_address_str} - {funding_amount/100000000:.8f} BTC")
    print(f"Change Output: {our_address_str} - {change_amount/100000000:.8f} BTC")
    print(f"Fee: {fee/100000000:.8f} BTC")
    
    return tx.get_txid(), tx.serialize()

if __name__ == "__main__":
    txid, raw_tx = create_funding_tx()