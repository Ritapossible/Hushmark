"""Step 8: anchor a receipt hash on NEAR (ADR-0004).

Signs one `FunctionCall` to the anchor contract's `anchor(key_hash, receipt_hash)` with a
function-call access key that can call only that method, attaches no deposit, and sends it over
NEAR RPC. A failed anchor never blocks the Check Run; the caller reports it and moves on.
"""

from __future__ import annotations

import base64
import hashlib
import json
import struct
from dataclasses import dataclass
from typing import Any

import httpx
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

TESTNET_RPC = "https://rpc.testnet.near.org"
EXPLORER = "https://testnet.nearblocks.io/txns/"
ANCHOR_GAS = 30 * 10**12  # 30 Tgas
_FUNCTION_CALL = 2  # NEAR Action enum index
_ED25519 = 0
_B58 = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"


def b58encode(data: bytes) -> str:
    n = int.from_bytes(data, "big")
    out = ""
    while n:
        n, r = divmod(n, 58)
        out = _B58[r] + out
    return "1" * (len(data) - len(data.lstrip(b"\0"))) + out


def b58decode(text: str) -> bytes:
    n = 0
    for ch in text:
        if ch not in _B58:
            raise ValueError("not base58")  # never echo the text: it may be a secret key
        n = n * 58 + _B58.index(ch)
    body = n.to_bytes((n.bit_length() + 7) // 8, "big") if n else b""
    return b"\0" * (len(text) - len(text.lstrip("1"))) + body


def _u32(v: int) -> bytes:
    return struct.pack("<I", v)


def _u64(v: int) -> bytes:
    return struct.pack("<Q", v)


def _u128(v: int) -> bytes:
    return v.to_bytes(16, "little")


def _string(s: str) -> bytes:
    raw = s.encode()
    return _u32(len(raw)) + raw


class NearKey:
    """An ed25519 key in NEAR's `ed25519:<base58>` form (64 bytes: seed then public key)."""

    def __init__(self, secret: str) -> None:
        # Secrets pasted into a settings page often carry a trailing newline or spaces.
        kind, _, encoded = secret.strip().partition(":")
        raw = b58decode(encoded)
        if kind != "ed25519" or len(raw) not in (32, 64):
            raise ValueError("expected an ed25519:<base58> NEAR secret key")
        self._key = Ed25519PrivateKey.from_private_bytes(raw[:32])
        self.public_bytes = self._key.public_key().public_bytes_raw()

    @property
    def public_key(self) -> str:
        return "ed25519:" + b58encode(self.public_bytes)

    def sign(self, message: bytes) -> bytes:
        return self._key.sign(message)


def function_call_tx(
    *,
    signer_id: str,
    key: NearKey,
    nonce: int,
    receiver_id: str,
    block_hash: bytes,
    method: str,
    args: dict[str, Any],
    gas: int = ANCHOR_GAS,
    deposit: int = 0,
) -> bytes:
    """Borsh-encode a Transaction with one FunctionCall action."""
    return (
        _string(signer_id)
        + bytes([_ED25519])
        + key.public_bytes
        + _u64(nonce)
        + _string(receiver_id)
        + block_hash
        + _u32(1)
        + bytes([_FUNCTION_CALL])
        + _string(method)
        + _u32(len(raw := json.dumps(args, separators=(",", ":")).encode()))
        + raw
        + _u64(gas)
        + _u128(deposit)
    )


def sign_tx(tx: bytes, key: NearKey) -> tuple[bytes, str]:
    """Return (signed transaction bytes, transaction hash in base58)."""
    digest = hashlib.sha256(tx).digest()
    return tx + bytes([_ED25519]) + key.sign(digest), b58encode(digest)


@dataclass(frozen=True)
class AnchorResult:
    status: str  # anchored | already_anchored
    tx_hash: str

    @property
    def url(self) -> str:
        return EXPLORER + self.tx_hash


class AnchorError(Exception):
    pass


class NearAnchor:
    def __init__(
        self,
        account_id: str,
        secret_key: str,
        rpc: str = TESTNET_RPC,
        http: httpx.Client | None = None,
    ) -> None:
        self.account_id = account_id
        self.key = NearKey(secret_key)
        self.http = http or httpx.Client(timeout=60)
        self.rpc = rpc

    def _call(self, method: str, params: Any) -> Any:
        r = self.http.post(
            self.rpc, json={"jsonrpc": "2.0", "id": "hushmark", "method": method, "params": params}
        )
        r.raise_for_status()
        body = r.json()
        if "error" in body:
            raise AnchorError(json.dumps(body["error"])[:500])
        return body["result"]

    def anchor(self, key_hash: str, receipt_hash: str) -> AnchorResult:
        access = self._call(
            "query",
            {
                "request_type": "view_access_key",
                "finality": "final",
                "account_id": self.account_id,
                "public_key": self.key.public_key,
            },
        )
        tx = function_call_tx(
            signer_id=self.account_id,
            key=self.key,
            nonce=int(access["nonce"]) + 1,
            receiver_id=self.account_id,  # the contract lives on the anchor account itself
            block_hash=b58decode(str(access["block_hash"])),
            method="anchor",
            args={"key_hash": key_hash, "receipt_hash": receipt_hash},
        )
        signed, tx_hash = sign_tx(tx, self.key)
        result = self._call(
            "send_tx",
            {"signed_tx_base64": base64.b64encode(signed).decode(), "wait_until": "FINAL"},
        )
        status = result.get("status", {})
        if "SuccessValue" in status:
            return AnchorResult("anchored", tx_hash)
        if "already anchored" in json.dumps(status):
            return AnchorResult("already_anchored", tx_hash)
        raise AnchorError(f"anchor transaction failed: {json.dumps(status)[:300]}")
