"""One review, end to end: scan, excerpt, infer, verify (checks a–g), receipt.

Everything that talks to the network is passed in, so the same code runs live and replays the
recorded evidence in tests. The pipeline never decides how results look on GitHub; that is
`report.py`. Any failure becomes a `Refusal` and no model finding survives it (rule 4).
"""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Protocol

import httpx

from hushmark.excerpt import build_excerpts
from hushmark.infer import Completion, build_request, load_prompt
from hushmark.nonce import IdempotencyKey, derive_nonce, input_sha256
from hushmark.receipt import Receipt, build_receipt
from hushmark.refusal import Refused
from hushmark.scan import Candidate, ScanResult, ensure_within_cap, scan
from hushmark.verify.attestation import select_model_attestation, verify_attestation
from hushmark.verify.grounding import Grounded, ground
from hushmark.verify.nras import verify_nras
from hushmark.verify.signature import check_signature


@dataclass(frozen=True)
class PullRequestInput:
    repo_id: int
    pr: int
    base_sha: str
    head_sha: str
    diff: str
    title: str
    body: str


class Tee(Protocol):
    """NEAR AI Cloud, as the pipeline needs it."""

    def complete(self, request_bytes: bytes) -> Completion: ...
    def signature(self, chat_id: str) -> dict[str, Any]: ...
    def attestation(self, nonce: str, signing_address: str) -> bytes: ...


class EvidenceSources(Protocol):
    """Intel and NVIDIA, as the pipeline needs them."""

    def collateral(self, raw_quote: bytes) -> str: ...
    def nras(self, gpu_payload: dict[str, Any]) -> Any: ...
    def jwks(self) -> dict[str, Any]: ...


@dataclass(frozen=True)
class NoCandidates:
    scan: ScanResult


@dataclass(frozen=True)
class Refusal:
    code: str
    detail: str
    candidates: tuple[Candidate, ...]


@dataclass(frozen=True)
class Reviewed:
    candidates: tuple[Candidate, ...]
    grounded: Grounded
    receipt: Receipt
    key: IdempotencyKey
    attestation: bytes  # the report the receipt's attestation_sha256 refers to


Outcome = NoCandidates | Refusal | Reviewed


def review(
    pr: PullRequestInput,
    *,
    model: str,
    tee: Tee,
    sources: EvidenceSources,
    now: Callable[[], int],
    salt: bytes | None = None,
    boundary: str | None = None,
) -> Outcome:
    """Run one review. `salt` and `boundary` are fixed only when replaying a recording."""
    result = scan(pr.diff, pr.title, pr.body)
    if not result.candidates:
        return NoCandidates(result)  # rule 13: no model call, no cost
    try:
        return _verified_review(pr, result, model, tee, sources, now, salt, boundary)
    except Refused as e:
        return Refusal(e.code, e.detail, result.candidates)
    except (httpx.HTTPError, ValueError, KeyError) as e:
        return Refusal("tee_unavailable", f"{type(e).__name__}: {e}", result.candidates)


def _verified_review(
    pr: PullRequestInput,
    result: ScanResult,
    model: str,
    tee: Tee,
    sources: EvidenceSources,
    now: Callable[[], int],
    salt: bytes | None,
    boundary: str | None,
) -> Reviewed:
    ensure_within_cap(result)
    excerpts = build_excerpts(result, pr.title, pr.body)
    _, prompt_hash = load_prompt()
    key = IdempotencyKey(
        repo_id=pr.repo_id,
        pr=pr.pr,
        base_sha=pr.base_sha,
        head_sha=pr.head_sha,
        input_sha256=input_sha256(pr.diff, pr.title, pr.body),
        model=model,
        prompt_hash=prompt_hash,
    )

    completion = tee.complete(build_request(model, excerpts, boundary))
    signature = tee.signature(completion.chat_id)
    signer = check_signature(  # check f
        signature, model, completion.request_bytes, completion.response_bytes
    )

    nonce, nonce_salt = derive_nonce(key, salt)
    attestation_bytes = tee.attestation(nonce, signer)
    report = json.loads(attestation_bytes)
    attestation = select_model_attestation(report, signer)  # check a
    collateral = sources.collateral(bytes.fromhex(str(attestation["intel_quote"])))
    verified_at = now()
    quote = verify_attestation(report, nonce, collateral, verified_at, signer)  # checks a–e
    verify_nras(  # check e, NVIDIA's signed verdict
        sources.nras(json.loads(str(attestation["nvidia_payload"]))),
        nonce,
        sources.jwks(),
        verified_at,
    )
    grounded = ground(completion.response_bytes, result.candidates)  # check g

    receipt = build_receipt(
        key=key,
        nonce=nonce,
        nonce_salt=nonce_salt,
        request_bytes=completion.request_bytes,
        response_bytes=completion.response_bytes,
        signature=signature,
        attestation_bytes=attestation_bytes,
        tcb_status=quote.tcb_status,
        candidates=len(result.candidates),
        grounded=grounded,
        verified_at=verified_at,
        created_at=now(),
    )
    return Reviewed(result.candidates, grounded, receipt, key, attestation_bytes)
