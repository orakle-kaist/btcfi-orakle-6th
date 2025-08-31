from typing import List, Optional

from pydantic import BaseModel


class BitVMXProverSignaturesDTO(BaseModel):
    hash_result_signature: Optional[str] = None  # Added for hash_result_tx signing
    trigger_protocol_signature: str
    search_hash_signatures: Optional[List[str]] = None  # Added for search hash transactions
    search_choice_signatures: List[str]
    trace_signature: Optional[str] = None  # Added for trace transactions
    trigger_execution_challenge_signature: str
    read_search_hash_signatures: Optional[List[str]] = None  # Added for read search hash transactions
    read_search_choice_signatures: List[str]
    read_trace_signature: Optional[str] = None  # Added for read trace transactions
