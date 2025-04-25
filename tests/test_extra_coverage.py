"""
Extra “thin-slice” tests that cover the branches PyPI never hits in
daily use:   min_stake_wei caching, ipfs_cid_to_bytes edge-paths and the
generic/fallback parts of tx_url().
"""
import time
import warnings
from unittest.mock import MagicMock

import pytest

from intentlayer_sdk.client import IntentClient
from intentlayer_sdk.utils import ipfs_cid_to_bytes
from intentlayer_sdk.exceptions import NetworkError, TransactionError
from tests.conftest import (
    TEST_RPC_URL,
    TEST_PINNER_URL,
    TEST_CONTRACT,
    TEST_PRIV_KEY,
)

# test_helpers is where create_test_client is actually defined
try:
    from tests.test_helpers import create_test_client
except ImportError:  # pragma: no cover  – fallback if someone runs the file standalone
    from intentlayer_sdk.client import IntentClient
    from intentlayer_sdk.signer.local import LocalSigner

    def create_test_client(
        rpc_url: str = TEST_RPC_URL,
        pinner_url: str = TEST_PINNER_URL,
        priv_key: str = TEST_PRIV_KEY,
        recorder_address: str = TEST_CONTRACT,
        min_stake_wei: int = 1,
    ) -> IntentClient:
        """Minimal fallback helper (mirrors test_helpers.create_test_client)."""
        return IntentClient(
            rpc_url=rpc_url,
            pinner_url=pinner_url,
            signer=LocalSigner(priv_key),
            recorder_address=recorder_address,
            min_stake_wei=min_stake_wei,
        )



# ---------------------------------------------------------------------
# 1)  ipfs_cid_to_bytes  — hex-CID path  +  truncation warning path
# ---------------------------------------------------------------------
def test_ipfs_cid_to_bytes_hex_and_truncate():
    # 64-byte hex string ( >32 so we trigger the truncation branch)
    long_hex_cid = "0x" + "ab" * 64
    with warnings.catch_warnings(record=True) as rec:
        warnings.simplefilter("always")
        out = ipfs_cid_to_bytes(long_hex_cid, max_bytes=32)
        # truncated to 32 bytes
        assert len(out) == 32
        assert rec and "Truncating" in str(rec[0].message)


# ---------------------------------------------------------------------
# 2)  min_stake_wei property   – cache hit vs. refresh path
# ---------------------------------------------------------------------
def test_min_stake_caching_and_manual_override(monkeypatch):
    """
    • first access: pulls from chain (mocked) and caches
    • second access: served from cache (no extra RPC)
    • manual override (constructor param) must NEVER auto-refresh
    """
    # build a dummy “chain” that returns a changing value so we can detect calls
    calls = {"count": 0}
    def _min_stake():
        calls["count"] += 1
        return 111  # wei

    client = create_test_client(
        rpc_url=TEST_RPC_URL,
        pinner_url=TEST_PINNER_URL,
        min_stake_wei=None,              # let it hit RPC
        priv_key=TEST_PRIV_KEY,
    )
    # monkey-patch the contract call
    # Patch **the factory** instead of the single instance, otherwise every
    # access returns a fresh MagicMock and our stub is ignored.
    monkeypatch.setattr(
        client.recorder_contract.functions,                   # the FunctionsProxy
        "MIN_STAKE_WEI",
        lambda: type("Stub", (), {"call": staticmethod(_min_stake)})(),
        raising=False,
    )

    # 1st read → makes RPC call
    assert client.min_stake_wei == 111
    assert calls["count"] == 1

    # 2nd read within 15 min → cached, NO new RPC
    assert client.min_stake_wei == 111
    assert calls["count"] == 1          # unchanged

    # manual override should disable auto-refresh completely
    client2 = create_test_client(
        rpc_url=TEST_RPC_URL,
        pinner_url=TEST_PINNER_URL,
        min_stake_wei=555,               # manual value
        priv_key=TEST_PRIV_KEY,
    )
    # fake an absurdly old timestamp to prove it would refresh if allowed
    client2._min_stake_wei_timestamp = 0
    assert client2.min_stake_wei == 555  # never replaced


# ---------------------------------------------------------------------
# 3)  tx_url() — network fallback & bytes/str handling in one shot
# ---------------------------------------------------------------------
@pytest.mark.parametrize(
    "chain_id, fragment",
    [
        (1, "etherscan.io"),
        (11155111, "sepolia.etherscan.io"),
        (300, "sepolia.explorer.zksync.io"),
        (999999, "blockscan.com"),   # unknown → generic fallback
    ],
)
def test_tx_url_variants(chain_id, fragment):
    client = create_test_client(
        rpc_url=TEST_RPC_URL,
        pinner_url=TEST_PINNER_URL,
        priv_key=TEST_PRIV_KEY,
        min_stake_wei=1,
    )
    client._expected_chain_id = chain_id

    # use BYTES to hit that branch too
    tx_hash_bytes = bytes.fromhex("42" * 32)
    url = client.tx_url(tx_hash_bytes)
    assert fragment in url
    assert url.endswith(tx_hash_bytes.hex())


# ---------------------------------------------------------------------
# 4)  assert_chain_id() — path where *web3* raises *Exception*,
#     which should be wrapped into NetworkError with the proper message
# ---------------------------------------------------------------------
def test_assert_chain_id_rpc_failure(monkeypatch):
    client = create_test_client(
        rpc_url=TEST_RPC_URL,
        pinner_url=TEST_PINNER_URL,
        priv_key=TEST_PRIV_KEY,
        min_stake_wei=1,
    )
    client._expected_chain_id = 10
    # make the underlying call blow up
    monkeypatch.setattr(
        client.w3.eth.__class__,                
        "chain_id",
        property(lambda self: (_ for _ in ()).throw(Exception("RPC error"))),
        raising=True,
    )
    with pytest.raises(NetworkError, match="Failed to validate chain ID"):
        client.assert_chain_id()