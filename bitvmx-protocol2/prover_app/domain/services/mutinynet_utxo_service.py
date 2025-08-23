"""
Mutinynet UTXO Service
Automatically fetches available UTXOs from Mutinynet for a given address
"""
import requests
from typing import List, Dict, Optional
from dataclasses import dataclass

@dataclass
class UTXO:
    txid: str
    vout: int
    value: int  # satoshis
    confirmations: int
    scriptPubKey: str

class MutinynetUTXOService:
    """Service to fetch and manage UTXOs from Mutinynet"""
    
    MUTINYNET_API = "https://mutinynet.com/api"
    
    def __init__(self):
        self.session = requests.Session()
    
    def get_utxos_for_address(self, address: str) -> List[UTXO]:
        """
        Fetch all UTXOs for a given address from Mutinynet
        
        Args:
            address: Bitcoin testnet address
            
        Returns:
            List of UTXO objects
        """
        try:
            # Get UTXOs from Mutinynet API
            response = self.session.get(f"{self.MUTINYNET_API}/address/{address}/utxo")
            response.raise_for_status()
            
            utxos = []
            for utxo_data in response.json():
                utxo = UTXO(
                    txid=utxo_data['txid'],
                    vout=utxo_data['vout'],
                    value=utxo_data['value'],
                    confirmations=utxo_data.get('status', {}).get('block_height', 0),
                    scriptPubKey=utxo_data.get('scriptpubkey', '')
                )
                utxos.append(utxo)
            
            return sorted(utxos, key=lambda x: x.value, reverse=True)  # Largest first
            
        except Exception as e:
            print(f"Error fetching UTXOs: {e}")
            return []
    
    def find_suitable_utxo(self, address: str, min_value: int = 10000) -> Optional[UTXO]:
        """
        Find a suitable UTXO for funding
        
        Args:
            address: Bitcoin testnet address
            min_value: Minimum value in satoshis (default 10000)
            
        Returns:
            Best UTXO for funding or None
        """
        utxos = self.get_utxos_for_address(address)
        
        # Filter confirmed UTXOs with sufficient value
        suitable_utxos = [
            utxo for utxo in utxos 
            if utxo.value >= min_value and utxo.confirmations > 0
        ]
        
        if suitable_utxos:
            # Return the smallest suitable UTXO to avoid wasting funds
            return min(suitable_utxos, key=lambda x: x.value)
        
        return None
    
    def get_funding_tx_info(self, address: str) -> Optional[Dict[str, any]]:
        """
        Get funding transaction info for Setup creation
        
        Returns dict with funding_tx_id and funding_index
        """
        utxo = self.find_suitable_utxo(address)
        
        if utxo:
            return {
                "funding_tx_id": utxo.txid,
                "funding_index": utxo.vout,
                "funding_value": utxo.value
            }
        
        return None