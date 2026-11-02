"""The idempotency key and the attestation nonce derived from it (ADR-0003, RECEIPT.md)."""

from __future__ import annotations

import hashlib
import json
import secrets
from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class IdempotencyKey:
    repo_id: int
    pr: int
    base_sha: str
    head_sha: str
    input_sha256: str
    model: str
    prompt_hash: str


def canonical_json(value: object) -> bytes:
    """RFC 8785 (JCS) for the values receipts use: strings, integers, lists and objects.

    For those types JCS is sorted keys, no whitespace and UTF-8 output. Floats are refused,
    because their JCS form differs from Python's and receipts never need them.
    """

    def no_floats(v: object) -> None:
        if isinstance(v, float):
            raise TypeError("canonical_json does not accept floats")
        if isinstance(v, dict):
            for item in v.values():
                no_floats(item)
        elif isinstance(v, list):
            for item in v:
                no_floats(item)

    no_floats(value)
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def input_sha256(diff: str, title: str, body: str) -> str:
    """Hash of everything scanned: diff ‖ 0x00 ‖ title ‖ 0x00 ‖ body, all UTF-8."""
    return hashlib.sha256(
        diff.encode() + b"\x00" + title.encode() + b"\x00" + body.encode()
    ).hexdigest()


def key_hash(key: IdempotencyKey) -> str:
    """What goes on chain: no repository names, only a hash of the key."""
    return hashlib.sha256(canonical_json(asdict(key))).hexdigest()


def derive_nonce(key: IdempotencyKey, salt: bytes | None = None) -> tuple[str, str]:
    """Return (nonce_hex, salt_hex). Fresh 16-byte salt per run unless one is given."""
    salt = salt if salt is not None else secrets.token_bytes(16)
    nonce = hashlib.sha256(canonical_json(asdict(key)) + salt).hexdigest()
    return nonce, salt.hex()
