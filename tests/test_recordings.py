"""Real recordings R1–R3 verified offline (fixtures 01, 04, 05, 06, 07, 10 in docs/FIXTURES.md).

Each failure case changes one thing in a copy of real evidence and names that change.
"""

from __future__ import annotations

import copy
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

from hushmark.nonce import IdempotencyKey, derive_nonce
from hushmark.refusal import Refused
from hushmark.verify.attestation import verify_attestation
from hushmark.verify.signature import check_signature
from tests.conftest import FIXTURES, AttestationFixture


@dataclass
class Recording:
    request: bytes
    response: bytes
    signature: dict[str, Any]
    report: dict[str, Any]
    collateral_json: str
    meta: dict[str, Any]

    @classmethod
    def load(cls, name: str) -> Recording:
        root: Path = FIXTURES / "recordings" / name
        return cls(
            request=(root / "request.json").read_bytes(),
            response=(root / "response.json").read_bytes(),
            signature=json.loads((root / "signature.json").read_text()),
            report=json.loads((root / "attestation.json").read_bytes()),
            collateral_json=(root / "collateral.json").read_text(),
            meta=json.loads((root / "meta.json").read_text()),
        )

    def verify(self, report: dict[str, Any] | None = None, nonce: str | None = None) -> None:
        signer = check_signature(self.signature, self.meta["model"], self.request, self.response)
        verify_attestation(
            self.report if report is None else report,
            self.meta["nonce"] if nonce is None else nonce,
            self.collateral_json,
            self.meta["fetched_at"],
            signer,
        )

    def findings(self) -> list[dict[str, Any]]:
        content = json.loads(self.response)["choices"][0]["message"]["content"]
        found: list[dict[str, Any]] = json.loads(content)["findings"]
        return found


@pytest.mark.parametrize("name", ["r1", "r2", "r3"])
def test_recording_verifies_end_to_end(name: str) -> None:
    Recording.load(name).verify()


@pytest.mark.parametrize("name", ["r1", "r2", "r3"])
def test_nonce_is_derived_from_the_idempotency_key(name: str) -> None:
    meta = Recording.load(name).meta
    key = IdempotencyKey(**meta["key"])
    assert derive_nonce(key, bytes.fromhex(meta["nonce_salt"])) == (
        meta["nonce"],
        meta["nonce_salt"],
    )


def test_request_carries_no_tools() -> None:
    for name in ["r1", "r2", "r3"]:
        assert "tools" not in json.loads(Recording.load(name).request)


def test_fixture_01_injection_has_two_findings() -> None:
    rec = Recording.load("r1")
    assert sorted(f["candidate_id"] for f in rec.findings()) == ["c1", "c2"]
    assert rec.meta["candidates"] == ["c1", "c2"]


def test_fixture_07_harmless_todo_has_no_findings() -> None:
    assert Recording.load("r2").findings() == []


def test_fixture_10_rules_file_has_one_finding() -> None:
    assert [f["candidate_id"] for f in Recording.load("r3").findings()] == ["c1"]


def test_fixture_04_attestation_removed_is_refused() -> None:
    rec = Recording.load("r1")
    with pytest.raises(Refused) as e:
        rec.verify(report={k: v for k, v in rec.report.items() if k != "model_attestations"})
    assert e.value.code == "no_attestation"


def test_fixture_05_one_changed_response_byte_is_refused() -> None:
    rec = Recording.load("r1")
    tampered = bytearray(rec.response)
    tampered[tampered.index(b"high")] = ord("H")  # exactly one byte of the answer changed
    with pytest.raises(Refused) as e:
        check_signature(rec.signature, rec.meta["model"], rec.request, bytes(tampered))
    assert e.value.code == "signature_mismatch"


def test_fixture_06_nonce_swap_is_refused() -> None:
    # R1's evidence checked against a report fetched for the same signer with another nonce.
    rec = Recording.load("r1")
    a2 = AttestationFixture("glm-a2")
    with pytest.raises(Refused) as e:
        verify_attestation(a2.report, rec.meta["nonce"], a2.collateral_json, a2.fetched_at)
    assert e.value.code == "nonce_mismatch"


def test_gateway_signature_is_not_enough() -> None:
    rec = Recording.load("r1")
    sig = dict(rec.signature, signature_kind="gateway")
    with pytest.raises(Refused) as e:
        check_signature(sig, rec.meta["model"], rec.request, rec.response)
    assert e.value.code == "signature_mismatch"


def test_signature_from_another_key_is_refused() -> None:
    rec = Recording.load("r1")
    other = Recording.load("r2")
    sig = copy.deepcopy(rec.signature)
    sig["signature"] = other.signature["signature"]
    with pytest.raises(Refused) as e:
        check_signature(sig, rec.meta["model"], rec.request, rec.response)
    assert e.value.code == "signature_mismatch"
