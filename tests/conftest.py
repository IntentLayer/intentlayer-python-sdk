"""
Pytest fixtures for the IntentLayer SDK tests.
"""
import pytest
import json
from unittest.mock import MagicMock
from eth_account import Account
from web3 import Web3
from web3.types import TxReceipt

@pytest.fixture
def mock_w3():
    """Create a mock Web3 instance"""
    mock = MagicMock()
    mock.eth.gas_price = 1000000000  # 1 gwei
    mock.eth.get_transaction_count.return_value = 0
    
    # Create a mock receipt
    receipt = {
        'transactionHash': '0x123456789abcdef',
        'blockNumber': 12345,
        'blockHash': '0xabcdef1234567890',
        'status': 1,
        'gasUsed': 100000,
        'from': '0x1234567890123456789012345678901234567890',
        'to': '0x0987654321098765432109876543210987654321',
        'logs': []
    }
    mock.eth.wait_for_transaction_receipt.return_value = receipt
    
    return mock

@pytest.fixture
def mock_account():
    """Create a test account"""
    return Account.create()

@pytest.fixture
def test_envelope():
    """Create a test envelope"""
    return {
        "did": "did:key:z6MkpzExampleTestDid123456789abcdefgh",
        "model_id": "gpt-4o@2025-03-12",
        "prompt_sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        "tool_id": "https://api.example.com/chat",
        "timestamp_ms": 1679529600000,
        "stake_wei": "1000000000000000",
        "sig_ed25519": "ABCDEFG123456789_-exampleSignatureWhichIsLongEnoughToMatchThePatternWithCorrectBase64UrlEncoding"
    }

@pytest.fixture
def test_payload():
    """Create a test payload"""
    return {
        "envelope": {
            "did": "did:key:z6MkpzExampleTestDid123456789abcdefgh",
            "model_id": "gpt-4o@2025-03-12",
            "prompt_sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
            "tool_id": "https://api.example.com/chat",
            "timestamp_ms": 1679529600000,
            "stake_wei": "1000000000000000",
            "sig_ed25519": "ABCDEFG123456789_-exampleSignatureWhichIsLongEnoughToMatchThePatternWithCorrectBase64UrlEncoding"
        },
        "prompt": "Example prompt content",
        "metadata": {
            "user_id": "test123",
            "session_id": "abcdef"
        }
    }

@pytest.fixture
def mock_pinner(requests_mock):
    """Mock the IPFS pinner service"""
    pinner_route = requests_mock.post(
        "https://pin.example.com/pin",
        json={"cid": "QmExample123456789"},
        status_code=200
    )
    return pinner_route