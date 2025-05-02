"""
Constants for elliptic curve cryptography.
"""

# SECP256K1 constants
# Order of the SECP256K1 elliptic curve (N value)
# This is needed to properly derive Ethereum keys
SECP256K1_N = 0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEBAAEDCE6AF48A03BBFD25E8CD0364141

# Minimum private key value for Ethereum (1)
SECP256K1_MIN = 1

# Maximum private key value for Ethereum (N-1)
SECP256K1_MAX = SECP256K1_N - 1