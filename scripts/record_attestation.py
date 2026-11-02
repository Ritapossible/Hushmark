"""Record a real NEAR AI Cloud attestation report as a fixture. No API key needed.

    uv run python scripts/record_attestation.py \
        --model Qwen/Qwen3.8-27B --out fixtures/attestation/a1

Saves the report's exact bytes, the nonce we sent, the Intel collateral, and the time the
evidence was fetched, so tests can verify it offline later (docs/FIXTURES.md).
"""

from __future__ import annotations

import argparse
import asyncio
import json
import secrets
import time
from pathlib import Path

import dcap_qvl
import httpx

REPORT_URL = "https://cloud-api.near.ai/v1/attestation/report"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--model", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    nonce = secrets.token_hex(32)
    r = httpx.get(
        REPORT_URL,
        params={"model": args.model, "nonce": nonce, "signing_algo": "ecdsa"},
        headers={"Accept-Encoding": "identity"},
        timeout=60,
    )
    r.raise_for_status()
    fetched_at = int(time.time())
    report = r.json()
    quote = bytes.fromhex(report["model_attestations"][0]["intel_quote"])
    collateral = asyncio.run(dcap_qvl.get_collateral_from_pcs(quote))

    (out / "report.json").write_bytes(r.content)
    (out / "collateral.json").write_text(collateral.to_json())
    (out / "meta.json").write_text(
        json.dumps({"model": args.model, "nonce": nonce, "fetched_at": fetched_at}, indent=2) + "\n"
    )
    (out / "FIXTURE.md").write_text(
        f"# Real attestation evidence\n\n"
        f"Recorded unedited from NEAR AI Cloud for `{args.model}` at unix time {fetched_at}, "
        f"with a fresh random nonce, by `scripts/record_attestation.py`. No API key was "
        f"used. Intel collateral was fetched from Intel PCS at the same time.\n"
    )
    print(f"recorded {args.model} -> {out}")


if __name__ == "__main__":
    main()
