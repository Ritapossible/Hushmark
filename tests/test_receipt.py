"""Receipts built from a real recording: canonical, reproducible, and free of any content."""

from __future__ import annotations

import hashlib
import json

from hushmark.nonce import IdempotencyKey, canonical_json
from hushmark.receipt import Receipt, build_receipt
from hushmark.verify.grounding import ground
from tests.conftest import FIXTURES
from tests.test_grounding import candidates


def r1_receipt(created_at: int = 1793617500) -> Receipt:
    root = FIXTURES / "recordings" / "r1"
    meta = json.loads((root / "meta.json").read_text())
    response = (root / "response.json").read_bytes()
    return build_receipt(
        key=IdempotencyKey(**meta["key"]),
        nonce=meta["nonce"],
        nonce_salt=meta["nonce_salt"],
        request_bytes=(root / "request.json").read_bytes(),
        response_bytes=response,
        signature=json.loads((root / "signature.json").read_text()),
        attestation_bytes=(root / "attestation.json").read_bytes(),
        tcb_status="UpToDate",
        candidates=2,
        grounded=ground(response, candidates("r1")),
        verified_at=meta["fetched_at"],
        created_at=created_at,
    )


def test_receipt_id_is_the_hash_of_canonical_bytes() -> None:
    receipt = r1_receipt()
    assert receipt.receipt_id == hashlib.sha256(receipt.body).hexdigest()
    assert canonical_json(json.loads(receipt.body)) == receipt.body


def test_same_inputs_give_the_same_receipt() -> None:
    assert r1_receipt().receipt_id == r1_receipt().receipt_id
    assert r1_receipt().receipt_id != r1_receipt(created_at=1).receipt_id


def test_receipt_has_exactly_the_v1_fields() -> None:
    body = json.loads(r1_receipt().body)
    assert set(body) == {
        "v", "key", "nonce_salt", "nonce", "request_sha256", "response_sha256", "signature",
        "attestation_sha256", "verification", "scan", "findings_sha256", "findings_count",
        "rejected_ungrounded", "created_at",
    }  # fmt: skip
    assert body["findings_count"] == 2
    assert body["signature"]["kind"] == "provider_tee"


def test_receipt_holds_no_content() -> None:
    # RECEIPT.md: never the diff, excerpts, title, body or finding text.
    text = r1_receipt().body.decode()
    inputs = FIXTURES / "inputs" / "r1"
    for leak in [
        "curl",
        "make install",
        "security team",
        (inputs / "title.txt").read_text(),
        "Hidden HTML comment",
        "docs/setup.md",
    ]:
        assert leak not in text, leak
