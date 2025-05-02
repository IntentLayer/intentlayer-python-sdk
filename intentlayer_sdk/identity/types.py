"""
Data types for the identity module.
"""
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from intentlayer_sdk.signer import Signer


@dataclass
class Identity:
    """
    Represents a DID identity with associated signer.
    
    Attributes:
        did: Decentralized Identifier string
        signer: Signer implementation for this identity
        created_at: When this identity was created
        org_id: Optional organization ID this identity belongs to
        agent_label: Optional label for identifying this identity
    """
    did: str
    signer: Signer
    created_at: datetime
    org_id: Optional[str] = None
    agent_label: Optional[str] = None