"""Check e, second half: NVIDIA's signed verdict, verified offline with pinned keys."""

from __future__ import annotations

import copy
import json
from typing import Any

import pytest

from hushmark.refusal import Refused
from hushmark.verify.nras import verify_nras
from tests.conftest import FIXTURES

JWKS: dict[str, Any] = json.loads((FIXTURES / "nvidia" / "jwks.json").read_text())


def load(name: str) -> tuple[Any, str, int]:
    root = FIXTURES / "recordings" / name
    meta = json.loads((root / "meta.json").read_text())
    return json.loads((root / "nras.json").read_text()), meta["nonce"], meta["fetched_at"]


def code_of(response: Any, nonce: str, now: int, jwks: dict[str, Any] = JWKS) -> str:
    with pytest.raises(Refused) as e:
        verify_nras(response, nonce, jwks, now)
    return e.value.code


@pytest.mark.parametrize("name", ["r1", "r2", "r3", "r4"])
def test_recorded_verdict_verifies(name: str) -> None:
    response, nonce, at = load(name)
    claims = verify_nras(response, nonce, JWKS, at)
    assert claims["x-nvidia-overall-att-result"] is True


def test_verdict_for_another_nonce_is_refused() -> None:
    response, _, at = load("r1")
    _, other_nonce, _ = load("r2")
    assert code_of(response, other_nonce, at) == "gpu_evidence_invalid"


def test_swapped_gpu_token_is_refused() -> None:
    # GPU-0's token from another recording: validly signed, but not the one committed to.
    response, nonce, at = load("r1")
    other, _, _ = load("r2")
    tampered = copy.deepcopy(response)
    tampered[1]["GPU-0"] = other[1]["GPU-0"]
    assert code_of(tampered, nonce, at) == "gpu_evidence_invalid"


def test_changed_overall_token_is_refused() -> None:
    response, nonce, at = load("r1")
    header, payload, sig = response[0][1].split(".")
    tampered = copy.deepcopy(response)
    tampered[0][1] = ".".join(
        [header, payload[:-2] + ("A" if payload[-2] != "A" else "B") + payload[-1], sig]
    )
    assert code_of(tampered, nonce, at) == "gpu_evidence_invalid"


def test_expired_verdict_is_refused() -> None:
    response, nonce, at = load("r1")
    assert code_of(response, nonce, at + 2 * 3600) == "gpu_evidence_invalid"


def test_unknown_signing_key_is_refused() -> None:
    response, nonce, at = load("r1")
    assert code_of(response, nonce, at, jwks={"keys": []}) == "gpu_evidence_invalid"


def test_unexpected_layout_is_refused() -> None:
    _, nonce, at = load("r1")
    assert code_of({"not": "nras"}, nonce, at) == "gpu_evidence_invalid"
