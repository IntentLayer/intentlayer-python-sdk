#!/usr/bin/env python3
"""
Example usage of the verify CLI command.

This example demonstrates how to use the 'intent-cli verify' command
to verify that an on-chain intent matches its IPFS payload.
"""
import sys
import subprocess
import argparse

def main():
    """Run the example."""
    parser = argparse.ArgumentParser(
        description="Verify an IntentLayer transaction.")
    parser.add_argument(
        "tx_hash", 
        help="Transaction hash to verify"
    )
    parser.add_argument(
        "--gateway", 
        help="IPFS gateway URL", 
        default="https://w3s.link/ipfs/"
    )
    parser.add_argument(
        "--no-color", 
        help="Disable colored output", 
        action="store_true"
    )
    parser.add_argument(
        "--debug", 
        help="Enable debug output", 
        action="store_true"
    )
    
    args = parser.parse_args()
    
    # Construct the command
    cmd = ["intent-cli", "verify", args.tx_hash]
    
    if args.gateway:
        cmd.extend(["--gateway", args.gateway])
    
    if args.no_color:
        cmd.append("--no-color")
    
    if args.debug:
        cmd.append("--debug")
    
    # Run the command
    print(f"Running command: {' '.join(cmd)}\n")
    result = subprocess.run(cmd)
    
    # Return the same exit code
    return result.returncode

if __name__ == "__main__":
    sys.exit(main())