"""
Pytest fixtures for the IntentLayer SDK tests.
"""
import pytest
import json
import os
import binascii
import time
from unittest.mock import MagicMock, patch
from eth_account import Account
from web3 import Web3
from web3.types import TxReceipt
from web3.providers import BaseProvider
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
import requests
import base58

from intentlayer_sdk.utils import sha256_hex, create_envelope
from intentlayer_sdk.models import CallEnvelope

# Constants for testing
TEST_RPC_URL = "https://rpc.example.com"
TEST_PINNER_URL = "https://pin.example.com"
TEST_CONTRACT = "0x1234567890123456789012345678901234567890"
TEST_STAKE_WEI = 1000000000000000  # 0.001 ETH
TEST_PRIV_KEY = "0x0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"

@pytest.fixture
def mock_web3_provider():
    """
    Create a realistic mock of Web3 provider with proper behavior.
    This fixture models actual blockchain interactions.
    """
    # Create provider mock
    provider = MagicMock(spec=BaseProvider)
    
    # Setup ETH object
    eth = MagicMock()
    eth.chain_id = 11155111  # Sepolia testnet ID
    eth.gas_price = MagicMock(return_value=1000000000)  # 1 gwei
    eth.get_transaction_count = MagicMock(return_value=12)
    
    # Configure realistic gas estimation
    def estimate_gas(tx):
        # Base gas + data size factor
        base_gas = 100000
        data_gas = len(str(tx.get('data', ''))) * 16
        return base_gas + data_gas
    
    eth.estimate_gas = MagicMock(side_effect=estimate_gas)
    
    # Configure transaction behavior
    def send_raw_transaction(raw_tx):
        # Generate deterministic but unique tx hash based on the raw tx
        tx_hash = '0x' + sha256_hex(raw_tx)[:40]
        return bytes.fromhex(tx_hash[2:])
    
    eth.send_raw_transaction = MagicMock(side_effect=send_raw_transaction)
    
    # Configure receipt behavior
    def wait_for_receipt(tx_hash, **kwargs):
        # Convert bytes to hex string if needed
        if isinstance(tx_hash, bytes):
            tx_hash_hex = '0x' + tx_hash.hex()
        else:
            tx_hash_hex = tx_hash
            
        # Create a realistic receipt based on tx_hash
        return {
            'transactionHash': tx_hash,
            'blockNumber': 12345,
            'blockHash': bytes.fromhex('abcdef1234567890' * 4),
            'status': 1,
            'gasUsed': 85000,
            'from': '0x1234567890123456789012345678901234567890',
            'to': TEST_CONTRACT,
            'logs': []
        }
    
    eth.wait_for_transaction_receipt = MagicMock(side_effect=wait_for_receipt)
    
    # Setup contract creation
    def contract(address, abi):
        contract_mock = MagicMock()
        
        # Create recordIntent function mock
        record_intent_fn = MagicMock()
        record_intent_fn.estimate_gas = MagicMock(return_value=150000)
        
        def build_tx(tx_params):
            # Combine function params with tx params
            return {
                **tx_params,
                'to': address,
                'data': '0x123456789abcdef'  # Mock contract call data
            }
        
        record_intent_fn.build_transaction = MagicMock(side_effect=build_tx)
        
        # Handle function calls with arguments
        # This will capture recordIntent(envelope_hash, cid_bytes) calls
        def record_intent_factory(*args, **kwargs):
            # Return the same mock regardless of args
            return record_intent_fn
            
        # Setup contract functions
        functions = MagicMock()
        functions.recordIntent = MagicMock(side_effect=record_intent_factory)
        contract_mock.functions = functions
        
        return contract_mock
    
    eth.contract = MagicMock(side_effect=contract)
    
    # Attach eth to provider
    provider.eth = eth
    
    return provider

@pytest.fixture
def mock_w3(mock_web3_provider):
    """Create a mock Web3 instance with realistic provider"""
    mock = MagicMock(spec=Web3)
    mock.eth = mock_web3_provider.eth
    return mock

@pytest.fixture
def mock_account():
    """Create a deterministic test account"""
    return Account.from_key(TEST_PRIV_KEY)

@pytest.fixture
def mock_session():
    """Create a mock HTTP session for testing API calls"""
    session = MagicMock(spec=requests.Session)
    
    # Configure post behavior  
    def mock_post(url, **kwargs):
        response = MagicMock(spec=requests.Response)
        
        if url.endswith('/pin'):
            # Simulate IPFS pinning
            payload = kwargs.get('json', {})
            # Generate deterministic CID based on the payload content
            cid_base = sha256_hex(str(payload))[:16]
            cid = f"QmTest{cid_base}"
            
            response.status_code = 200
            response.headers = {'Content-Type': 'application/json'}
            response.json = MagicMock(return_value={"cid": cid})
            # Add a raise_for_status method that does nothing (success)
            response.raise_for_status = MagicMock(return_value=None)
        else:
            # Default failure for unknown endpoints
            response.status_code = 404
            response.raise_for_status = MagicMock(side_effect=requests.HTTPError("Not found"))
            
        return response
    
    session.post = MagicMock(side_effect=mock_post)
    
    # Configure realistic retry and mounting behavior
    session.mount = MagicMock()
    
    return session

@pytest.fixture
def test_envelope():
    """Create a realistic test envelope with valid signature"""
    # Generate deterministic private key for testing
    private_key = Ed25519PrivateKey.generate()
    
    # Create actual envelope
    envelope = create_envelope(
        prompt="Example prompt content",
        model_id="gpt-4o@2025-03-12",
        tool_id="https://api.example.com/chat",
        did="did:key:z6MkpzExampleTestDid123456789abcdefgh",
        private_key=private_key,
        stake_wei="1000000000000000",
        timestamp_ms=1679529600000
    )
    
    # Return as dictionary for backward compatibility
    return envelope.model_dump()

@pytest.fixture
def test_payload(test_envelope):
    """Create a realistic test payload with valid envelope"""
    return {
        "envelope": test_envelope,
        "prompt": "Example prompt content",
        "metadata": {
            "user_id": "test123",
            "session_id": "abcdef"
        }
    }

@pytest.fixture
def test_private_key():
    """Generate a deterministic Ed25519 private key for testing"""
    return Ed25519PrivateKey.generate()

@pytest.fixture
def mock_pinner(requests_mock):
    """Mock the IPFS pinner service with realistic behavior"""
    def response_callback(request, context):
        # Extract payload from request
        payload = request.json()
        
        # Set proper content type
        context.headers['Content-Type'] = 'application/json'
        
        # Validate payload has required fields
        if not isinstance(payload, dict) or 'envelope' not in payload:
            context.status_code = 400
            return {"error": "Invalid payload format"}
            
        # Generate deterministic CID based on payload content
        content_hash = sha256_hex(str(payload))[:16]
        cid = f"QmExample{content_hash}"
        
        # Return successful response
        return {"cid": cid}
    
    # Register the mock endpoint with the callback
    pinner_route = requests_mock.post(
        "https://pin.example.com/pin",
        json=response_callback,
        status_code=200
    )
    
    return pinner_route