#!/usr/bin/env python3
"""
Migrate JSON data to SQLite database
"""
from prover_app.persistence.database import BitVMXDatabase
import json
import os

def migrate_and_test():
    """Migrate JSON to DB and test functionality"""
    
    print("🔄 Starting migration to SQLite database")
    print("=" * 60)
    
    # Initialize database
    db = BitVMXDatabase()
    
    # 1. Create our active setup in DB
    print("\n📋 Creating Setup in database...")
    setup_data = {
        'setup_uuid': '84e9d815-5227-41ff-a0eb-b898456294cf',
        'name': 'BTCFi Unified Option System',
        'funding_tx_id': '0' * 64,  # dummy for now
        'funding_index': 0,
        'prover_address': 'tb1qt8rdur557nz338g3lekc6458pj0dl63c0s9904',
        'elf_file': 'execution_files/btcfi_option_unified.elf',
        'input_hex': '00000000404b4c0080584f0064000000',
        'metadata': {
            'max_steps': 10000,
            'verifier_count': 1
        }
    }
    
    try:
        db.create_setup(setup_data)
        print(f"✅ Setup created: {setup_data['setup_uuid']}")
    except Exception as e:
        print(f"⚠️ Setup may already exist: {e}")
    
    # 2. Migrate existing JSON data
    print("\n📦 Migrating JSON data...")
    db.migrate_from_json()
    
    # 3. Test database functionality
    print("\n🧪 Testing database operations...")
    
    # Get active setup
    active_setup = db.get_active_setup()
    if active_setup:
        print(f"✅ Active setup found: {active_setup['setup_uuid']}")
    
    # Get options
    options = db.get_active_options(setup_uuid='84e9d815-5227-41ff-a0eb-b898456294cf')
    print(f"✅ Found {len(options)} active options")
    
    if options:
        print("\n📊 Sample options:")
        for opt in options[:3]:
            print(f"   - {opt['product_id']}: {opt['option_type']} @ ${opt['strike_price']:,.0f}")
    
    # Get pool status
    pool = db.get_or_create_pool("main")
    print(f"\n💰 Pool status:")
    print(f"   Available: {pool['available_btc']} BTC")
    print(f"   Locked: {pool.get('locked_btc', 0)} BTC")
    
    # 4. Create a test option
    print("\n➕ Adding test option to DB...")
    test_option = {
        'product_id': 'OPT-db-test-001',
        'setup_uuid': '84e9d815-5227-41ff-a0eb-b898456294cf',
        'option_type': 'CALL',
        'strike_price': 75000,
        'expiry_date': '2025-09-01 12:00:00',
        'premium_btc': 0.001,
        'quantity': 1.0,
        'greeks': {'delta': 0.5, 'theta': -0.02}
    }
    
    try:
        db.register_option(test_option)
        print(f"✅ Test option created: {test_option['product_id']}")
        
        # Verify it was saved
        saved_option = db.get_option(test_option['product_id'])
        if saved_option:
            print(f"✅ Verified: Option retrieved from DB")
    except Exception as e:
        print(f"⚠️ Test option creation: {e}")
    
    print("\n" + "=" * 60)
    print("✅ Migration complete! Database is ready.")
    print(f"📁 Database file: bitvmx_data.db")
    
    # Show summary
    print("\n📊 Database Summary:")
    with db.get_connection() as conn:
        cursor = conn.cursor()
        
        cursor.execute("SELECT COUNT(*) FROM setups")
        setup_count = cursor.fetchone()[0]
        print(f"   Setups: {setup_count}")
        
        cursor.execute("SELECT COUNT(*) FROM option_products")
        option_count = cursor.fetchone()[0]
        print(f"   Options: {option_count}")
        
        cursor.execute("SELECT COUNT(*) FROM pools")
        pool_count = cursor.fetchone()[0]
        print(f"   Pools: {pool_count}")
        
        cursor.execute("SELECT COUNT(*) FROM transactions")
        tx_count = cursor.fetchone()[0]
        print(f"   Transactions: {tx_count}")

if __name__ == "__main__":
    migrate_and_test()