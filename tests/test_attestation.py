"""Checks a–e against real NEAR AI Cloud evidence (fixtures/attestation/a1, a2).

Each failure case changes one thing in a copy of the real evidence and names that change.
"""

from __future__ import annotations

import copy
import json
from typing import Any

import pytest

from hushmark.refusal import Refused
from hushmark.verify.attestation import (
    check_gpu_nonce,
    check_measurements,
    check_report_data,
    verify_attestation,
    verify_quote,
)
from tests.conftest import AttestationFixture

ONE_YEAR = 365 * 24 * 3600


def refused_code(fx: AttestationFixture, report: dict[str, Any], nonce: str | None = None) -> str:
    with pytest.raises(Refused) as e:
        verify_attestation(report, nonce or fx.nonce, fx.collateral_json, fx.fetched_at)
    return e.value.code


def test_real_evidence_passes_checks_a_to_e(a1: AttestationFixture) -> None:
    quote = verify_attestation(a1.report, a1.nonce, a1.collateral_json, a1.fetched_at)
    assert quote.tcb_status == "UpToDate"
    assert quote.report_data[32:] == bytes.fromhex(a1.nonce)


def test_second_recording_also_passes(a2: AttestationFixture) -> None:
    verify_attestation(a2.report, a2.nonce, a2.collateral_json, a2.fetched_at)


def test_signer_filter_selects_the_attested_signer(a1: AttestationFixture) -> None:
    signer = a1.attestation["signing_address"].upper().replace("0X", "0x")
    verify_attestation(a1.report, a1.nonce, a1.collateral_json, a1.fetched_at, signer)


def test_nonce_swap_is_refused(a1: AttestationFixture, a2: AttestationFixture) -> None:
    # A1's real report, checked against the nonce we sent for A2: a replayed report.
    assert refused_code(a1, a1.report, nonce=a2.nonce) == "nonce_mismatch"


def test_missing_attestation_is_refused(a1: AttestationFixture) -> None:
    assert refused_code(a1, {"gateway_attestation": {}}) == "no_attestation"


def test_unknown_signer_is_refused(a1: AttestationFixture) -> None:
    with pytest.raises(Refused) as e:
        verify_attestation(a1.report, a1.nonce, a1.collateral_json, a1.fetched_at, "0x" + "11" * 20)
    assert e.value.code == "no_attestation"


def test_flipped_quote_byte_is_refused(a1: AttestationFixture) -> None:
    report = copy.deepcopy(a1.report)
    quote = bytearray.fromhex(report["model_attestations"][0]["intel_quote"])
    quote[600] ^= 0x01  # inside the signed TD report body
    report["model_attestations"][0]["intel_quote"] = quote.hex()
    assert refused_code(a1, report) == "quote_invalid"


def test_expired_collateral_is_refused(a1: AttestationFixture) -> None:
    att = a1.attestation
    with pytest.raises(Refused) as e:
        verify_quote(att["intel_quote"], a1.collateral_json, a1.fetched_at + ONE_YEAR)
    assert e.value.code == "quote_invalid"


def test_status_outside_allowlist_is_refused(a1: AttestationFixture) -> None:
    with pytest.raises(Refused) as e:
        verify_quote(a1.attestation["intel_quote"], a1.collateral_json, a1.fetched_at, frozenset())
    assert e.value.code == "quote_invalid"


def test_different_signing_address_is_not_bound(a1: AttestationFixture) -> None:
    quote = verify_quote(a1.attestation["intel_quote"], a1.collateral_json, a1.fetched_at)
    att = dict(a1.attestation, signing_address="0x" + "22" * 20)
    with pytest.raises(Refused) as e:
        check_report_data(att, quote, a1.nonce)
    assert e.value.code == "signer_not_bound"


def test_changed_app_compose_is_refused(a1: AttestationFixture) -> None:
    quote = verify_quote(a1.attestation["intel_quote"], a1.collateral_json, a1.fetched_at)
    att = copy.deepcopy(a1.attestation)
    info = att["info"]
    tcb = json.loads(info["tcb_info"]) if isinstance(info["tcb_info"], str) else info["tcb_info"]
    tcb["app_compose"] += " "
    info["tcb_info"] = tcb
    with pytest.raises(Refused) as e:
        check_measurements(att, quote)
    assert e.value.code == "measurement_mismatch"


def test_changed_event_log_is_refused(a1: AttestationFixture) -> None:
    quote = verify_quote(a1.attestation["intel_quote"], a1.collateral_json, a1.fetched_at)
    att = copy.deepcopy(a1.attestation)
    event = next(e for e in att["event_log"] if e.get("imr") == 3 and e.get("event_payload"))
    event["event_payload"] = "00" + event["event_payload"]
    with pytest.raises(Refused) as e:
        check_measurements(att, quote)
    assert e.value.code == "measurement_mismatch"


def test_gpu_evidence_for_another_nonce_is_refused(
    a1: AttestationFixture, a2: AttestationFixture
) -> None:
    with pytest.raises(Refused) as e:
        check_gpu_nonce(a1.attestation, a2.nonce)
    assert e.value.code == "gpu_evidence_invalid"
