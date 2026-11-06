"""The `hushmark-verify` command."""

from __future__ import annotations

import io
from pathlib import Path

import pytest

from hushmark.config import Config
from hushmark.report import render
from hushmark.verify_receipt import extract, main
from tests.test_pipeline import replay

OUTCOME, _ = replay("r1")


def run(*argv: str) -> tuple[int, str]:
    out = io.StringIO()
    return main(list(argv), out), out.getvalue()


def test_verifies_a_receipt_file_offline(tmp_path: Path) -> None:
    receipt = tmp_path / "receipt.json"
    receipt.write_bytes(OUTCOME.receipt.body)
    code, out = run(str(receipt), "--offline")
    assert code == 0 and out.endswith("VERIFIED\n")
    assert f"receipt {OUTCOME.receipt.receipt_id}" in out
    assert "PASS  signature" in out and "skip  anchor" in out


def test_a_changed_receipt_fails_with_exit_1(tmp_path: Path) -> None:
    receipt = tmp_path / "receipt.json"
    receipt.write_bytes(OUTCOME.receipt.body.replace(b'"provider_tee"', b'"gateway"'))
    code, out = run(str(receipt), "--offline")
    assert code == 1 and "FAIL  signature" in out and out.endswith("NOT VERIFIED\n")


def test_the_check_details_can_be_pasted_as_they_are(tmp_path: Path) -> None:
    details = render(OUTCOME, Config()).text  # what GitHub shows under the check
    assert extract(details) == OUTCOME.receipt.body
    pasted = tmp_path / "details.txt"
    pasted.write_text(details)
    assert run(str(pasted), "--offline")[0] == 0


def test_stdin(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("sys.stdin", io.StringIO(OUTCOME.receipt.body.decode()))
    assert run("-", "--offline")[0] == 0


LIVE = Path(__file__).resolve().parent.parent / "fixtures" / "receipts" / "pr17.json"


def test_a_real_live_receipt_verifies_offline() -> None:
    """The receipt PR #17's live check published (fixtures/receipts/FIXTURE.md)."""
    code, out = run(str(LIVE), "--offline")
    assert code == 0, out
    assert "receipt 8baa04a2aac0786efb1b3a204db09ddbd4cdd775897c543e2aa261c42547ce36" in out
    assert "signed in the TEE by 0x3b753b4406613c5e70ae640508632b600424fa0c" in out


def test_the_website_example_is_the_same_receipt() -> None:
    site = LIVE.parent.parent.parent / "site" / "examples" / "receipt-pr17.json"
    assert site.read_bytes() == LIVE.read_bytes()
