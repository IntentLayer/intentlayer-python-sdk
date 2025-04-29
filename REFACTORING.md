# IntentClient Refactoring Proposal

## Problem Statement

The `IntentClient` class in `intentlayer_sdk/client.py` has grown too large and handles too many responsibilities, making it difficult to maintain and extend. The class currently:

1. Manages blockchain interactions (transactions, contract calls)
2. Handles IPFS pinning
3. Deals with identity management and DID registration
4. Integrates with the Gateway service
5. Performs input validation and error handling across all these domains

## Solution Approach

We should refactor the monolithic `IntentClient` into a set of smaller, focused service classes that follow the Single Responsibility Principle. Each service class will handle a specific aspect of the client's functionality, while the main `IntentClient` class will coordinate these services.

## Proposed Architecture

### 1. Core Components

#### `IntentClient` (Coordinator)

- Primary entry point for SDK users
- Coordinates between specialized services
- Maintains backward compatibility with existing API
- Lightweight, delegating implementation details to specialized services

#### Service Classes

1. **`BlockchainService`**
   - Handles all blockchain interactions
   - Manages web3 instance, contract binding, and transaction building
   - Provides methods for sending transactions and querying contracts
   - Implements chain ID validation

2. **`IPFSService`**
   - Handles IPFS pinning and CID validation/conversion
   - Manages HTTP session and retries for pinning service

3. **`IdentityService`**
   - Handles DID registration and resolution
   - Integrates with the Identity module
   - Provides DID validation and registration status checks

4. **`GatewayIntegration`**
   - Manages Gateway client setup and DID registration with Gateway
   - Handles Gateway-specific error conditions
   - Provides clean integration between client and Gateway service

### 2. Utility Components

1. **`TransactionBuilder`**
   - Creates, signs, and sends transactions
   - Handles gas estimation and nonce management
   - Provides consistent transaction building across service classes

2. **`ConfigurationManager`**
   - Handles environment variables and configuration settings
   - Manages network configuration loading
   - Validates URLs and other configuration parameters

## Implementation Plan

### Phase 1: Preparation

1. Extract interfaces/protocols for each service class to define the API
2. Create utility classes for shared functionality
3. Add placeholder implementations of service classes

### Phase 2: Service Implementation

1. Implement each service class with unit tests
2. Refactor `IntentClient` to use service classes internally
3. Ensure backward compatibility with existing API

### Phase 3: Integration

1. Update integration tests to use the refactored classes
2. Ensure all existing tests still pass
3. Add comprehensive documentation for the new architecture

## File Structure

```
intentlayer_sdk/
├── __init__.py
├── client.py                     # Main client interface (refactored to be thinner)
├── config.py                     # Existing config module
├── envelope.py                   # Existing envelope module
├── exceptions.py                 # Existing exceptions module
├── blockchain/                   # New module
│   ├── __init__.py
│   ├── service.py                # BlockchainService implementation
│   └── tx_builder.py             # TransactionBuilder implementation
├── ipfs/                         # New module
│   ├── __init__.py
│   ├── service.py                # IPFSService implementation
│   └── utils.py                  # CID conversion utilities
├── identity/                     # Existing module
│   ├── __init__.py
│   ├── service.py                # New IdentityService implementation
│   └── ...                       # Existing identity module files
├── gateway/                      # Existing module
│   ├── __init__.py
│   ├── client.py                 # Existing gateway client
│   ├── integration.py            # New GatewayIntegration implementation
│   └── exceptions.py             # Existing gateway exceptions
└── ...                           # Other existing files
```

## Migration Strategy

To ensure a smooth transition, we'll follow these steps:

1. Create the new services with feature parity to existing code
2. Modify `IntentClient` to use these services internally without changing its API
3. Add tests for each service
4. Gradually migrate users to the new services as needed

## Benefits

1. **Maintainability**: Smaller, focused classes are easier to understand and maintain
2. **Testability**: Services can be tested in isolation
3. **Extensibility**: New functionality can be added without modifying existing code
4. **Separation of Concerns**: Each service has a clear responsibility
5. **Composability**: Services can be used independently or together

## Backward Compatibility

The refactored `IntentClient` will maintain the same public API to ensure backward compatibility. Existing code using the client will continue to work without modification.

## Detailed Service Definitions

### `BlockchainService`

```python
class BlockchainService:
    """Handles all blockchain interactions for the IntentClient."""
    
    def __init__(
        self, 
        rpc_url: str,
        recorder_address: str,
        did_registry_address: Optional[str] = None,
        signer: Signer = None,
        expected_chain_id: Optional[int] = None,
        network_name: Optional[str] = None,
        logger: Optional[logging.Logger] = None,
    ):
        """Initialize the blockchain service."""
        # Implementation...
    
    def assert_chain_id(self) -> None:
        """Assert that connected chain matches expected chain ID."""
        # Implementation...
        
    def get_min_stake_wei(self) -> int:
        """Get minimum stake required by IntentRecorder contract."""
        # Implementation...
        
    def refresh_min_stake(self) -> int:
        """Force refresh minimum stake from contract."""
        # Implementation...
        
    def build_transaction(
        self, 
        contract_function,
        **kwargs
    ) -> Dict[str, Any]:
        """Build a transaction for a contract function."""
        # Implementation...
        
    def sign_and_send_transaction(
        self,
        transaction: Dict[str, Any],
        wait_for_receipt: bool = True,
    ) -> Dict[str, Any]:
        """Sign and send a transaction."""
        # Implementation...
        
    def record_intent(
        self,
        envelope_hash: Union[str, bytes],
        cid_bytes: bytes,
        stake_wei: int,
        **kwargs
    ) -> Dict[str, Any]:
        """Record an intent on the blockchain."""
        # Implementation...
        
    def register_did(
        self,
        did: str,
        **kwargs
    ) -> Dict[str, Any]:
        """Register a DID on the blockchain."""
        # Implementation...
        
    def resolve_did(self, did: str) -> Tuple[str, bool]:
        """Resolve a DID to its owner address and active status."""
        # Implementation...
```

### `IPFSService`

```python
class IPFSService:
    """Handles IPFS pinning and CID operations."""
    
    def __init__(
        self,
        pinner_url: str,
        retry_count: int = 3,
        timeout: int = 30,
        logger: Optional[logging.Logger] = None,
    ):
        """Initialize the IPFS service."""
        # Implementation...
        
    def pin_to_ipfs(self, payload: Dict[str, Any]) -> str:
        """Pin data to IPFS via pinning service."""
        # Implementation...
        
    def validate_cid(self, cid: str) -> bool:
        """Validate an IPFS CID format."""
        # Implementation...
        
    def cid_to_bytes(self, cid: str) -> bytes:
        """Convert an IPFS CID to bytes for on-chain use."""
        # Implementation...
```

### `IdentityService`

```python
class IdentityService:
    """Handles DID identity operations."""
    
    def __init__(
        self,
        blockchain_service: BlockchainService,
        auto_did: bool = True,
        logger: Optional[logging.Logger] = None,
    ):
        """Initialize the identity service."""
        # Implementation...
        
    def get_or_create_identity(self) -> Identity:
        """Get existing identity or create a new one."""
        # Implementation...
        
    def register_did_on_chain(
        self,
        did: str,
        **kwargs
    ) -> Dict[str, Any]:
        """Register a DID on-chain."""
        # Implementation...
        
    def resolve_did(self, did: str) -> Tuple[str, bool]:
        """Resolve a DID to its owner and active status."""
        # Implementation...
        
    def validate_did(self, did: str) -> bool:
        """Validate a DID string format."""
        # Implementation...
```

### `GatewayIntegration`

```python
class GatewayIntegration:
    """Handles integration with Gateway service."""
    
    def __init__(
        self,
        gateway_url: Optional[str] = None,
        api_key: Optional[str] = None,
        logger: Optional[logging.Logger] = None,
    ):
        """Initialize Gateway integration."""
        # Implementation...
        
    def initialize_gateway_client(self) -> Optional[GatewayClient]:
        """Initialize Gateway client if URL is provided."""
        # Implementation...
        
    def ensure_registered(self, did: str) -> bool:
        """Ensure the DID is registered with Gateway service."""
        # Implementation...
        
    def extract_org_id_from_api_key(self) -> Optional[str]:
        """Extract org_id from JWT token in API key."""
        # Implementation...
```

## Example of Refactored Client Usage

```python
# Example integration in the refactored IntentClient

def __init__(self, rpc_url, pinner_url, signer, recorder_address, ...):
    # Initialize services
    self.blockchain_service = BlockchainService(
        rpc_url=rpc_url,
        recorder_address=recorder_address,
        did_registry_address=did_registry_address,
        signer=signer,
        expected_chain_id=expected_chain_id,
        network_name=self._network_name,
        logger=logger,
    )
    
    self.ipfs_service = IPFSService(
        pinner_url=pinner_url,
        retry_count=retry_count,
        timeout=timeout,
        logger=logger,
    )
    
    self.identity_service = IdentityService(
        blockchain_service=self.blockchain_service,
        auto_did=auto_did,
        logger=logger,
    )
    
    self.gateway_integration = GatewayIntegration(
        gateway_url=gateway_url,
        api_key=api_key,
        logger=logger,
    )

def send_intent(self, envelope_hash, payload_dict, ...):
    # Use services to implement the method
    
    # 1. Validate chain ID
    self.blockchain_service.assert_chain_id()
    
    # 2. Ensure DID is registered with Gateway if needed
    if hasattr(self, "_identity"):
        self.gateway_integration.ensure_registered(self._identity.did)
    
    # 3. Validate payload
    self._validate_payload(payload_dict)
    
    # 4. Verify DID is active
    if "envelope" in payload_dict and isinstance(payload_dict["envelope"], dict):
        did = payload_dict["envelope"].get("did")
        if did:
            self.identity_service.validate_did_active(did)
    
    # 5. Pin to IPFS
    cid = self.ipfs_service.pin_to_ipfs(payload_dict)
    cid_bytes = self.ipfs_service.cid_to_bytes(cid)
    
    # 6. Record intent on-chain
    return self.blockchain_service.record_intent(
        envelope_hash=envelope_hash,
        cid_bytes=cid_bytes,
        stake_wei=stake_wei or self.blockchain_service.get_min_stake_wei(),
        gas=gas,
        gas_price_override=gas_price_override,
        wait_for_receipt=wait_for_receipt,
        poll_interval=poll_interval,
    )
```