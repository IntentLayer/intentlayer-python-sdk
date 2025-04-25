"""
Data models for the IntentLayer SDK.
"""
from typing import Dict, Any, Optional, List
from pydantic import BaseModel, Field

class CallEnvelope(BaseModel):
    """CallEnvelope-v0 schema representation"""
    did: str
    model_id: str
    prompt_sha256: str
    tool_id: str
    timestamp_ms: int
    stake_wei: str
    sig_ed25519: str
    metadata: Optional[Dict[str, Any]] = None

class TxReceipt(BaseModel):
    """Transaction receipt from the blockchain"""
    tx_hash: str = Field(..., alias="transactionHash")
    block_number: int = Field(..., alias="blockNumber")
    block_hash: str = Field(..., alias="blockHash")
    status: int
    gas_used: int = Field(..., alias="gasUsed")
    from_address: str = Field(..., alias="from")
    to_address: Optional[str] = Field(None, alias="to")
    logs: List[Dict[str, Any]]
    
    class Config:
        populate_by_name = True