"""The whole pipeline on real recorded evidence (fixtures 01, 05, 07, 09, 10, 11, 13)."""

from __future__ import annotations

from typing import Any

import httpx
import pytest

from hushmark.infer import Completion
from hushmark.pipeline import NoCandidates, PullRequestInput, Refusal, Reviewed, review
from tests.replay import RecordedEvidence, RecordedTee, Recording
from tests.test_scan import make_diff

MODEL = "z-ai/glm-5.3-flash"


def replay(name: str, response: bytes | None = None) -> tuple[Any, RecordedTee]:
    rec = Recording(name)
    tee = RecordedTee(rec, response)
    outcome = review(
        rec.pr(),
        model=MODEL,
        tee=tee,
        sources=RecordedEvidence(rec),
        now=lambda: rec.meta["fetched_at"],
        salt=rec.salt(),
        boundary=rec.boundary(),
    )
    return outcome, tee


@pytest.mark.parametrize(("name", "findings"), [("r1", 2), ("r2", 0), ("r3", 1), ("r4", 0)])
def test_recorded_review_verifies_end_to_end(name: str, findings: int) -> None:
    outcome, tee = replay(name)
    assert isinstance(outcome, Reviewed), outcome
    assert len(outcome.grounded.findings) == findings
    assert tee.calls == 1


def test_receipt_key_matches_the_recording() -> None:
    outcome, _ = replay("r1")
    assert isinstance(outcome, Reviewed)
    assert outcome.key.__dict__ == Recording("r1").meta["key"]


def test_changed_response_byte_is_refused() -> None:
    rec = Recording("r1")
    tampered = bytearray(rec.response)
    tampered[tampered.index(b"high")] = ord("H")
    outcome, _ = replay("r1", bytes(tampered))
    assert isinstance(outcome, Refusal) and outcome.code == "signature_mismatch"
    assert len(outcome.candidates) == 2  # shown as unconfirmed, never as findings


class NoCallTee:
    def complete(self, request_bytes: bytes) -> Completion:
        raise AssertionError("no model call expected")

    def signature(self, chat_id: str) -> dict[str, Any]:
        raise AssertionError

    def attestation(self, nonce: str, signing_address: str) -> bytes:
        raise AssertionError


def pr(diff: str) -> PullRequestInput:
    return PullRequestInput(1, 1, "a" * 40, "b" * 40, diff, "t", "")


def test_no_hidden_regions_means_no_model_call() -> None:
    diff = make_diff("src/app.py", [f"x_{i} = {i}" for i in range(500)])
    outcome = review(pr(diff), model=MODEL, tee=NoCallTee(), sources=None, now=lambda: 0)  # type: ignore[arg-type]
    assert isinstance(outcome, NoCandidates)


def test_too_many_regions_is_refused_without_a_model_call() -> None:
    diff = make_diff("a.md", [f"<!-- {i} -->" for i in range(21)])
    outcome = review(pr(diff), model=MODEL, tee=NoCallTee(), sources=None, now=lambda: 0)  # type: ignore[arg-type]
    assert isinstance(outcome, Refusal) and outcome.code == "too_many_candidates"


class DownTee(NoCallTee):
    def complete(self, request_bytes: bytes) -> Completion:
        raise httpx.ConnectError("NEAR AI Cloud unreachable")


def test_unreachable_tee_is_a_refusal_not_a_crash() -> None:
    diff = make_diff("a.md", ["<!-- hello -->"])
    outcome = review(pr(diff), model=MODEL, tee=DownTee(), sources=None, now=lambda: 0)  # type: ignore[arg-type]
    assert isinstance(outcome, Refusal) and outcome.code == "tee_unavailable"
