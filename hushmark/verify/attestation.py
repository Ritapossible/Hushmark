"""Checks a–e of docs/ARCHITECTURE.md step 5: is the signer inside a genuine NEAR AI Cloud TEE?

Quote parsing and verification are done by `dcap-qvl` (ADR-0006). The checks around it are
ported from NEAR's reference verifier, but each one raises `Refused` instead of printing.
"""

from __future__ import annotations

import hashlib
import json
import struct
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

import dcap_qvl

from hushmark.refusal import Refused

# OutOfDate quotes still verify cryptographically, but we do not accept them silently.
ACCEPTED_TCB_STATUSES = frozenset({"UpToDate"})

_ECDSA_ADDRESS_LEN = 20


@dataclass(frozen=True)
class VerifiedQuote:
    tcb_status: str
    report_data: bytes
    mr_config_id: bytes
    rt_mr3: bytes


def _json_field(value: Any) -> Any:
    return json.loads(value) if isinstance(value, str) else value


def select_model_attestation(
    report: Mapping[str, Any], signing_address: str | None = None
) -> Mapping[str, Any]:
    """Check a: the report holds exactly one model attestation for this signer."""
    attestations = report.get("model_attestations")
    if not isinstance(attestations, list) or not attestations:
        raise Refused("no_attestation", "report has no model_attestations")
    if signing_address is not None:
        wanted = signing_address.lower()
        attestations = [
            a for a in attestations if str(a.get("signing_address", "")).lower() == wanted
        ]
    if len(attestations) != 1:
        raise Refused("no_attestation", f"{len(attestations)} attestations match the signer")
    attestation: Mapping[str, Any] = attestations[0]
    return attestation


def verify_quote(
    intel_quote_hex: str,
    collateral_json: str,
    now_secs: int,
    accepted_statuses: frozenset[str] = ACCEPTED_TCB_STATUSES,
) -> VerifiedQuote:
    """Check b: the Intel TDX quote verifies against the given collateral at `now_secs`."""
    try:
        raw_quote = bytes.fromhex(intel_quote_hex)
        collateral = dcap_qvl.QuoteCollateralV3.from_json(collateral_json)
        verified = dcap_qvl.verify(raw_quote, collateral, now_secs)
        result = json.loads(verified.to_json())
    except Exception as e:  # dcap-qvl raises plain exceptions for every failure
        raise Refused("quote_invalid", str(e)) from e

    status = str(result.get("status"))
    if status not in accepted_statuses:
        raise Refused("quote_invalid", f"TCB status {status}")
    report = result.get("report", {})
    td = report.get("TD10") or report.get("TD15")
    if td is None:
        raise Refused("quote_invalid", f"not a TDX report: {list(report)}")
    if bytes.fromhex(td["td_attributes"])[0] & 1:
        raise Refused("quote_invalid", "TDX debug mode is enabled")
    return VerifiedQuote(
        tcb_status=status,
        report_data=bytes.fromhex(td["report_data"]),
        mr_config_id=bytes.fromhex(td["mr_config_id"]),
        rt_mr3=bytes.fromhex(td["rt_mr3"]),
    )


def check_report_data(attestation: Mapping[str, Any], quote: VerifiedQuote, nonce_hex: str) -> None:
    """Check c: report_data = signer identity (32 bytes) ‖ our nonce, and the nonce is echoed."""
    if attestation.get("signing_algo") != "ecdsa":
        raise Refused("signer_not_bound", f"unsupported algo {attestation.get('signing_algo')}")
    identity = bytes.fromhex(str(attestation["signing_address"]).removeprefix("0x"))
    if len(identity) != _ECDSA_ADDRESS_LEN:
        raise Refused("signer_not_bound", "signing address is not 20 bytes")

    fingerprint = attestation.get("tls_cert_fingerprint")
    if fingerprint:
        bound = hashlib.sha256(identity + bytes.fromhex(fingerprint)).digest()
    else:
        bound = identity.ljust(32, b"\0")
    if quote.report_data[:32] != bound:
        raise Refused("signer_not_bound", "report_data does not bind the signing address")

    nonce = bytes.fromhex(nonce_hex)
    if len(nonce) != 32 or quote.report_data[32:64] != nonce:
        raise Refused("nonce_mismatch", "report_data does not carry our nonce")
    if str(attestation.get("request_nonce", "")).lower() != nonce_hex.lower():
        raise Refused("nonce_mismatch", "request_nonce does not echo our nonce")


def replay_rtmr3(event_log: list[Mapping[str, Any]]) -> bytes:
    """Recompute RTMR3 from the IMR 3 events, as NEAR's reference does."""
    rtmr3 = bytes(48)
    for event in event_log:
        if event.get("imr") != 3:
            continue
        digest = hashlib.sha384(
            struct.pack("<I", event["event_type"])
            + b":"
            + str(event["event"]).encode()
            + b":"
            + bytes.fromhex(event.get("event_payload") or "")
        ).digest()
        if event.get("digest") and bytes.fromhex(event["digest"]) != digest:
            raise Refused("measurement_mismatch", f"digest mismatch for event {event['event']}")
        rtmr3 = hashlib.sha384(rtmr3 + digest).digest()
    return rtmr3


def check_measurements(attestation: Mapping[str, Any], quote: VerifiedQuote) -> None:
    """Check d: MRCONFIGID commits to the published app_compose; RTMR3 replays from the log."""
    try:
        tcb_info = _json_field(attestation["info"]["tcb_info"])
        app_compose = str(tcb_info["app_compose"])
        event_log = _json_field(attestation["event_log"])
    except (KeyError, TypeError, ValueError) as e:
        raise Refused("measurement_mismatch", f"report lacks measurement data: {e}") from e

    expected = b"\x01" + hashlib.sha256(app_compose.encode()).digest() + bytes(15)
    if quote.mr_config_id != expected:
        raise Refused("measurement_mismatch", "MRCONFIGID does not match app_compose")
    if replay_rtmr3(event_log) != quote.rt_mr3:
        raise Refused("measurement_mismatch", "event log does not replay to RTMR3")


def check_gpu_nonce(attestation: Mapping[str, Any], nonce_hex: str) -> None:
    """Check e, first half: the NVIDIA GPU evidence was produced for our nonce.

    The second half (NRAS verdict and its JWT signature) needs the network and lands with
    the NRAS client (docs/PLAN.md day 7).
    """
    try:
        payload = _json_field(attestation["nvidia_payload"])
        gpu_nonce = str(payload["nonce"])
    except (KeyError, TypeError, ValueError) as e:
        raise Refused("gpu_evidence_invalid", f"no GPU evidence: {e}") from e
    if gpu_nonce.lower() != nonce_hex.lower():
        raise Refused("gpu_evidence_invalid", "GPU evidence does not carry our nonce")


def verify_attestation(
    report: Mapping[str, Any],
    nonce_hex: str,
    collateral_json: str,
    now_secs: int,
    signing_address: str | None = None,
) -> VerifiedQuote:
    """Run checks a–e (offline part) in order. Returns the verified quote or raises Refused."""
    attestation = select_model_attestation(report, signing_address)
    quote = verify_quote(str(attestation["intel_quote"]), collateral_json, now_secs)
    check_report_data(attestation, quote, nonce_hex)
    check_measurements(attestation, quote)
    check_gpu_nonce(attestation, nonce_hex)
    return quote
