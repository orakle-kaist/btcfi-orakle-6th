#!/usr/bin/env python3
"""
Update existing setup with real funding and create transaction
"""
import requests
import json
from prover_app.persistence.database import BitVMXDatabase
from prover_app.domain.services.mutinynet_utxo_service import MutinynetUTXOService

def create_option_tx_with_real_funding():
    """Create option registration transaction with real funding"""
    
    print("🚀 Option Registration with Real Funding TX")
    print("=" * 60)
    
    # Initialize services
    db = BitVMXDatabase()
    utxo_service = MutinynetUTXOService()
    
    # Our setup
    setup_uuid = "84e9d815-5227-41ff-a0eb-b898456294cf"
    
    # 1. Get real funding UTXO
    print("\n💰 Step 1: Getting Real Funding UTXO")
    address = "tb1qt8rdur557nz338g3lekc6458pj0dl63c0s9904"
    funding_info = utxo_service.get_funding_tx_info(address)
    
    if funding_info:
        print(f"✅ Found UTXO:")
        print(f"   TX: {funding_info['funding_tx_id']}")
        print(f"   Index: {funding_info['funding_index']}")
        print(f"   Value: {funding_info['funding_value']:,} sats")
        
        # Update setup in database
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE setups 
                SET funding_tx_id = ?, funding_index = ?
                WHERE setup_uuid = ?
            ''', (funding_info['funding_tx_id'], funding_info['funding_index'], setup_uuid))
            print(f"✅ Updated Setup with real funding")
    else:
        print("❌ No funding UTXO found")
        return
    
    # 2. Register an option
    print("\n📝 Step 2: Register Option Product")
    
    option_data = {
        "option_type": "CALL",
        "strike_price": 68000,
        "expiry_date": "2025-09-01T12:00:00",
        "quantity": 0.001,
        "premium": 0.0001,
        "issuer": "real-funding-test"
    }
    
    response = requests.post(
        f"http://localhost:8081/api/v1/option/register?setup_uuid={setup_uuid}",
        json=option_data
    )
    
    if response.status_code == 200:
        result = response.json()
        product_id = result['product_id']
        print(f"✅ Option registered: {product_id}")
        
        # Save to DB
        db.register_option(result)
    else:
        print(f"❌ Registration failed: {response.text}")
        return
    
    # 3. Submit input for option registration
    print("\n🔐 Step 3: Submit Input to BitVMX")
    
    # Input for option_registration.c:
    # struct: option_type(4) + strike_price(4) + quantity(4) + expiry_timestamp(4)
    # CALL=0, strike=$68000, quantity=100, expiry=future
    input_hex = "00000000a0090100640000005f680000"  # Simplified input
    
    response = requests.post(
        f"http://localhost:8081/api/v1/input",
        json={
            "setup_uuid": setup_uuid,
            "input_hex": input_hex
        }
    )
    
    if response.status_code == 200:
        print(f"✅ Input submitted")
    else:
        print(f"⚠️ Input submission: {response.status_code}")
    
    # 4. Try to create transaction
    print("\n📋 Step 4: Create Bitcoin Transaction")
    
    response = requests.post(
        f"http://localhost:8081/api/v1/next_step",
        json={"setup_uuid": setup_uuid}
    )
    
    if response.status_code == 200:
        result = response.json()
        print(f"✅ Transaction created!")
        print(f"   Result: {json.dumps(result, indent=2)}")
        
        # Record in database
        db.record_transaction({
            'tx_id': f"TX-{product_id}",
            'setup_uuid': setup_uuid,
            'product_id': product_id,
            'tx_type': 'OPTION_REGISTER',
            'status': 'BROADCAST'
        })
        
    elif response.status_code == 500:
        print("❌ Transaction broadcast failed")
        print("   This may be due to:")
        print("   - UTXO already spent")
        print("   - Insufficient fees")
        print("   - Network issues")
        
        # Check if we can get the raw transaction
        response_text = response.text
        if "bad-txns-inputs-missingorspent" in response_text:
            print("\n⚠️ The funding UTXO may have been spent")
            print("   Need to find a new unspent UTXO")
    else:
        print(f"❌ Unexpected error: {response.status_code}")
    
    # 5. Summary
    print("\n" + "=" * 60)
    print("📊 Summary:")
    print(f"✅ Setup: {setup_uuid}")
    print(f"✅ Funding TX: {funding_info['funding_tx_id'][:16]}...")
    print(f"✅ Option: {product_id}")
    
    # Show current state
    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT COUNT(*) FROM transactions')
        tx_count = cursor.fetchone()[0]
        print(f"✅ Total transactions in DB: {tx_count}")

if __name__ == "__main__":
    create_option_tx_with_real_funding()