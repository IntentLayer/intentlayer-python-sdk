"""
Tests for the verify CLI command.
"""
import json
import pytest
from unittest.mock import MagicMock, patch
from typing import Dict, Any
from web3 import Web3

from intent_cli.verify import (
    canonicalize_envelope,
    _compare_envelopes as compare_envelopes,
    fetch_ipfs_json,
    verify_hash_match,
    should_use_color,
)

# Sample data for tests
SAMPLE_ENVELOPE = {
    "did": "did:example:123",
    "model_id": "test-model",
    "prompt_sha256": "1234567890abcdef",
    "tool_id": "test-tool",
    "timestamp_ms": 1672531200000,
    "stake_wei": "1000000000000000000",
    "sig_ed25519": "sample-signature",
    "metadata": {
        "extra": "data"
    }
}

SAMPLE_PAYLOAD = {
    "prompt": "Test prompt",
    "envelope": SAMPLE_ENVELOPE,
    "metadata": {
        "source": "test"
    }
}

def test_canonicalize_envelope():
    # Test that metadata is removed and JSON is canonical
    envelope = SAMPLE_ENVELOPE.copy()
    canonical = canonicalize_envelope(envelope)
    
    # Parse back to verify
    parsed = json.loads(canonical)
    
    # Check metadata is gone
    assert "metadata" not in parsed
    
    # Check other fields remain
    assert parsed["did"] == "did:example:123"
    assert parsed["model_id"] == "test-model"
    
    # Verify canonical form
    canonical2 = canonicalize_envelope(parsed)
    assert canonical == canonical2

def test_compare_envelopes_match():
    # Test with matching envelopes
    envelope1 = SAMPLE_ENVELOPE.copy()
    envelope2 = SAMPLE_ENVELOPE.copy()
    
    # Add different metadata (should be ignored)
    envelope1["metadata"] = {"one": 1}
    envelope2["metadata"] = {"two": 2}
    
    match, diff = _compare_envelopes(envelope1, envelope2)
    
    assert match is True
    assert len(diff) == 0

def test_compare_envelopes_mismatch():
    # Test with non-matching envelopes
    envelope1 = SAMPLE_ENVELOPE.copy()
    envelope2 = SAMPLE_ENVELOPE.copy()
    envelope2["model_id"] = "different-model"
    
    match, diff = _compare_envelopes(envelope1, envelope2)
    
    assert match is False
    assert len(diff) > 0

@pytest.mark.parametrize("no_color", [True, False])
def test_compare_envelopes_color_option(no_color):
    # Test color option in diff output
    envelope1 = SAMPLE_ENVELOPE.copy()
    envelope2 = SAMPLE_ENVELOPE.copy()
    envelope2["model_id"] = "different-model"
    
    match, diff = _compare_envelopes(envelope1, envelope2, no_color=no_color)
    
    # Check if color codes are present based on no_color flag
    has_color_codes = any('\033[' in line for line in diff)
    assert has_color_codes != no_color

@patch('requests.get')
def test_fetch_ipfs_json(mock_get):
    # Mock the response
    mock_response = MagicMock()
    mock_response.json.return_value = SAMPLE_PAYLOAD
    mock_get.return_value = mock_response
    
    result = fetch_ipfs_json("test-cid", "https://w3s.link/")
    
    # Verify the URL construction
    mock_get.assert_called_once_with('https://w3s.link/ipfs/test-cid', timeout=10)
    
    # Verify the result
    assert result == SAMPLE_PAYLOAD

@patch('requests.get')
def test_fetch_ipfs_json_error(mock_get):
    # Test error handling
    mock_get.side_effect = Exception("Connection error")
    
    with pytest.raises(ConnectionError):
        fetch_ipfs_json("test-cid", "https://w3s.link/")

def test_verify_hash_match():
    # Test hash verification
    envelope = SAMPLE_ENVELOPE.copy()
    
    # Create canonical JSON
    canonical = canonicalize_envelope(envelope).encode('utf-8')
    
    # Calculate hash
    envelope_hash = Web3.keccak(canonical).hex()
    
    # Test match
    assert verify_hash_match(envelope_hash, envelope)
    
    # Test non-match
    modified_envelope = envelope.copy()
    modified_envelope["model_id"] = "different-model"
    assert not verify_hash_match(envelope_hash, modified_envelope)

@patch('sys.stdout.isatty')
def test_should_use_color(mock_isatty):
    # Test TTY check
    mock_isatty.return_value = True
    assert should_use_color() is True
    
    mock_isatty.return_value = False
    assert should_use_color() is False

# Golden diff test
def test_compare_envelopes_diff_content():
    # Create two envelopes with one different field
    envelope1 = SAMPLE_ENVELOPE.copy()
    envelope2 = SAMPLE_ENVELOPE.copy()
    envelope2["model_id"] = "different-model"
    
    match, diff = compare_envelopes(envelope1, envelope2, no_color=True)
    
    assert match is False
    assert any("model_id" in line for line in diff)
    assert any("-\"model_id\":\"test-model\"" in line or "+\"model_id\":\"different-model\"" in line for line in diff)

# Chain-agnostic test
@pytest.mark.parametrize('chain_id', [300, 324])
@patch('intent_cli.verify.fetch_ipfs_json')
@patch('intent_cli.verify.setup_web3_for_network')
@patch('web3.Web3.HTTPProvider')
@patch('web3.Web3.eth.get_transaction_receipt')
@patch('web3.Web3.eth.contract')
@patch('typer.echo')
@patch('typer.Exit')
@pytest.mark.xfail(reason="Test stub not fully implemented")
def test_verify_tx_chain_agnostic(
    mock_exit,
    mock_echo,
    mock_contract,
    mock_get_receipt,
    mock_http_provider,
    mock_setup_web3,
    mock_fetch_ipfs,
    chain_id
):
    # Test stub - marked as xfail until implemented
    pass