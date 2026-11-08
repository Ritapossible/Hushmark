"""Verify a Hushmark receipt from the command line, without trusting Hushmark (UPGRADES #4).

    python -m hushmark.verify_receipt receipt.json [attestation.json] [--offline]
    hushmark-verify receipt.json [attestation.json] [--offline]

The receipt is in every `Hushmark` check's details, and in the Action's `hushmark-receipt-pr<N>`
artifact together with its attestation report. Use `-` to read the receipt from stdin.

Each check prints pass, fail or skipped with why (see `receipt_check.py`). With the attestation
report and network access, Intel's quote and NVIDIA's GPU verdict are checked as of now, and
the NEAR testnet anchor is looked up. Exit status: 0 if the receipt verifies (the TEE checks
included), 1 if any check fails, 2 on bad usage, 3 if nothing failed but the TEE was not
checked: the signature then only matches the address written in the receipt.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import TextIO

from hushmark.near import LiveEvidence
from hushmark.receipt_check import DEFAULT_ANCHOR_ACCOUNT, ReceiptReport, check_receipt

MARK = {"pass": "PASS", "fail": "FAIL", "skipped": "skip"}
LAST_LINE = {
    "verified": "VERIFIED",
    "not_verified": "NOT VERIFIED",
    "tee_not_checked": "SIGNATURE ONLY: the TEE was not checked",
    "not_anchored_receipt": "NOT THE ANCHORED RECEIPT: a different receipt is anchored",
}
EXIT = {"verified": 0, "not_verified": 1, "not_anchored_receipt": 1, "tee_not_checked": 3}


def extract(text: str) -> bytes:
    """Accept the bare receipt, or the check's whole details text with the ```json block."""
    if "```json" in text:
        text = text.split("```json", 1)[1].split("```", 1)[0]
    return text.strip().encode()


def show(report: ReceiptReport, out: TextIO) -> None:
    out.write(f"receipt {report.receipt_id}\n")
    for c in report.checks:
        out.write(f"  {MARK[c.status]}  {c.name:<16} {c.detail}\n")
    out.write(LAST_LINE[report.verdict] + "\n")


def main(argv: list[str] | None = None, out: TextIO = sys.stdout) -> int:
    parser = argparse.ArgumentParser(prog="hushmark-verify", description=__doc__.split("\n")[0])
    parser.add_argument("receipt", help="receipt JSON file, or - for stdin")
    parser.add_argument("attestation", nargs="?", help="the attestation report the receipt names")
    parser.add_argument("--offline", action="store_true", help="skip Intel, NVIDIA and NEAR")
    parser.add_argument("--anchor-account", default=DEFAULT_ANCHOR_ACCOUNT)
    args = parser.parse_args(argv)

    text = sys.stdin.read() if args.receipt == "-" else Path(args.receipt).read_text()
    attestation = Path(args.attestation).read_bytes() if args.attestation else None
    report = check_receipt(
        extract(text),
        attestation,
        sources=None if args.offline else LiveEvidence(),
        anchor_account=None if args.offline else args.anchor_account,
    )
    show(report, out)
    return EXIT[report.verdict]


if __name__ == "__main__":
    sys.exit(main())
