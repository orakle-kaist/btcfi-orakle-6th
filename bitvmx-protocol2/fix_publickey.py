#!/usr/bin/env python3
"""
Fix PublicKey.to_x_only_hex() to always return string
"""

def patch_publickey():
    from bitcoinutils.keys import PublicKey
    
    # Save original method
    original_to_x_only_hex = PublicKey.to_x_only_hex
    
    # Create wrapper that ensures string return
    def safe_to_x_only_hex(self):
        result = original_to_x_only_hex(self)
        if isinstance(result, bytes):
            return result.hex()
        return result
    
    # Replace method
    PublicKey.to_x_only_hex = safe_to_x_only_hex
    print("[PATCH] PublicKey.to_x_only_hex now always returns string")

if __name__ == "__main__":
    patch_publickey()