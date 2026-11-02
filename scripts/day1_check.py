"""Day-one go/no-go check (docs/PLAN.md).

Answers one question with a real key: does a NEAR AI Cloud completion carry a
`provider_tee` signature that recovers to a signing address bound into a valid
TDX quote with our fresh nonce?

Not part of the hushmark package. Modelled on nearai-cloud-verifier
(py/chat_verifier.py, py/model_verifier.py), but stops on the first failure.

Run:
    NEARAI_API_KEY=... uv run --with httpx --with eth-account --with dcap-qvl==0.7.0 \
        scripts/day1_check.py --model Qwen/Qwen3.8-27B

Raw evidence goes to .evidence/day1/ (git-ignored). Exit code 0 means go.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import secrets
import sys
import time
from pathlib import Path
from typing import Any

import dcap_qvl
import httpx
from eth_account import Account
from eth_account.messages import encode_defunct

BASE_URL = "https://cloud-api.near.ai/v1"
NRAS_URL = "https://nras.attestation.nvidia.com/v3/attest/gpu"


class CheckFailed(Exception):
    pass


def check(ok: bool, label: str, detail: str = "") -> None:
    print(f"{'PASS' if ok else 'FAIL'}  {label}{f'  ({detail})' if detail else ''}")
    if not ok:
        raise CheckFailed(label)


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def fetch_signature(http: httpx.Client, chat_id: str, model: str) -> dict[str, Any]:
    # The signature can lag the response briefly; retry a few times, then give up.
    for _ in range(5):
        r = http.get(f"/signature/{chat_id}", params={"model": model, "signing_algo": "ecdsa"})
        if r.status_code == 200:
            body: dict[str, Any] = r.json()
            if "signature" in body:
                return body
        time.sleep(2)
    raise CheckFailed(f"no signature for {chat_id} (last HTTP {r.status_code}: {r.text[:200]})")


async def verify_quote(quote_hex: str, out: Path) -> tuple[str, bytes]:
    raw_quote = bytes.fromhex(quote_hex)
    collateral = await dcap_qvl.get_collateral_from_pcs(raw_quote)
    (out / "collateral.json").write_text(collateral.to_json())
    now = int(time.time())
    (out / "verified_at.txt").write_text(str(now))
    # Offline path: the same call judges will run later against saved collateral.
    verified = dcap_qvl.verify(raw_quote, collateral, now)
    report = json.loads(verified.to_json())["report"]
    td = report.get("TD10") or report.get("TD15")
    if td is None:
        raise CheckFailed(f"unexpected quote report type: {list(report)}")
    return str(verified.status), bytes.fromhex(td["report_data"].removeprefix("0x"))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--model", required=True, help="canonical model id, no alias")
    parser.add_argument("--out", default=".evidence/day1")
    args = parser.parse_args()

    api_key = os.environ.get("NEARAI_API_KEY")
    if not api_key:
        print("set NEARAI_API_KEY")
        return 2
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    headers = {"Authorization": f"Bearer {api_key}", "Accept-Encoding": "identity"}
    # Model TEEs can take minutes on a cold start; a slow answer is not a failed check.
    timeout = httpx.Timeout(300, connect=30)
    with httpx.Client(base_url=BASE_URL, headers=headers, timeout=timeout) as http:
        # 1. One completion. Serialize once and keep the exact bytes we sent.
        request_bytes = json.dumps(
            {
                "model": args.model,
                "messages": [{"role": "user", "content": "Reply with the single word: ok"}],
                "temperature": 0,
                "max_tokens": 8,
                "stream": False,
            },
            separators=(",", ":"),
        ).encode()
        r = http.post(
            "/chat/completions",
            content=request_bytes,
            headers={"Content-Type": "application/json", "x-no-aliasing": "true"},
        )
        check(r.status_code == 200, "completion returned 200", f"HTTP {r.status_code}: {r.text[:200]}")
        response_bytes = r.content
        (out / "request.bin").write_bytes(request_bytes)
        (out / "response.bin").write_bytes(response_bytes)
        chat_id = json.loads(response_bytes)["id"]

        # 2. Signature over model:sha256(request):sha256(response).
        sig = fetch_signature(http, chat_id, args.model)
        (out / "signature.json").write_text(json.dumps(sig, indent=2))
        kind = sig.get("signature_kind")
        check(kind == "provider_tee", "signature_kind is provider_tee", f"got {kind!r}")
        expected_text = f"{args.model}:{sha256_hex(request_bytes)}:{sha256_hex(response_bytes)}"
        check(sig["text"] == expected_text, "signed text covers our exact bytes",
              f"expected {expected_text!r}, got {sig['text']!r}")
        signer = Account.recover_message(encode_defunct(text=sig["text"]), signature=sig["signature"])
        address = str(sig["signing_address"])
        check(signer.lower() == address.lower(), "EIP-191 signer equals signing_address", signer)

        # 3. Attestation for that signer, with a fresh nonce.
        nonce = secrets.token_hex(32)
        r = http.get(
            "/attestation/report",
            params={"model": args.model, "nonce": nonce, "signing_algo": "ecdsa", "signing_address": address},
        )
        check(r.status_code == 200, "attestation report returned 200", f"HTTP {r.status_code}")
        (out / "attestation.json").write_bytes(r.content)
        report = r.json()
        candidates = [
            a for a in report.get("model_attestations", [report])
            if str(a.get("signing_address", "")).lower() == address.lower()
        ]
        check(len(candidates) == 1, "exactly one model attestation for this signer", f"found {len(candidates)}")
        att = candidates[0]

    # 4. TDX quote, and report_data = padded signer || nonce.
    status, report_data = asyncio.run(verify_quote(att["intel_quote"], out))
    check(status in {"UpToDate", "OutOfDate"}, "TDX quote verifies", f"TCB status {status}")
    check(not att.get("tls_cert_fingerprint"), "no TLS binding in this report (not requested)")
    expected = bytes.fromhex(address.removeprefix("0x")).ljust(32, b"\0") + bytes.fromhex(nonce)
    check(report_data[:64] == expected, "report_data binds signer and our nonce")
    check(str(att.get("request_nonce", "")).lower() == nonce, "request_nonce echoes our nonce")

    # 5. GPU evidence carries our nonce; NVIDIA's verdict is recorded.
    #    The NRAS JWT signature is NOT verified here; that is day 7 (docs/OPEN_QUESTIONS.md).
    gpu = json.loads(att["nvidia_payload"])
    check(str(gpu.get("nonce", "")).lower() == nonce, "GPU evidence carries our nonce")
    nras = httpx.post(NRAS_URL, json=gpu, timeout=60)
    (out / "nras.json").write_bytes(nras.content)
    check(nras.status_code == 200, "NVIDIA NRAS returned 200", f"HTTP {nras.status_code}")
    print(f"INFO  NRAS response saved to {out / 'nras.json'} (verdict checked on day 7)")

    print(f"\nGO. TCB status {status}. Evidence in {out}/")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except CheckFailed as e:
        print(f"\nNO-GO at: {e}")
        sys.exit(1)
