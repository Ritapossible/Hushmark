"""Step 6: the receipt (RECEIPT.md v1). Hashes only: never code, excerpts or finding text."""

from __future__ import annotations

import hashlib
from collections.abc import Mapping
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from typing import Any

from hushmark.nonce import IdempotencyKey, canonical_json
from hushmark.scan import DETECTORS_VERSION
from hushmark.verify.grounding import Grounded

CHECKS = ["a", "b", "c", "d", "e", "f", "g"]


@dataclass(frozen=True)
class Receipt:
    body: bytes  # canonical JSON
    receipt_id: str


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _rfc3339(unix_secs: int) -> str:
    return datetime.fromtimestamp(unix_secs, UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def findings_digest(grounded: Grounded) -> str:
    """Hash of the findings, so a published finding can be matched to its receipt."""
    rows = [
        {
            "candidate_id": f.candidate.id,
            "severity": f.severity,
            "rationale_sha256": _sha256(f.rationale.encode()),
        }
        for f in sorted(grounded.findings, key=lambda f: f.candidate.id)
    ]
    return _sha256(canonical_json(rows))


def build_receipt(
    *,
    key: IdempotencyKey,
    nonce: str,
    nonce_salt: str,
    request_bytes: bytes,
    response_bytes: bytes,
    signature: Mapping[str, Any],
    attestation_bytes: bytes,
    tcb_status: str,
    candidates: int,
    grounded: Grounded,
    verified_at: int,
    created_at: int,
) -> Receipt:
    """Build the canonical receipt. Only call after checks a–g have all passed."""
    body = {
        "v": 1,
        "key": asdict(key),
        "nonce_salt": nonce_salt,
        "nonce": nonce,
        "request_sha256": _sha256(request_bytes),
        "response_sha256": _sha256(response_bytes),
        "signature": {
            "text": signature["text"],
            "sig": signature["signature"],
            "signing_address": signature["signing_address"],
            "algo": signature["signing_algo"],
            "kind": signature["signature_kind"],
        },
        "attestation_sha256": _sha256(attestation_bytes),
        "verification": {
            "tcb_status": tcb_status,
            "checks": CHECKS,
            "verified_at": _rfc3339(verified_at),
        },
        "scan": {"detectors_version": DETECTORS_VERSION, "candidates": candidates},
        "findings_sha256": findings_digest(grounded),
        "findings_count": len(grounded.findings),
        "rejected_ungrounded": grounded.rejected_ungrounded,
        "created_at": _rfc3339(created_at),
    }
    raw = canonical_json(body)
    return Receipt(raw, _sha256(raw))
