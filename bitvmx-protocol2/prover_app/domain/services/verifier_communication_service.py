"""
Verifier Communication Service
Handles all communication with verifier backend
"""
import httpx
from typing import Dict, List
from bitcoinutils.keys import PublicKey

class VerifierCommunicationService:
    """Service to handle verifier communication"""
    
    def __init__(self, verifier_urls: List[str]):
        self.verifier_urls = verifier_urls
        self.client = httpx.AsyncClient(timeout=60.0)
    
    async def get_public_keys(self, setup_params: Dict) -> Dict[str, str]:
        """
        Get public keys from verifiers
        
        Args:
            setup_params: Setup configuration
            
        Returns:
            Dict of verifier_id -> public_key
        """
        verifier_keys = {}
        
        for verifier_url in self.verifier_urls:
            try:
                response = await self.client.post(
                    f"{verifier_url}/api/v1/public_keys",
                    json=self._prepare_request_data(setup_params)
                )
                
                if response.status_code == 200:
                    data = response.json()
                    verifier_keys[data['verifier_id']] = data['public_key']
                else:
                    print(f"⚠️ Verifier {verifier_url} returned {response.status_code}")
                    
            except Exception as e:
                print(f"❌ Error communicating with verifier {verifier_url}: {e}")
        
        return verifier_keys
    
    def _prepare_request_data(self, setup_params: Dict) -> Dict:
        """
        Prepare request data for verifier
        
        This encapsulates the data preparation logic
        """
        return {
            "max_amount_of_steps": setup_params["max_amount_of_steps"],
            "amount_of_bits_wrong_step_search": setup_params["amount_of_bits_wrong_step_search"],
            "signature_public_key": setup_params["prover_signature_public_key"],
            "amount_of_input_words": setup_params["amount_of_input_words"]
        }
    
    async def close(self):
        """Clean up resources"""
        await self.client.aclose()