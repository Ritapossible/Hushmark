"""Checking a receipt without trusting Hushmark, on the real R1 recording."""

from __future__ import annotations

import json
from typing import Any

import httpx
import respx

from hushmark.anchor import TESTNET_RPC
from hushmark.nonce import canonical_json
from hushmark.receipt_check import check_receipt
from tests.replay import RecordedEvidence, Recording
from tests.test_pipeline import replay

REC = Recording("r1")
OUTCOME, _ = replay("r1")
RECEIPT, ATTESTATION = OUTCOME.receipt.body, OUTCOME.attestation


def statuses(
    receipt: bytes = RECEIPT, attestation: bytes | None = ATTESTATION, **kw: Any
) -> dict[str, str]:
    kw.setdefault("sources", RecordedEvidence(REC))
    kw.setdefault("anchor_account", None)
    report = check_receipt(receipt, attestation, now=lambda: REC.meta["fetched_at"], **kw)
    return {c.name: c.status for c in report.checks}


def edited(**changes: Any) -> bytes:
    receipt = json.loads(RECEIPT)
    for path, value in changes.items():
        node = receipt
        *parents, leaf = path.split("__")
        for p in parents:
            node = node[p]
        node[leaf] = value
    return canonical_json(receipt)


def test_real_receipt_passes_every_check_offline() -> None:
    report = check_receipt(
        RECEIPT,
        ATTESTATION,
        sources=RecordedEvidence(REC),
        anchor_account=None,
        now=lambda: REC.meta["fetched_at"],
    )
    assert report.ok and report.receipt_id == OUTCOME.receipt.receipt_id
    assert {c.name: c.status for c in report.checks} == {
        "receipt_id": "pass",
        "nonce": "pass",
        "signature": "pass",
        "attestation_file": "pass",
        "attestation": "pass",
        "gpu": "pass",
        "anchor": "skipped",
    }


def test_without_the_report_only_the_receipt_is_checked() -> None:
    s = statuses(attestation=None)
    assert s["signature"] == "pass" and s["attestation"] == "skipped" and s["gpu"] == "skipped"


def test_reformatted_receipt_is_not_canonical() -> None:
    pretty = json.dumps(json.loads(RECEIPT), indent=2).encode()
    report = check_receipt(pretty, None, anchor_account=None)
    assert not report.ok and report.checks[0].status == "fail"


def test_changed_salt_breaks_the_nonce() -> None:
    assert statuses(edited(nonce_salt="00" * 16))["nonce"] == "fail"


def test_changed_response_hash_breaks_the_signature() -> None:
    assert statuses(edited(response_sha256="0" * 64))["signature"] == "fail"


def test_gateway_signature_is_refused() -> None:
    assert statuses(edited(signature__kind="gateway"))["signature"] == "fail"


def test_another_attestation_report_is_refused() -> None:
    s = statuses(attestation=ATTESTATION + b" ")
    assert s["attestation_file"] == "fail" and s["attestation"] == "skipped"


def test_garbage_is_a_failure_not_a_crash() -> None:
    report = check_receipt(b"not json", None, anchor_account=None)
    assert not report.ok and report.checks[0].status == "fail"


def rpc_returns(value: Any) -> None:
    raw = list(json.dumps(value).encode())
    respx.post(TESTNET_RPC).respond(200, json={"result": {"result": raw}})


@respx.mock
def test_anchor_holding_this_receipt_passes() -> None:
    rpc_returns({"receipt_hash": OUTCOME.receipt.receipt_id, "block_height": 1, "timestamp_ns": 2})
    assert statuses(attestation=None, anchor_account="anchor.hushmark.testnet")["anchor"] == "pass"


@respx.mock
def test_anchor_holding_another_receipt_fails() -> None:
    rpc_returns({"receipt_hash": "f" * 64, "block_height": 1, "timestamp_ns": 2})
    assert statuses(attestation=None, anchor_account="anchor.hushmark.testnet")["anchor"] == "fail"


@respx.mock
def test_no_anchor_or_no_network_is_skipped_not_failed() -> None:
    rpc_returns(None)
    assert statuses(attestation=None, anchor_account="a.testnet")["anchor"] == "skipped"
    respx.post(TESTNET_RPC).mock(side_effect=httpx.ConnectError("down"))
    s = statuses(attestation=None, anchor_account="a.testnet")
    assert s["anchor"] == "skipped"


# --- what "verified" means (audit 2026-11-08) -----------------------------------------------
# A receipt's own signature only proves that the key named inside it signed it. Any laptop key
# can do that, so without the attestation report the verdict is "signature only", never
# "verified".


def forged() -> bytes:
    """A receipt for a review that never happened, signed with a throwaway key."""
    from eth_account import Account
    from eth_account.messages import encode_defunct

    from hushmark.nonce import IdempotencyKey, derive_nonce

    r = json.loads(RECEIPT)
    r["key"]["pr"] = 999_999
    r["nonce"], _ = derive_nonce(IdempotencyKey(**r["key"]), bytes.fromhex(r["nonce_salt"]))
    r["response_sha256"] = "1" * 64
    account = Account.create()
    text = f"{r['key']['model']}:{r['request_sha256']}:{r['response_sha256']}"
    r["signature"].update(
        text=text,
        sig=account.sign_message(encode_defunct(text=text)).signature.hex(),
        signing_address=account.address,
    )
    return canonical_json(r)


def report_of(receipt: bytes, attestation: bytes | None, **kw: Any) -> Any:
    kw.setdefault("sources", RecordedEvidence(REC))
    kw.setdefault("anchor_account", None)
    return check_receipt(receipt, attestation, now=lambda: REC.meta["fetched_at"], **kw)


def test_a_laptop_signed_receipt_is_never_verified() -> None:
    report = report_of(forged(), None)
    assert not report.ok and report.verdict == "tee_not_checked"
    signature = next(c for c in report.checks if c.name == "signature")
    assert signature.status == "pass" and "TEE" not in signature.detail
    assert "address named in the receipt" in signature.detail


def test_a_laptop_signed_receipt_fails_against_a_real_attestation() -> None:
    report = report_of(forged(), ATTESTATION)
    assert not report.ok and report.verdict == "not_verified"


def test_a_real_receipt_without_its_attestation_is_signature_only() -> None:
    report = report_of(RECEIPT, None)
    assert not report.ok and report.verdict == "tee_not_checked"


def test_verified_needs_the_tee_checks() -> None:
    report = report_of(RECEIPT, ATTESTATION)
    assert report.ok and report.verdict == "verified"
    assert report.as_dict()["verdict"] == "verified"


@respx.mock
def test_a_rerun_receipt_says_another_receipt_is_the_anchored_one() -> None:
    """The contract keeps the first receipt for a review key; a re-run's receipt is genuine
    but not the anchored one. The message must say that, not suggest the TEE did not sign."""
    rpc_returns({"receipt_hash": "f" * 64, "block_height": 1, "timestamp_ns": 2})
    report = report_of(RECEIPT, ATTESTATION, anchor_account="anchor.hushmark.testnet")
    assert report.verdict == "not_anchored_receipt" and not report.ok
    anchor = next(c for c in report.checks if c.name == "anchor")
    assert anchor.status == "fail" and "a different receipt is the anchored one" in anchor.detail
    assert {c.name: c.status for c in report.checks}["attestation"] == "pass"
