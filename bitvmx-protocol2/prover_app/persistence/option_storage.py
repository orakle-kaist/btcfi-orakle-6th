"""
옵션 상품 및 구매 정보 저장소
"""

import json
import os
from typing import Optional, List, Dict, Any
from datetime import datetime

from prover_app.domain.models.option_product import (
    OptionProduct, OptionPurchase, OptionPool, OptionStatus
)


class OptionStorage:
    """옵션 데이터 파일 기반 저장소"""
    
    def __init__(self, base_path: str = "./option_data"):
        self.base_path = base_path
        self.products_file = os.path.join(base_path, "products.json")
        self.purchases_file = os.path.join(base_path, "purchases.json")
        self.pools_file = os.path.join(base_path, "pools.json")
        
        # 디렉토리 생성
        os.makedirs(base_path, exist_ok=True)
        
        # 파일 초기화
        for file_path in [self.products_file, self.purchases_file, self.pools_file]:
            if not os.path.exists(file_path):
                with open(file_path, 'w') as f:
                    json.dump({}, f)
    
    async def save_product(self, product: OptionProduct) -> bool:
        """옵션 상품 저장"""
        try:
            # 기존 데이터 로드
            products = await self._load_json(self.products_file)
            
            # 새 상품 추가
            products[product.product_id] = product.to_dict()
            
            # 저장
            await self._save_json(self.products_file, products)
            return True
        except Exception as e:
            print(f"Error saving product: {e}")
            return False
    
    async def get_product(self, product_id: str) -> Optional[OptionProduct]:
        """옵션 상품 조회"""
        products = await self._load_json(self.products_file)
        if product_id in products:
            data = products[product_id]
            # datetime 문자열을 객체로 변환
            data['expiry_date'] = datetime.fromisoformat(data['expiry_date'])
            data['created_at'] = datetime.fromisoformat(data['created_at'])
            if data.get('settlement', {}).get('date'):
                data['settlement_date'] = datetime.fromisoformat(data['settlement']['date'])
            return OptionProduct(**data)
        return None
    
    async def get_active_products(self, setup_uuid: Optional[str] = None) -> List[OptionProduct]:
        """활성 옵션 상품 목록 조회"""
        products = await self._load_json(self.products_file)
        active_products = []
        
        for product_data in products.values():
            if product_data['status'] == OptionStatus.ACTIVE.value:
                if setup_uuid and product_data['setup_uuid'] != setup_uuid:
                    continue
                    
                # datetime 변환
                product_data['expiry_date'] = datetime.fromisoformat(product_data['expiry_date'])
                product_data['created_at'] = datetime.fromisoformat(product_data['created_at'])
                
                product = OptionProduct(**product_data)
                active_products.append(product)
        
        return active_products
    
    async def save_purchase(self, purchase: OptionPurchase) -> bool:
        """옵션 구매 정보 저장"""
        try:
            purchases = await self._load_json(self.purchases_file)
            purchases[purchase.purchase_id] = purchase.to_dict()
            await self._save_json(self.purchases_file, purchases)
            return True
        except Exception as e:
            print(f"Error saving purchase: {e}")
            return False
    
    async def get_purchase(self, purchase_id: str) -> Optional[OptionPurchase]:
        """옵션 구매 정보 조회"""
        purchases = await self._load_json(self.purchases_file)
        if purchase_id in purchases:
            data = purchases[purchase_id]
            data['purchase_date'] = datetime.fromisoformat(data['purchase_date'])
            return OptionPurchase(**data)
        return None
    
    async def get_purchases_by_buyer(self, buyer_address: str) -> List[OptionPurchase]:
        """구매자별 옵션 구매 목록"""
        purchases = await self._load_json(self.purchases_file)
        buyer_purchases = []
        
        for purchase_data in purchases.values():
            if purchase_data['buyer_address'] == buyer_address:
                purchase_data['purchase_date'] = datetime.fromisoformat(purchase_data['purchase_date'])
                purchase = OptionPurchase(**purchase_data)
                buyer_purchases.append(purchase)
        
        return buyer_purchases
    
    async def save_pool(self, pool: OptionPool) -> bool:
        """옵션 풀 정보 저장"""
        try:
            pools = await self._load_json(self.pools_file)
            pools[pool.pool_id] = pool.to_dict()
            await self._save_json(self.pools_file, pools)
            return True
        except Exception as e:
            print(f"Error saving pool: {e}")
            return False
    
    async def get_pool(self, pool_id: str) -> Optional[OptionPool]:
        """옵션 풀 정보 조회"""
        pools = await self._load_json(self.pools_file)
        if pool_id in pools:
            data = pools[pool_id]
            data['created_at'] = datetime.fromisoformat(data['created_at'])
            data['last_updated'] = datetime.fromisoformat(data['last_updated'])
            return OptionPool(**data)
        return None
    
    async def get_pool_by_setup(self, setup_uuid: str) -> Optional[OptionPool]:
        """Setup UUID로 풀 조회"""
        pools = await self._load_json(self.pools_file)
        for pool_data in pools.values():
            if pool_data['setup_uuid'] == setup_uuid:
                pool_data['created_at'] = datetime.fromisoformat(pool_data['created_at'])
                pool_data['last_updated'] = datetime.fromisoformat(pool_data['last_updated'])
                return OptionPool(**pool_data)
        return None
    
    async def update_product_status(self, product_id: str, status: OptionStatus, 
                                   settlement_price: Optional[float] = None,
                                   settlement_txid: Optional[str] = None) -> bool:
        """옵션 상품 상태 업데이트"""
        product = await self.get_product(product_id)
        if not product:
            return False
        
        product.status = status
        if settlement_price:
            product.settlement_price = settlement_price
        if settlement_txid:
            product.settlement_txid = settlement_txid
        if status == OptionStatus.SETTLED:
            product.settlement_date = datetime.now()
        
        return await self.save_product(product)
    
    async def _load_json(self, file_path: str) -> Dict[str, Any]:
        """JSON 파일 로드"""
        try:
            with open(file_path, 'r') as f:
                content = f.read()
                return json.loads(content) if content else {}
        except FileNotFoundError:
            return {}
        except json.JSONDecodeError:
            return {}
    
    async def _save_json(self, file_path: str, data: Dict[str, Any]):
        """JSON 파일 저장"""
        with open(file_path, 'w') as f:
            f.write(json.dumps(data, indent=2, default=str))