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
