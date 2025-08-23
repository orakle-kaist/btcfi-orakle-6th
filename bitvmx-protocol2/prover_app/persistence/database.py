"""
SQLite Database for BitVMX Option System
Replaces JSON file storage with proper database
"""
import sqlite3
import json
from datetime import datetime
from typing import List, Dict, Optional
from contextlib import contextmanager
import os

class BitVMXDatabase:
    """SQLite database for managing setups, options, and pools"""
    
    def __init__(self, db_path: str = "bitvmx_data.db"):
        self.db_path = db_path
        self.init_database()
    
    @contextmanager
    def get_connection(self):
        """Context manager for database connections"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()
    
    def init_database(self):
        """Initialize database tables"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Setups table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS setups (
                    setup_uuid TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    funding_tx_id TEXT,
                    funding_index INTEGER,
                    prover_address TEXT,
                    elf_file TEXT,
                    input_hex TEXT,
                    status TEXT DEFAULT 'ACTIVE',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    metadata JSON
                )
            ''')
            
            # Option products table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS option_products (
                    product_id TEXT PRIMARY KEY,
                    setup_uuid TEXT NOT NULL,
                    option_type TEXT NOT NULL,
                    strike_price REAL NOT NULL,
                    expiry_date TIMESTAMP NOT NULL,
                    premium_btc REAL NOT NULL,
                    quantity REAL NOT NULL,
                    status TEXT DEFAULT 'ACTIVE',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    greeks JSON,
                    FOREIGN KEY (setup_uuid) REFERENCES setups(setup_uuid)
                )
            ''')
            
            # Pools table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS pools (
                    pool_id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    total_btc REAL NOT NULL,
                    available_btc REAL NOT NULL,
                    locked_btc REAL DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Transactions table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS transactions (
                    tx_id TEXT PRIMARY KEY,
                    setup_uuid TEXT NOT NULL,
                    product_id TEXT,
                    tx_type TEXT NOT NULL,
                    tx_hex TEXT,
                    status TEXT DEFAULT 'PENDING',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    broadcast_at TIMESTAMP,
                    confirmed_at TIMESTAMP,
                    FOREIGN KEY (setup_uuid) REFERENCES setups(setup_uuid),
                    FOREIGN KEY (product_id) REFERENCES option_products(product_id)
                )
            ''')
            
            # Create indexes
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_products_setup ON option_products(setup_uuid)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_products_status ON option_products(status)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_tx_setup ON transactions(setup_uuid)')
    
    # Setup methods
    def create_setup(self, setup_data: Dict) -> str:
        """Create new setup"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO setups (setup_uuid, name, funding_tx_id, funding_index, 
                                  prover_address, elf_file, input_hex, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                setup_data['setup_uuid'],
                setup_data['name'],
                setup_data.get('funding_tx_id'),
                setup_data.get('funding_index', 0),
                setup_data.get('prover_address'),
                setup_data.get('elf_file'),
                setup_data.get('input_hex'),
                json.dumps(setup_data.get('metadata', {}))
            ))
            return setup_data['setup_uuid']
    
    def get_setup(self, setup_uuid: str) -> Optional[Dict]:
        """Get setup by UUID"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM setups WHERE setup_uuid = ?', (setup_uuid,))
            row = cursor.fetchone()
            if row:
                return dict(row)
            return None
    
    def get_active_setup(self) -> Optional[Dict]:
        """Get the most recent active setup"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT * FROM setups 
                WHERE status = 'ACTIVE' 
                ORDER BY created_at DESC 
                LIMIT 1
            ''')
            row = cursor.fetchone()
            if row:
                return dict(row)
            return None
    
    # Option product methods
    def register_option(self, option_data: Dict) -> str:
        """Register new option product"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO option_products 
                (product_id, setup_uuid, option_type, strike_price, expiry_date, 
                 premium_btc, quantity, greeks)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                option_data['product_id'],
                option_data['setup_uuid'],
                option_data['option_type'],
                option_data['strike_price'],
                option_data['expiry_date'],
                option_data['premium_btc'],
                option_data['quantity'],
                json.dumps(option_data.get('greeks', {}))
            ))
            return option_data['product_id']
    
    def get_option(self, product_id: str) -> Optional[Dict]:
        """Get option by product ID"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM option_products WHERE product_id = ?', (product_id,))
            row = cursor.fetchone()
            if row:
                result = dict(row)
                result['greeks'] = json.loads(result['greeks']) if result['greeks'] else {}
                return result
            return None
    
    def get_active_options(self, setup_uuid: str = None) -> List[Dict]:
        """Get all active options"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            if setup_uuid:
                cursor.execute('''
                    SELECT * FROM option_products 
                    WHERE status = 'ACTIVE' AND setup_uuid = ?
                    ORDER BY created_at DESC
                ''', (setup_uuid,))
            else:
                cursor.execute('''
                    SELECT * FROM option_products 
                    WHERE status = 'ACTIVE'
                    ORDER BY created_at DESC
                ''')
            
            results = []
            for row in cursor.fetchall():
                option = dict(row)
                option['greeks'] = json.loads(option['greeks']) if option['greeks'] else {}
                results.append(option)
            return results
    
    # Pool methods
    def get_or_create_pool(self, pool_name: str = "main") -> Dict:
        """Get or create pool"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Try to get existing pool
            cursor.execute('SELECT * FROM pools WHERE name = ?', (pool_name,))
            row = cursor.fetchone()
            
            if row:
                return dict(row)
            
            # Create new pool
            pool_id = f"POOL-{pool_name}"
            cursor.execute('''
                INSERT INTO pools (pool_id, name, total_btc, available_btc)
                VALUES (?, ?, ?, ?)
            ''', (pool_id, pool_name, 1.0, 1.0))
            
            return {
                'pool_id': pool_id,
                'name': pool_name,
                'total_btc': 1.0,
                'available_btc': 1.0,
                'locked_btc': 0
            }
    
    def update_pool(self, pool_name: str, available_btc: float, locked_btc: float = 0):
        """Update pool balances"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE pools 
                SET available_btc = ?, locked_btc = ?, updated_at = CURRENT_TIMESTAMP
                WHERE name = ?
            ''', (available_btc, locked_btc, pool_name))
    
    # Transaction methods
    def record_transaction(self, tx_data: Dict) -> str:
        """Record a transaction"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO transactions 
                (tx_id, setup_uuid, product_id, tx_type, tx_hex, status)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (
                tx_data['tx_id'],
                tx_data['setup_uuid'],
                tx_data.get('product_id'),
                tx_data['tx_type'],
                tx_data.get('tx_hex'),
                tx_data.get('status', 'PENDING')
            ))
            return tx_data['tx_id']
    
    def get_transactions(self, setup_uuid: str = None) -> List[Dict]:
        """Get transactions"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            if setup_uuid:
                cursor.execute('''
                    SELECT * FROM transactions 
                    WHERE setup_uuid = ?
                    ORDER BY created_at DESC
                ''', (setup_uuid,))
            else:
                cursor.execute('''
                    SELECT * FROM transactions 
                    ORDER BY created_at DESC
                ''')
            
            return [dict(row) for row in cursor.fetchall()]
    
    # Migration method
    def migrate_from_json(self):
        """Migrate existing JSON data to database"""
        # Migrate products
        products_file = 'option_data/products.json'
        if os.path.exists(products_file):
            with open(products_file, 'r') as f:
                products = json.load(f)
                for product_id, product_data in products.items():
                    try:
                        product_data['product_id'] = product_id
                        self.register_option(product_data)
                        print(f"✅ Migrated option: {product_id}")
                    except Exception as e:
                        print(f"⚠️ Skipped {product_id}: {e}")
        
        # Migrate pools
        pools_file = 'option_data/pools.json'
        if os.path.exists(pools_file):
            with open(pools_file, 'r') as f:
                pools = json.load(f)
                for pool_name, pool_data in pools.items():
                    try:
                        self.update_pool(
                            pool_name,
                            pool_data.get('available_btc', 1.0),
                            pool_data.get('locked_btc', 0)
                        )
                        print(f"✅ Migrated pool: {pool_name}")
                    except Exception as e:
                        print(f"⚠️ Skipped pool {pool_name}: {e}")