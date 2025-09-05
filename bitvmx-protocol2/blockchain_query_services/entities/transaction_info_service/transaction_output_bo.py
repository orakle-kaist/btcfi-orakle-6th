from typing import Optional
from pydantic import BaseModel


class TransactionOutputBO(BaseModel):
    address: str
    index: int
    value: int
    scriptpubkey_hex: Optional[str] = None

    @staticmethod
    def from_vout(vout: dict, index: int) -> "TransactionOutputBO":
        # Handle OP_RETURN and other outputs without addresses
        try:
            address = vout.get("scriptpubkey_address", "")
            if not address:
                if vout.get("scriptpubkey_type") == "op_return":
                    address = "OP_RETURN"
                else:
                    address = "UNKNOWN"
            
            # Get the scriptpubkey hex for signature verification
            scriptpubkey_hex = vout.get("scriptpubkey")
            
            return TransactionOutputBO(
                address=address, 
                index=index, 
                value=vout.get("value", 0),
                scriptpubkey_hex=scriptpubkey_hex
            )
        except Exception as e:
            print(f"Error processing vout at index {index}: {vout}")
            print(f"Error: {e}")
            raise
