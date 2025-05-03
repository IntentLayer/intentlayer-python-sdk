#!/usr/bin/env python3
"""
Verify command for IntentLayer CLI.

This module implements the 'verify' command which verifies that the hash of the JSON 
envelope stored on IPFS matches the hash recorded on-chain.
"""
import sys
import json
import difflib
import logging
import urllib.parse
from typing import Dict, Any, Optional, Tuple, List

import typer
import requests
from web3 import Web3
from web3.types import TxReceipt

from intentlayer_sdk.config import NetworkConfig

# Create the app
app = typer.Typer(
    help="Verify an intent transaction",
    epilog="""
    Exit codes:
      0: Hashes match (PASS)
      1: Mismatch (FAIL)
      2: Network/RPC error or gateway unreachable
      3: Unexpected error
      4: Invalid command arguments
    """
)

# ABI for IntentRecorder contract events
INTENT_RECORDED_EVENT_ABI = {
    "anonymous": False,
    "inputs": [
        {"indexed": True, "internalType": "bytes32", "name": "envelopeHash", "type": "bytes32"},
        {"indexed": False, "internalType": "string", "name": "cid", "type": "string"},
        {"indexed": True, "internalType": "address", "name": "sender", "type": "address"},
        {"indexed": False, "internalType": "uint256", "name": "stakeWei", "type": "uint256"}
    ],
    "name": "IntentRecorded",
    "type": "event"
}

# Setup logger
logger = logging.getLogger("intent_cli.verify")

# Lazy singleton for the event signature
_EVENT_SIGNATURE = None

def get_intent_recorded_event_signature():
    """Get the IntentRecorded event signature hex, cached for performance."""
    global _EVENT_SIGNATURE
    if _EVENT_SIGNATURE is None:
        _EVENT_SIGNATURE = Web3.keccak(text="IntentRecorded(bytes32,string,address,uint256)").hex()
    return _EVENT_SIGNATURE

def setup_web3_for_network(
    network_name: Optional[str] = None, 
    chain_id: Optional[int] = None, 
    tx_hash: Optional[str] = None
) -> Tuple[Web3, str, Optional[Dict[str, Any]]]:
    """
    Setup Web3 for a specific network based on network name, chain ID, or transaction hash.
    
    Args:
        network_name: Specific network name to use (optional)
        chain_id: Chain ID to match (optional)
        tx_hash: Transaction hash to find on a network (optional)
        
    Returns:
        Tuple of (Web3 instance, network_name, receipt or None)
        
    Raises:
        ValueError: If no matching network configuration is found
    """
    # Get all available networks
    networks = NetworkConfig.get_all_networks()
    
    # Case 1: Network name provided
    if network_name:
        if network_name not in networks:
            raise ValueError(f"Network '{network_name}' not found in configuration")
        
        rpc_url = NetworkConfig.get_rpc_url(network_name)
        w3 = Web3(Web3.HTTPProvider(rpc_url))
        return w3, network_name, None
    
    # Case 2: Chain ID provided
    elif chain_id is not None:
        for name, config in networks.items():
            if config["chainId"] == chain_id:
                rpc_url = NetworkConfig.get_rpc_url(name)
                w3 = Web3(Web3.HTTPProvider(rpc_url))
                return w3, name, None
        
        raise ValueError(f"No network configuration found for chain ID {chain_id}")
    
    # Case 3: Transaction hash provided - try all networks
    elif tx_hash is not None:
        errors = []
        for name, config in networks.items():
            try:
                rpc_url = NetworkConfig.get_rpc_url(name)
                w3 = Web3(Web3.HTTPProvider(rpc_url))
                
                # Try to get the transaction receipt
                receipt = w3.eth.get_transaction_receipt(tx_hash)
                # If we get here, we found the transaction
                logger.debug(f"Found transaction on network: {name}")
                return w3, name, receipt
            except Exception as e:
                errors.append(f"{name}: {str(e)}")
                continue
        
        # If we get here, no network had the transaction
        err_msg = "\n".join(errors)
        raise ValueError(f"Transaction {tx_hash} not found on any configured network:\n{err_msg}")
    
    # Case 4: Just find any working network
    else:
        errors = []
        for name, config in networks.items():
            try:
                rpc_url = NetworkConfig.get_rpc_url(name)
                w3 = Web3(Web3.HTTPProvider(rpc_url))
                
                # Check if we can connect
                _ = w3.eth.chain_id
                return w3, name, None
            except Exception as e:
                errors.append(f"{name}: {str(e)}")
                continue
        
        # If we get here, none of the networks worked
        err_msg = "\n".join(errors)
        raise ValueError(f"Could not connect to any configured network:\n{err_msg}")

def fetch_ipfs_json(cid: str, gateway_url: str, token: Optional[str] = None) -> Dict[str, Any]:
    """
    Fetch JSON payload from IPFS.
    
    Args:
        cid: IPFS CID
        gateway_url: IPFS gateway URL
        token: Optional authentication token
        
    Returns:
        Parsed JSON payload
        
    Raises:
        ValueError: If CID is invalid or payload is not valid JSON
        ConnectionError: If gateway is unreachable
    """
    # Parse the gateway URL properly
    parsed = urllib.parse.urlparse(gateway_url)
    path = parsed.path.rstrip('/')
    if not path.endswith('/ipfs'):
        path += '/ipfs'
    
    # Construct the URL - strip any leading slashes from CID to avoid double slashes
    url = f"{parsed.scheme}://{parsed.netloc}{path}/{cid.lstrip('/')}"
    
    # Prepare headers
    headers = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        raise ConnectionError(f"Failed to fetch from IPFS gateway: {e}")
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON payload from IPFS: {e}")

def canonicalize_envelope(envelope: Dict[str, Any]) -> str:
    """
    Convert envelope to canonical JSON representation.
    
    Args:
        envelope: Envelope dictionary
        
    Returns:
        Canonical JSON string
    """
    # Create a copy without metadata (if present)
    env_copy = envelope.copy()
    if "metadata" in env_copy:
        del env_copy["metadata"]
    
    # Sort keys and remove whitespace
    return json.dumps(env_copy, sort_keys=True, separators=(',', ':'))

# UNUSED until v2 contracts emit full envelope
# This function will be used in a future version when the contract is upgraded 
# to emit the full envelope structure instead of just the hash.
# It's marked as private with _ prefix to indicate it's not currently in active use.
def _compare_envelopes(envelope1: Dict[str, Any], envelope2: Dict[str, Any], no_color: bool = False) -> Tuple[bool, List[str]]:
    """
    Compare two envelopes to generate a detailed diff.
    
    Note: This function is currently UNUSED as we only have the hash on-chain.
          It will be used in the future when the contract is upgraded to emit the full envelope.
    
    Args:
        envelope1: First envelope to compare
        envelope2: Second envelope to compare
        no_color: Whether to disable colored output
        
    Returns:
        Tuple of (match_result, diff_lines)
    """
    # Canonicalize envelopes
    json1 = canonicalize_envelope(envelope1)
    json2 = canonicalize_envelope(envelope2)
    
    # Compare
    match = json1 == json2
    
    # Generate diff
    diff_lines = []
    if not match:
        lines1 = json1.splitlines() or [json1]
        lines2 = json2.splitlines() or [json2]
        diff = difflib.unified_diff(
            lines1, 
            lines2,
            fromfile='envelope1',
            tofile='envelope2',
            lineterm=''
        )
        
        for line in diff:
            if no_color:
                diff_lines.append(line)
            else:
                if line.startswith('+'):
                    # Green for additions
                    diff_lines.append(f"\033[92m{line}\033[0m")
                elif line.startswith('-'):
                    # Red for deletions
                    diff_lines.append(f"\033[91m{line}\033[0m")
                else:
                    diff_lines.append(line)
    
    return match, diff_lines

def verify_hash_match(envelope_hash_hex: str, ipfs_envelope: Dict[str, Any]) -> bool:
    """
    Verify that the envelope hash recorded on-chain matches the IPFS envelope.
    
    Args:
        envelope_hash_hex: Hex-encoded envelope hash from on-chain
        ipfs_envelope: Envelope from IPFS
        
    Returns:
        True if hashes match, False otherwise
        
    Note:
        This assumes the contract uses keccak(json) for hashing.
        TODO: Confirm with Solidity team if they use keccak(abi.encode(envelope)) instead,
              which would require RLP encoding rather than JSON serialization.
              See https://github.com/IntentLayer/intentlayer-contracts/blob/main/contracts/IntentRecorder.sol
    """
    # Generate hash from IPFS envelope
    ipfs_canonical = canonicalize_envelope(ipfs_envelope).encode('utf-8')
    calculated_hash = Web3.keccak(ipfs_canonical).hex()
    
    # Normalize hex strings
    if not envelope_hash_hex.startswith('0x'):
        envelope_hash_hex = '0x' + envelope_hash_hex
    
    return calculated_hash.lower() == envelope_hash_hex.lower()

def should_use_color() -> bool:
    """
    Determine if color output should be used.
    
    Returns:
        True if color should be used, False otherwise
    """
    # Check if stdout is a TTY
    return sys.stdout.isatty()

def verify_tx(
    tx_hash: str,
    gateway: str,
    gateway_token: Optional[str] = None,
    network: Optional[str] = None,
    no_color: bool = False,
    debug: bool = False,
):
    """
    Verify a transaction's intent envelope against IPFS.
    
    Args:
        tx_hash: Transaction hash to verify
        gateway: IPFS gateway URL
        gateway_token: Optional authentication token for gateway
        network: Optional network name to use
        no_color: Whether to disable colored output
        debug: Whether to enable debug output
    
    Raises:
        typer.Exit: With appropriate exit code based on verification result
    """
    # Configure logging only if no handlers are set anywhere
    # This prevents any duplicate log entries, even if caller code sets up handlers
    log_level = logging.DEBUG if debug else logging.INFO
    root_logger = logging.getLogger()
    if not root_logger.handlers and not logger.handlers:
        logging.basicConfig(
            level=log_level,
            format="%(levelname)s: %(message)s"
        )
    
    # Disable color if not a TTY or explicitly disabled
    use_color = should_use_color() and not no_color
    
    try:
        # Normalize tx_hash
        if not tx_hash.startswith("0x"):
            tx_hash = "0x" + tx_hash
        
        # Validate gateway URL
        try:
            parsed = urllib.parse.urlparse(gateway)
            if parsed.scheme not in ("http", "https"):
                typer.echo(f"Error: Invalid gateway URL scheme: {parsed.scheme}", err=True)
                raise typer.Exit(4)
        except Exception as e:
            typer.echo(f"Error: Invalid gateway URL: {e}", err=True)
            raise typer.Exit(4)
        
        # Try to connect to the appropriate network and find the transaction
        try:
            # If network is specified, use it
            if network:
                w3, network_name, _ = setup_web3_for_network(network_name=network)
                logger.debug(f"Connected to specified network: {network_name}")
                
                # Now try to get the transaction receipt on this network
                try:
                    receipt = w3.eth.get_transaction_receipt(tx_hash)
                    logger.debug(f"Transaction found on specified network: {receipt['transactionHash'].hex()}")
                except Exception as e:
                    typer.echo(f"Error: Transaction not found on specified network {network}: {e}", err=True)
                    raise typer.Exit(2)
            else:
                # Try to find the transaction on any network
                try:
                    w3, network_name, receipt = setup_web3_for_network(tx_hash=tx_hash)
                    logger.debug(f"Transaction found on network: {network_name}")
                except ValueError as e:
                    typer.echo(f"Error: {e}", err=True)
                    raise typer.Exit(2)
                    
            # Get the chain ID
            tx_chain_id = w3.eth.chain_id
            logger.debug(f"Chain ID: {tx_chain_id}")
            
        except ValueError as e:
            typer.echo(f"Error: Failed to connect to network: {e}", err=True)
            raise typer.Exit(2)
        
        # Get IntentRecorder contract address
        try:
            network_config = NetworkConfig.get_network(network_name)
            recorder_address = network_config["intentRecorder"]
            logger.debug(f"IntentRecorder address: {recorder_address}")
        except KeyError as e:
            typer.echo(f"Error: Invalid network configuration: Missing {e}", err=True)
            raise typer.Exit(2)
        
        # Get the event signature once (lazy-loaded singleton)
        event_signature = get_intent_recorded_event_signature()
        
        # Create contract instance for event decoding
        contract = w3.eth.contract(address=recorder_address, abi=[INTENT_RECORDED_EVENT_ABI])
        
        # Parse logs to find IntentRecorded event
        cid = None
        envelope_hash = None
        sender = None
        stake_wei = None
        
        for log in receipt['logs']:
            # Check if log is from IntentRecorder contract
            if log['address'].lower() == recorder_address.lower() and len(log['topics']) > 0:
                # Check if it's the IntentRecorded event (case-insensitive comparison)
                if log['topics'][0].hex().lower() == event_signature.lower():
                    try:
                        # Decode log data
                        decoded_log = contract.events.IntentRecorded().process_log(log)
                        cid = decoded_log['args']['cid']
                        envelope_hash = decoded_log['args']['envelopeHash'].hex()
                        sender = decoded_log['args']['sender']
                        stake_wei = decoded_log['args']['stakeWei']
                        
                        logger.debug(f"Found IntentRecorded log event: cid={cid}, sender={sender}, stake={stake_wei}")
                        break
                    except Exception as e:
                        logger.error(f"Failed to parse log: {e}")
                        continue
        
        if cid is None:
            typer.echo("Error: No IntentRecorded event found in transaction logs", err=True)
            raise typer.Exit(1)
        
        # Fetch JSON payload from IPFS
        try:
            payload = fetch_ipfs_json(cid, gateway, gateway_token)
            logger.debug(f"Fetched payload from IPFS: {len(str(payload))} bytes")
        except Exception as e:
            typer.echo(f"Error: Failed to fetch IPFS payload: {e}", err=True)
            raise typer.Exit(2)
        
        # Extract envelope from IPFS payload
        if "envelope" not in payload:
            typer.echo("Error: No envelope found in IPFS payload", err=True)
            raise typer.Exit(1)
        
        ipfs_envelope = payload["envelope"]
        
        # Verify the envelope hash matches
        hash_match = verify_hash_match(envelope_hash, ipfs_envelope)
        if not hash_match:
            typer.echo("❌ VERIFICATION FAILED: Envelope hash mismatch", err=True)
            typer.echo("\nThe envelope hash recorded on-chain does not match the hash of the IPFS envelope.")
            raise typer.Exit(1)
        
        # Since we only have the hash on-chain, we can't compare the full envelope structure
        # Consider the verification successful if the hash matches
        match = hash_match
        diff_lines = []
        
        # Output result
        if match:
            if use_color:
                typer.echo(typer.style("✅ VERIFICATION PASSED", fg=typer.colors.GREEN))
            else:
                typer.echo("VERIFICATION PASSED")
            
            # Print summary
            typer.echo(f"\nTransaction: {tx_hash}")
            typer.echo(f"Network: {network_name} (Chain ID: {tx_chain_id})")
            typer.echo(f"IPFS CID: {cid}")
            typer.echo(f"Envelope hash: {envelope_hash}")
            
            raise typer.Exit(0)
        else:
            if use_color:
                typer.echo(typer.style("❌ VERIFICATION FAILED", fg=typer.colors.RED))
            else:
                typer.echo("VERIFICATION FAILED")
            
            # Print diff if available
            if diff_lines:
                typer.echo("\nDifferences between on-chain and IPFS envelopes:")
                for line in diff_lines:
                    typer.echo(line)
            
            raise typer.Exit(1)
    
    except typer.Exit:
        # Re-raise typer.Exit exceptions
        raise
    except Exception as e:
        if debug:
            logger.exception("Unexpected error")
        else:
            typer.echo(f"Error: Unexpected error: {e}", err=True)
            typer.echo("Run with --debug for more information", err=True)
        raise typer.Exit(3)

@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    tx_hash: str = typer.Argument(None, help="Transaction hash to verify"),
    gateway: str = typer.Option(
        "https://w3s.link/ipfs/", 
        "--gateway", 
        help="IPFS gateway URL"
    ),
    gateway_token: str = typer.Option(
        None, 
        "--gateway-token", 
        help="Authentication token for private IPFS gateways"
    ),
    network: str = typer.Option(
        None, 
        "--network", 
        help="Specific network to use (default: auto-detect)"
    ),
    api_key: str = typer.Option(
        None, 
        "--api-key", 
        help="API key for authentication (preferred)"
    ),
    jwt_token: str = typer.Option(
        None, 
        "--jwt-token", 
        help="JWT token for authentication (deprecated)"
    ),
    allow_insecure: bool = typer.Option(
        False, 
        "--allow-insecure", 
        help="Allow insecure connections (not recommended for production)"
    ),
    no_color: bool = typer.Option(
        False, 
        "--no-color", 
        help="Disable colored output"
    ),
    debug: bool = typer.Option(
        False, 
        "--debug", 
        help="Enable debug output"
    ),
):
    """
    Verify that an IntentEnvelope recorded on-chain matches the JSON envelope stored on IPFS.
    
    Returns exit code:
    - 0: Hashes match (PASS)
    - 1: Mismatch (FAIL)
    - 2: Network/RPC error or gateway unreachable
    - 3: Unexpected error
    - 4: Invalid command arguments
    """
    # If this is called with a subcommand, just return
    if ctx.invoked_subcommand is not None:
        return
    
    # Handle security flags
    if allow_insecure:
        os.environ["INTENT_SKIP_TLS_VERIFY"] = "true"
        # Print warning in color if supported
        if not no_color and should_use_color():
            typer.echo(
                typer.style(
                    "SECURITY WARNING: Insecure connections enabled. Not recommended for production!",
                    fg=typer.colors.RED, bold=True
                )
            )
        else:
            typer.echo("SECURITY WARNING: Insecure connections enabled. Not recommended for production!")
    
    # Handle authentication options - strip whitespace to handle copy-paste issues
    if api_key:
        os.environ["INTENT_API_KEY"] = api_key.strip()
    if jwt_token:
        os.environ["INTENT_BEARER_TOKEN"] = jwt_token.strip()
        
    # Check for both authentication methods - raise error
    if os.environ.get("INTENT_API_KEY") and os.environ.get("INTENT_BEARER_TOKEN"):
        typer.echo(
            "Error: Both API key and JWT token provided. Use only one authentication method.",
            err=True
        )
        raise typer.Exit(4)
        
    # If no tx_hash is provided, show help
    if not tx_hash:
        ctx.get_help()
        raise typer.Exit(0)
        
    # Otherwise, run the verification directly
    verify_tx(tx_hash, gateway, gateway_token, network, no_color, debug)

# Legacy command for backward compatibility if needed
@app.command(hidden=True)
def tx(
    tx_hash: str = typer.Argument(..., help="Transaction hash to verify"),
    gateway: str = typer.Option(
        "https://w3s.link/ipfs/", 
        "--gateway", 
        help="IPFS gateway URL"
    ),
    gateway_token: str = typer.Option(
        None, 
        "--gateway-token", 
        help="Authentication token for private IPFS gateways"
    ),
    network: str = typer.Option(
        None, 
        "--network", 
        help="Specific network to use (default: auto-detect)"
    ),
    api_key: str = typer.Option(
        None, 
        "--api-key", 
        help="API key for authentication (preferred)"
    ),
    jwt_token: str = typer.Option(
        None, 
        "--jwt-token", 
        help="JWT token for authentication (deprecated)"
    ),
    allow_insecure: bool = typer.Option(
        False, 
        "--allow-insecure", 
        help="Allow insecure connections (not recommended for production)"
    ),
    no_color: bool = typer.Option(
        False, 
        "--no-color", 
        help="Disable colored output"
    ),
    debug: bool = typer.Option(
        False, 
        "--debug", 
        help="Enable debug output"
    ),
):
    """Legacy command for verifying transaction hashes."""
    # Handle security flags
    if allow_insecure:
        os.environ["INTENT_SKIP_TLS_VERIFY"] = "true"
        # Print warning in color if supported
        if not no_color and should_use_color():
            typer.echo(
                typer.style(
                    "SECURITY WARNING: Insecure connections enabled. Not recommended for production!",
                    fg=typer.colors.RED, bold=True
                )
            )
        else:
            typer.echo("SECURITY WARNING: Insecure connections enabled. Not recommended for production!")
    
    # Handle authentication options
    if api_key:
        os.environ["INTENT_API_KEY"] = api_key.strip()
    if jwt_token:
        os.environ["INTENT_BEARER_TOKEN"] = jwt_token.strip()
        
    # Check for both authentication methods - raise error
    if os.environ.get("INTENT_API_KEY") and os.environ.get("INTENT_BEARER_TOKEN"):
        typer.echo(
            "Error: Both API key and JWT token provided. Use only one authentication method.",
            err=True
        )
        raise typer.Exit(4)
        
    verify_tx(tx_hash, gateway, gateway_token, network, no_color, debug)

if __name__ == "__main__":
    app()