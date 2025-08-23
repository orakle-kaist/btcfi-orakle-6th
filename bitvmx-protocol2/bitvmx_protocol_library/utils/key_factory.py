"""
Key Factory - Centralized key creation to avoid inconsistencies
"""
from bitcoinutils.keys import PublicKey, PrivateKey
from typing import Optional

class KeyFactory:
    """Factory for consistent key creation across the codebase"""
    
    @staticmethod
    def create_public_key(key_data: str) -> Optional[PublicKey]:
        """
        Create PublicKey from hex string
        
        Args:
            key_data: Hex string of public key
            
        Returns:
            PublicKey object or None if invalid
        """
        try:
            # Always use from_hex for consistency
            return PublicKey.from_hex(key_data)
        except Exception as e:
            print(f"Error creating public key: {e}")
            return None
    
    @staticmethod
    def create_private_key(key_data: str) -> Optional[PrivateKey]:
        """
        Create PrivateKey from hex string
        
        Args:
            key_data: Hex string of private key
            
        Returns:
            PrivateKey object or None if invalid
        """
        try:
            return PrivateKey(secret_exponent=int(key_data, 16))
        except Exception as e:
            print(f"Error creating private key: {e}")
            return None
    
    @staticmethod
    def validate_public_key_hex(key_hex: str) -> bool:
        """
        Validate if hex string is valid public key
        
        Args:
            key_hex: Hex string to validate
            
        Returns:
            True if valid public key format
        """
        # Compressed: 33 bytes (66 hex chars)
        # Uncompressed: 65 bytes (130 hex chars)
        return len(key_hex) in [66, 130] and all(c in '0123456789abcdefABCDEF' for c in key_hex)