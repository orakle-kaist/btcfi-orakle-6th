#!/usr/bin/env python3
"""
Test auto-funding functionality
"""
from prover_app.domain.services.mutinynet_utxo_service import MutinynetUTXOService

def test_auto_funding():
    """Test automatic UTXO fetching from Mutinynet"""
    
    # Our test address with funds
    address = "tb1qt8rdur557nz338g3lekc6458pj0dl63c0s9904"
    
    # Create service
    utxo_service = MutinynetUTXOService()
    
    print(f"🔍 Fetching UTXOs for {address}")
    print("=" * 60)
    
    # Get all UTXOs
    utxos = utxo_service.get_utxos_for_address(address)
    
    if utxos:
        print(f"✅ Found {len(utxos)} UTXOs:")
        for utxo in utxos[:5]:  # Show first 5
            print(f"   - {utxo.txid[:8]}...:{utxo.vout} = {utxo.value:,} sats")
    else:
        print("❌ No UTXOs found")
    
    print("\n" + "-" * 60)
    
    # Get funding info for setup
    funding_info = utxo_service.get_funding_tx_info(address)
    
    if funding_info:
        print("📋 Best UTXO for funding:")
        print(f"   TX ID: {funding_info['funding_tx_id']}")
        print(f"   Output Index: {funding_info['funding_index']}")
        print(f"   Value: {funding_info['funding_value']:,} sats")
        
        print("\n✅ Ready to create Setup with real funding!")
        print("\nNext step: Use this in setup creation:")
        print(f'   "funding_tx_id": "{funding_info["funding_tx_id"]}"')
        print(f'   "funding_index": {funding_info["funding_index"]}')
    else:
        print("❌ No suitable UTXO for funding")

if __name__ == "__main__":
    test_auto_funding()