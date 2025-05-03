# Implementation Plan: SDK Authentication for API Keys

## Overview

This plan updates the IntentLayer Python SDK to use API key authentication as the primary method, with fallback support for JWT tokens. The changes align with the gateway team's migration to Kong Konnect for API key management.

## Key Requirements

1. **Authentication Headers**:
   - [x] Use `Authorization: Key <INTENT_API_KEY>` as the primary authentication method
   - [x] The SDK does NOT send `x-intent-org-id` - Kong will handle that transformation
   - [x] Keep API keys as opaque strings (not UUIDs) - no format validation needed
   - [x] Trim whitespace on credentials to handle copy-paste errors

2. **JWT Fallback Support**:
   - [x] Support `INTENT_BEARER_TOKEN` environment variable (or CLI `--jwt-token`) 
   - [x] If API key is absent but bearer token exists, use `Authorization: Bearer <token>`
   - [x] Document this as deprecated, noting it requires Gateway with `--enable-jwt-fallback`
   - [x] Raise error if both API key and Bearer token are provided

3. **Connection Security**:
   - [x] Parse URL schemes: `http`, `https`, `grpc`, `grpcs`
   - [x] Use `secure_channel` for `https` and `grpcs`
   - [x] Use `insecure_channel` for `grpc`
   - [x] For `http`, default to insecure but warn unless explicitly allowed
   - [x] When `INTENT_SKIP_TLS_VERIFY=true`, keep TLS encryption but skip certificate validation

4. **Environment Variables and CLI Flags**:
   - [x] Use `INTENT_API_KEY` (not renaming to INTENT_ORG_ID to avoid confusion)
   - [x] Support `INTENT_SKIP_TLS_VERIFY=true` for development environments
   - [x] Print strong security warnings (in red/bold where possible) for insecure channels
   - [x] Add CLI flags for `--allow-insecure` and `--jwt-token`

## Implementation Tasks

### 1. Update Authentication Headers

1. Modify `GatewayClient._create_metadata()` in `intentlayer_sdk/gateway/client.py`:
   - [x] Use `INTENT_API_KEY` from environment or constructor parameter
   - [x] Change prefix from `Bearer` to `Key`
   - [x] Remove all JWT validation logic (no longer needed)
   - [x] Add fallback to use `Authorization: Bearer <token>` if `INTENT_BEARER_TOKEN` is set and API key is absent
   - [x] Raise error if both API key and Bearer token are provided
   - [x] Trim whitespace from credentials to handle copy-paste issues

### 2. Update URL Scheme Parsing

1. Enhance URL parsing in `_validate_gateway_url()` and `_create_channel()`:
   - [x] Parse URL schemes: `http`, `https`, `grpc`, `grpcs`
   - [x] Use `secure_channel` for `https` and `grpcs`
   - [x] Use `insecure_channel` for `grpc`
   - [x] For `http`, default to insecure but warn unless explicitly allowed
   - [x] When `INTENT_SKIP_TLS_VERIFY=true`, keep TLS encryption but skip certificate validation

### 3. Add Environment Variables and CLI Flags

1. Add `INTENT_SKIP_TLS_VERIFY` environment variable support:
   - [x] Implement in URL validation and channel creation
   - [x] Print strong security warnings for insecure connections (in red where possible)

2. Add CLI flags:
   - [x] `--allow-insecure`: Allow insecure connections (sets `INTENT_SKIP_TLS_VERIFY=true`)
   - [x] `--jwt-token`: Provide JWT token for authentication (deprecated)

### 4. Test Coverage

1. Create tests for different connection schemes and auth methods:
   - [x] `grpc://` + Key → header = Key, insecure channel
   - [x] `https://` + Key → header = Key, secure channel
   - [x] `https://` + Bearer token → header = Bearer, secure channel
   - [x] Both env vars set → raises ValueError

### 5. Documentation Updates

1. Update environment variable documentation:
   - [x] Show example: `export INTENT_API_KEY=sk_live_123...`
   - [x] Note that Kong maps the key to an organization automatically - no UUID needed
   - [x] Document `INTENT_BEARER_TOKEN` as deprecated
   - [x] Explain security implications of `INTENT_SKIP_TLS_VERIFY`
   - [x] Document URL scheme handling

## Code Changes

### 1. Update GatewayClient Constructor

```python
def __init__(
    self,
    gateway_url: str,
    api_key: Optional[str] = None,
    bearer_token: Optional[str] = None,
    timeout: Optional[int] = None,
    verify_ssl: bool = True
):
    """
    Initialize the Gateway client.

    Args:
        gateway_url: URL of the gateway service
        api_key: Optional API key for authentication (preferred)
        bearer_token: Optional JWT token for authentication (deprecated)
        timeout: Request timeout in seconds
        verify_ssl: Whether to verify SSL certificates

    Raises:
        ValueError: If gateway_url is invalid or both api_key and bearer_token are provided
    """
    # Always call ensure_grpc_installed which will raise a proper error if needed
    ensure_grpc_installed()

    # Validate URL
    self._validate_gateway_url(gateway_url)
    self.gateway_url = gateway_url
    
    # Get API key and bearer token from environment if not provided
    # Strip whitespace to handle copy-paste errors
    self.api_key = (api_key or os.getenv("INTENT_API_KEY", "")).strip() or None
    self.bearer_token = (bearer_token or os.getenv("INTENT_BEARER_TOKEN", "")).strip() or None
    
    # Check for both authentication methods - raise error
    if self.api_key and self.bearer_token:
        raise ValueError(
            "Both API key and bearer token provided. Use only one authentication method. "
            "API keys are preferred, bearer tokens are deprecated."
        )

    # Get timeout from env var or parameter (default: 5 seconds)
    self.timeout = timeout or int(os.environ.get("INTENT_GW_TIMEOUT", "5"))

    # Create gRPC channel and stub
    self.channel = self._create_channel(gateway_url, verify_ssl)
    
    # Create stub for gRPC communication
    if PROTO_AVAILABLE:
        self.stub = GatewayServiceStub(self.channel)
        logger.debug("Using proto-generated GatewayServiceStub")
    else:
        logger.warning("Proto stubs not available - using placeholder implementation")
        self.stub = self._create_stub_placeholder()

    logger.debug(f"Initialized Gateway client for {gateway_url}")
```

### 2. Modify _create_metadata()

```python
def _create_metadata(self) -> Optional[Tuple[Tuple[str, str], ...]]:
    """
    Create gRPC metadata with authentication.

    Returns:
        Tuple of metadata key-value pairs, or None if no metadata needed.
    """
    metadata = []
    
    # Prefer API key authentication (primary method)
    if self.api_key:
        metadata.append(('authorization', f'Key {self.api_key}'))
        logger.debug("Using API key authentication")
    # Fall back to bearer token if provided (deprecated)
    elif self.bearer_token:
        metadata.append(('authorization', f'Bearer {self.bearer_token}'))
        logger.warning(
            "Using deprecated JWT bearer token authentication. "
            "API keys are the preferred authentication method."
        )

    return tuple(metadata) if metadata else None
```

### 3. Update URL Scheme Parsing and Channel Creation

```python
def _validate_gateway_url(self, url: str) -> None:
    """
    Validate the gateway URL and scheme.

    Args:
        url: Gateway URL to validate

    Raises:
        ValueError: If URL is invalid or uses insecure HTTP without explicit permission
    """
    try:
        parsed = urllib.parse.urlparse(url)
        host = parsed.hostname or ""
        scheme = parsed.scheme.lower()
        
        # Treat localhost/loopback as local development 
        is_local = host in ("localhost", "127.0.0.1", "::1")
        
        # Check for secure schemes (https, grpcs) vs insecure schemes (http, grpc)
        is_secure_scheme = scheme in ("https", "grpcs")
        is_insecure_scheme = scheme in ("http", "grpc")
        
        if not (is_secure_scheme or is_insecure_scheme):
            raise ValueError(
                f"Gateway URL scheme must be one of: https, http, grpcs, grpc (got: {scheme})"
            )
            
        # For non-secure schemes, warn unless explicitly allowed
        if not is_secure_scheme and not is_local:
            insecure_allowed = os.environ.get("INTENT_SKIP_TLS_VERIFY") == "true"
            if not insecure_allowed:
                raise ValueError(
                    f"Gateway URL uses insecure scheme ({scheme}://). "
                    "Set INTENT_SKIP_TLS_VERIFY=true to allow insecure connections "
                    "(not recommended for production)."
                )
            else:
                logger.warning(
                    f"SECURITY ALERT: Using insecure scheme ({scheme}://) "
                    "with INTENT_SKIP_TLS_VERIFY=true. This is not recommended for production!"
                )
    except Exception as e:
        # Catch potential parsing errors too
        raise ValueError(f"Invalid gateway URL '{url}': {e}")

def _create_channel(self, url: str, verify_ssl: bool) -> grpc.Channel:
    """
    Create a gRPC channel based on URL scheme and verify_ssl flag.
    
    Args:
        url: Gateway URL
        verify_ssl: Whether to verify SSL certificates
        
    Returns:
        gRPC channel
    """
    # Parse URL to extract host, port, and scheme
    parsed = urllib.parse.urlparse(url)
    host = parsed.hostname
    scheme = parsed.scheme.lower()
    
    # Determine port and security based on scheme
    if scheme in ('https', 'grpcs'):
        default_port = 443
        secure = True
    else:  # http or grpc
        default_port = 80
        secure = False
    
    port = parsed.port or default_port
    target = f"{host}:{port}"
    
    # Check for TLS verification override
    skip_tls_verify = os.environ.get("INTENT_SKIP_TLS_VERIFY") == "true"
    
    # Create appropriate channel based on scheme and verification requirements
    if not secure:
        # Plaintext channel for http/grpc schemes
        logger.warning(
            f"SECURITY ALERT: Creating insecure gRPC channel to {target}. "
            "This is not recommended for production environments!"
        )
        return grpc.insecure_channel(target)
    elif verify_ssl and not skip_tls_verify:
        # Fully verified TLS for secure schemes
        # ... existing secure channel creation logic with roots ...
        creds = grpc.ssl_channel_credentials()  # Simplified for the plan
        options = [
            # ... existing channel options ...
        ]
        return grpc.secure_channel(target, creds, options=options)
    else:
        # Encrypted but not verified TLS (for dev environments)
        logger.warning(
            "SECURITY ALERT: Creating TLS channel without certificate validation. "
            "This is not recommended for production environments!"
        )
        # Create channel with encryption but no certificate validation
        creds = grpc.ssl_channel_credentials()  # No root certificates = no host verification
        return grpc.secure_channel(
            target, 
            creds, 
            options=[("grpc.ssl_target_name_override", host)]
        )
```

### 4. Add CLI Flags

```python
@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    tx_hash: str = typer.Argument(None, help="Transaction hash to verify"),
    # ...existing options...
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
    # ...other options...
):
    """
    Verify that an IntentEnvelope recorded on-chain matches the JSON envelope stored on IPFS.
    """
    # Handle security flags
    if allow_insecure:
        os.environ["INTENT_SKIP_TLS_VERIFY"] = "true"
        if not no_color:
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
    
    # Proceed with verification
    # ...existing verification logic...
```

## Testing Plan

Create tests to verify the following scenarios:

1. **Connection scheme tests**:
   - `grpc://` + API Key → Uses `Key` header and insecure channel
   - `https://` + API Key → Uses `Key` header and secure channel
   - `https://` + Bearer token → Uses `Bearer` header and secure channel

2. **Authentication tests**:
   - Both API key and Bearer token set → Raises ValueError
   - API key from constructor parameter
   - API key from environment variable
   - Bearer token from environment variable (fallback)
   - Credentials with whitespace are properly trimmed

3. **Security configuration tests**:
   - `INTENT_SKIP_TLS_VERIFY=true` with secure scheme → Uses secure channel with SSL but no cert validation
   - Insecure scheme without override → Raises error

## Expected Outcomes

1. SDK successfully connects to gateway with properly secured channels
2. Authentication headers correctly use `Key` prefix for API keys
3. JWT token authentication works as fallback when enabled
4. Security warnings alert users to insecure configurations
5. Tests pass for all specified scenarios
6. Documentation clearly explains new authentication flow and environment variables