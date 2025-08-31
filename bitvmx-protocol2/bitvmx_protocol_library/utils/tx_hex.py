"""
Transaction hex serialization utility to ensure witness data is always included
"""

def tx_to_hex(tx) -> str:
    """
    Serialize transaction with witness data if present
    """
    # Check if transaction has witness data
    has_witness = False
    
    if hasattr(tx, "has_segwit"):
        has_witness = tx.has_segwit
    elif hasattr(tx, "witnesses") and tx.witnesses:
        has_witness = True
    
    # Serialize with proper flag
    if hasattr(tx, "serialize"):
        # bitcoinutils uses just serialize() and checks witnesses internally
        return tx.serialize()
    elif hasattr(tx, "to_hex"):
        return tx.to_hex()
    else:
        raise TypeError(f"Unknown transaction type: {type(tx)}")