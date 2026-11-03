"""NEAR transaction encoding and the anchor call, against a mocked NEAR RPC."""

from __future__ import annotations

import base64
import hashlib
import json
import struct

import httpx
import pytest
import respx
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from hushmark.anchor import (
    TESTNET_RPC,
    AnchorError,
    NearAnchor,
    NearKey,
    b58decode,
    b58encode,
    function_call_tx,
    sign_tx,
)

SEED = bytes(range(32))
ACCOUNT = "hushmark-anchor.testnet"
KEY_HASH, RECEIPT = "1" * 64, "2" * 64
PANIC = "Smart contract panicked: this review key is already anchored"


def secret() -> str:
    key = NearKey("ed25519:" + b58encode(SEED))
    return "ed25519:" + b58encode(SEED + key.public_bytes)


@pytest.mark.parametrize(
    ("raw", "text"),
    [
        (b"", ""),
        (b"Hello World!", "2NEpo7TZRRrLZSi2U"),
        (b"\0\0\x01", "112"),
        (bytes(32), "1" * 32),
    ],
)
def test_base58_matches_bitcoin_alphabet(raw: bytes, text: str) -> None:
    assert b58encode(raw) == text
    assert b58decode(text) == raw


def test_key_accepts_64_byte_near_secret_and_derives_public_key() -> None:
    key = NearKey(secret())
    assert NearKey("ed25519:" + b58encode(SEED)).public_key == key.public_key
    with pytest.raises(ValueError):
        NearKey("secp256k1:" + b58encode(SEED))


def test_transaction_layout_and_signature() -> None:
    key = NearKey(secret())
    tx = function_call_tx(
        signer_id=ACCOUNT, key=key, nonce=5, receiver_id=ACCOUNT, block_hash=bytes(32),
        method="anchor", args={"key_hash": KEY_HASH, "receipt_hash": RECEIPT},
    )  # fmt: skip
    # signer_id, public key, nonce, receiver_id, block hash, one FunctionCall action
    offset = 4 + len(ACCOUNT)
    assert tx[:offset] == struct.pack("<I", len(ACCOUNT)) + ACCOUNT.encode()
    assert tx[offset] == 0 and tx[offset + 1 : offset + 33] == key.public_bytes
    assert struct.unpack_from("<Q", tx, offset + 33)[0] == 5
    action_at = offset + 41 + 4 + len(ACCOUNT) + 32
    assert struct.unpack_from("<I", tx, action_at)[0] == 1 and tx[action_at + 4] == 2
    assert tx.endswith(struct.pack("<Q", 30 * 10**12) + bytes(16))  # 30 Tgas, zero deposit

    signed, tx_hash = sign_tx(tx, key)
    digest = hashlib.sha256(tx).digest()
    assert tx_hash == b58encode(digest)
    assert signed[: len(tx)] == tx and signed[len(tx)] == 0
    Ed25519PublicKey.from_public_bytes(key.public_bytes).verify(signed[len(tx) + 1 :], digest)


def rpc_mock(status: dict[str, object]) -> respx.Route:
    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        if body["method"] == "query":
            return httpx.Response(
                200, json={"result": {"nonce": 41, "block_hash": b58encode(bytes(32))}}
            )
        assert body["method"] == "send_tx" and body["params"]["wait_until"] == "FINAL"
        return httpx.Response(200, json={"result": {"status": status}})

    return respx.post(TESTNET_RPC).mock(side_effect=handler)


@respx.mock
def test_anchor_sends_one_signed_call_with_our_hashes() -> None:
    route = rpc_mock({"SuccessValue": ""})
    result = NearAnchor(ACCOUNT, secret()).anchor(KEY_HASH, RECEIPT)
    assert result.status == "anchored"
    assert result.url.endswith(result.tx_hash)
    sent = base64.b64decode(
        json.loads(route.calls.last.request.content)["params"]["signed_tx_base64"]
    )
    assert (
        json.dumps({"key_hash": KEY_HASH, "receipt_hash": RECEIPT}, separators=(",", ":")).encode()
        in sent
    )
    assert struct.pack("<Q", 42) in sent  # nonce = access key nonce + 1


@respx.mock
def test_second_anchor_is_reported_not_raised() -> None:
    rpc_mock(
        {"Failure": {"ActionError": {"kind": {"FunctionCallError": {"ExecutionError": PANIC}}}}}
    )
    assert NearAnchor(ACCOUNT, secret()).anchor(KEY_HASH, RECEIPT).status == "already_anchored"


@respx.mock
def test_other_failures_raise() -> None:
    rpc_mock({"Failure": {"ActionError": {"kind": "something else"}}})
    with pytest.raises(AnchorError):
        NearAnchor(ACCOUNT, secret()).anchor(KEY_HASH, RECEIPT)
