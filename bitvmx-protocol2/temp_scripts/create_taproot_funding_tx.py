#!/usr/bin/env python3

import json
import hashlib
import secrets
from bitcoinutils.setup import setup
from bitcoinutils.keys import PrivateKey, PublicKey
from bitcoinutils.transactions import Transaction, TxInput, TxOutput, TxWitnessInput
from bitcoinutils.script import Script
import requests

def create_taproot_funding_tx():
    """
    Create a proper Taproot (P2TR) funding transaction for BitVMX protocol.
    This creates the initial Taproot UTXO that will be consumed by the Prover TX.
    """
    
    # Setup for testnet (Mutinynet)
    setup('testnet')
    
    # Generate new private key for the Taproot address
    taproot_priv_key = PrivateKey(b=secrets.token_bytes(32))
    taproot_pub_key = taproot_priv_key.get_public_key()
    
    # Get available UTXO from wallet (we'll use an existing P2WPKH UTXO)
    # For demonstration, using a known UTXO from previous transactions
    # In production, you'd query the wallet for available UTXOs
    
    # Example source UTXO (P2WPKH from wallet)
    source_txid = "5e10ac0775e392386aeae9848a98d76f13663666aadec37ae8f61be1b56435d7"
    source_index = 0
    source_amount = 1179983810  # satoshis
    
    # Source private key (from wallet that owns the P2WPKH UTXO)
    # This would normally come from wallet
    source_priv_key_hex = "d28a5b3e8c8f6a2d1b7e9f4c3a5d8b2e7f1c4a9d6b3e8f5c2a7d4b1e9c6f3a8d"
    source_priv_key = PrivateKey(secret_exponent=int(source_priv_key_hex, 16))
    source_pub_key = source_priv_key.get_public_key()
    
    # Calculate Taproot output script (P2TR)
    # Remove the first byte (version) from compressed pubkey for x-only format
    taproot_internal_pubkey = taproot_pub_key.to_hex()[2:]  # Remove '02' or '03' prefix
    
    # Create P2TR output script
    # OP_1 (0x51) followed by 32-byte x-only pubkey
    taproot_script = Script(['OP_1', taproot_internal_pubkey])
    
    # Transaction fee
    fee = 5000  # 5000 satoshis
    
    # Output amount
    output_amount = source_amount - fee
    
    # Create transaction
    tx_input = TxInput(source_txid, source_index)
    tx_output = TxOutput(output_amount, taproot_script)
    
    # Create the transaction with witness flag
    tx = Transaction([tx_input], [tx_output], has_segwit=True)
    
    # Sign the input (P2WPKH)
    # Create script code for P2WPKH
    source_pkh = hashlib.new('ripemd160', hashlib.sha256(bytes.fromhex(source_pub_key.to_hex())).digest()).digest()
    script_code = Script(['OP_DUP', 'OP_HASH160', source_pkh.hex(), 'OP_EQUALVERIFY', 'OP_CHECKSIG'])
    
    # Sign the transaction
    sig = source_priv_key.sign_segwit_input(tx, 0, script_code, source_amount)
    witness = TxWitnessInput([sig, source_pub_key.to_hex()])
    tx.witnesses = [witness]
    
    # Get transaction details
    txid = tx.get_txid()
    raw_tx = tx.serialize()
    
    # Save funding transaction info
    funding_tx_data = {
        "funding_tx_id": txid,
        "funding_index": 0,
        "funding_amount_satoshis": output_amount,
        "taproot_private_key": taproot_priv_key.to_bytes().hex(),
        "taproot_public_key": taproot_pub_key.to_hex(),
        "taproot_internal_pubkey": taproot_internal_pubkey,
        "raw_transaction": raw_tx,
        "network": "mutinynet",
        "tx_type": "taproot_funding",
        "output_script_type": "v1_p2tr"
    }
    
    # Save to file
    with open("taproot_funding_tx.json", 'w') as f:
        json.dump(funding_tx_data, f, indent=2)
    
    print("=" * 60)
    print("BitVMX Taproot Funding Transaction Created")
    print("=" * 60)
    print(f"Funding TX ID: {txid}")
    print(f"Funding Index: 0")
    print(f"Funding Amount: {output_amount} satoshis ({output_amount/100000000:.8f} BTC)")
    print(f"Taproot Public Key: {taproot_pub_key.to_hex()}")
    print(f"Output Type: P2TR (Taproot)")
    print("-" * 60)
    print(f"Raw Transaction: {raw_tx}")
    print("=" * 60)
    
    return txid, raw_tx, funding_tx_data

def broadcast_funding_tx(raw_tx):
    """
    Broadcast the funding transaction to Mutinynet
    """
    url = "https://mutinynet.com/api/tx"
    
    try:
        response = requests.post(url, data=raw_tx)
        if response.status_code == 200:
            print(f"✅ Funding TX broadcast successfully!")
            print(f"TX ID: {response.text}")
            return response.text
        else:
            print(f"❌ Failed to broadcast: {response.text}")
            return None
    except Exception as e:
        print(f"❌ Error broadcasting: {e}")
        return None

if __name__ == "__main__":
    # Create the Taproot funding transaction
    txid, raw_tx, funding_data = create_taproot_funding_tx()
    
    # Optionally broadcast it
    print("\nWould you like to broadcast this transaction? (y/n)")
    if input().lower() == 'y':
        broadcast_funding_tx(raw_tx)
    
    print("\n✅ Funding transaction data saved to 'taproot_funding_tx.json'")
    print("Use this funding TX info when creating your BitVMX setup.")