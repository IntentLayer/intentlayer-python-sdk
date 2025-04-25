"""
Utility functions for creating test clients with backward compatibility.
"""
from typing import Optional
from intentlayer_sdk.client import IntentClient
from intentlayer_sdk.signer.local import LocalSigner

# Test constants used throughout tests
TEST_RPC_URL = "https://rpc.example.com"
TEST_PINNER_URL = "https://pin.example.com"
TEST_STAKE_WEI = 1000000000000000  # 0.001 ETH
TEST_PRIV_KEY = "0x0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
TEST_CONTRACT = "0x1234567890123456789012345678901234567890"
TEST_DID_CONTRACT = "0x2345678901234567890123456789012345678901"

def create_test_client(
    rpc_url: str = TEST_RPC_URL,
    pinner_url: str = TEST_PINNER_URL,
    priv_key: Optional[str] = TEST_PRIV_KEY,
    signer=None,
    min_stake_wei: Optional[int] = TEST_STAKE_WEI,
    recorder_address: Optional[str] = TEST_CONTRACT,
    did_registry_address: Optional[str] = TEST_DID_CONTRACT,
    expected_chain_id: Optional[int] = None,
    retry_count: int = 3,
    timeout: int = 30,
    **kwargs
) -> IntentClient:
    """
    Create a client instance for testing with consistent defaults.
    
    This function helps ensure backward compatibility with test files
    while adapting to the new client constructor signature.
    
    Args:
        rpc_url: RPC URL for the blockchain node
        pinner_url: IPFS pinner service URL
        priv_key: Private key string (deprecated)
        signer: Signer instance
        min_stake_wei: Manual override for minimum stake
        recorder_address: IntentRecorder contract address
        did_registry_address: DIDRegistry contract address
        expected_chain_id: Chain ID for validation
        retry_count: Number of HTTP retries
        timeout: Timeout in seconds
        **kwargs: Additional parameters
        
    Returns:
        Configured IntentClient instance
    """
    # Handle signer/priv_key priority
    if signer is None:
        if priv_key:
            signer = LocalSigner(priv_key)
        elif priv_key is None and kwargs.get('__allow_missing_signer', False) is not True:
            raise ValueError("signer must be provided")
    
    # Create the client
    client = IntentClient(
        rpc_url=rpc_url,
        pinner_url=pinner_url,
        signer=signer,
        recorder_address=recorder_address,
        did_registry_address=did_registry_address,
        min_stake_wei=min_stake_wei,
        expected_chain_id=expected_chain_id,
        retry_count=retry_count,
        timeout=timeout,
        **kwargs
    )
    
    return client