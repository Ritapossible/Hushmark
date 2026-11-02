"""Record real NEAR AI Cloud evidence for fixture pull requests R1–R3 (docs/FIXTURES.md).

    NEARAI_API_KEY=... uv run python scripts/record_completion.py \
        --model z-ai/glm-5.3-flash --out out/ fixtures/inputs/r1 fixtures/inputs/r2 ...

For each input it runs the real pipeline up to step 5: scan, excerpts, one completion, then
the signature, the attestation for that signer with our derived nonce, Intel collateral and
the NVIDIA NRAS response. Everything is verified before it is saved, so evidence that does
not verify never becomes a fixture. Runs on GitHub Actions (.github/workflows/record.yml).
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import sys
import time
from dataclasses import asdict
from pathlib import Path
from typing import Any

import dcap_qvl
import httpx
from eth_account import Account
from eth_account.messages import encode_defunct

from hushmark.excerpt import build_excerpts
from hushmark.infer import BASE_URL, build_request, complete, load_prompt
from hushmark.nonce import IdempotencyKey, derive_nonce, input_sha256, key_hash
from hushmark.scan import ensure_within_cap, scan
from hushmark.verify.attestation import select_model_attestation, verify_attestation

NRAS_URL = "https://nras.attestation.nvidia.com/v3/attest/gpu"


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def fetch_signature(http: httpx.Client, chat_id: str, model: str) -> dict[str, Any]:
    for _ in range(10):
        r = http.get(f"/signature/{chat_id}", params={"model": model, "signing_algo": "ecdsa"})
        if r.status_code == 200 and "signature" in r.json():
            body: dict[str, Any] = r.json()
            return body
        time.sleep(2)
    raise SystemExit(f"no signature for {chat_id}: HTTP {r.status_code} {r.text[:200]}")


def record(http: httpx.Client, model: str, src: Path, out: Path) -> None:
    diff = (src / "diff.patch").read_text()
    title = (src / "title.txt").read_text()
    body = (src / "body.txt").read_text()
    meta = json.loads((src / "meta.json").read_text())

    result = scan(diff, title, body)
    ensure_within_cap(result)
    excerpts = build_excerpts(result, title, body)
    _, prompt_hash = load_prompt()
    key = IdempotencyKey(
        repo_id=meta["repo_id"],
        pr=meta["pr"],
        base_sha=meta["base_sha"],
        head_sha=meta["head_sha"],
        input_sha256=input_sha256(diff, title, body),
        model=model,
        prompt_hash=prompt_hash,
    )

    completion = complete(http, build_request(model, excerpts))
    sig = fetch_signature(http, completion.chat_id, model)
    expected = (
        f"{model}:{sha256_hex(completion.request_bytes)}:{sha256_hex(completion.response_bytes)}"
    )
    if sig.get("signature_kind") != "provider_tee" or sig["text"] != expected:
        raise SystemExit(f"{src.name}: signature does not cover our bytes: {sig}")
    signer = Account.recover_message(encode_defunct(text=sig["text"]), signature=sig["signature"])
    if signer.lower() != str(sig["signing_address"]).lower():
        raise SystemExit(f"{src.name}: signer {signer} != {sig['signing_address']}")

    nonce, salt = derive_nonce(key)
    r = http.get(
        "/attestation/report",
        params={
            "model": model,
            "nonce": nonce,
            "signing_algo": "ecdsa",
            "signing_address": sig["signing_address"],
        },
    )
    r.raise_for_status()
    report = r.json()
    attestation = select_model_attestation(report, sig["signing_address"])
    raw_quote = bytes.fromhex(attestation["intel_quote"])
    collateral_json = asyncio.run(dcap_qvl.get_collateral_from_pcs(raw_quote)).to_json()
    fetched_at = int(time.time())
    verify_attestation(report, nonce, collateral_json, fetched_at, sig["signing_address"])
    nras = httpx.post(NRAS_URL, json=json.loads(attestation["nvidia_payload"]), timeout=60)

    out.mkdir(parents=True, exist_ok=True)
    (out / "request.json").write_bytes(completion.request_bytes)
    (out / "response.json").write_bytes(completion.response_bytes)
    (out / "signature.json").write_text(json.dumps(sig, indent=2) + "\n")
    (out / "attestation.json").write_bytes(r.content)
    (out / "collateral.json").write_text(collateral_json)
    (out / "nras.json").write_bytes(nras.content)
    (out / "meta.json").write_text(
        json.dumps(
            {
                "model": model,
                "chat_id": completion.chat_id,
                "key": asdict(key),
                "key_hash": key_hash(key),
                "nonce": nonce,
                "nonce_salt": salt,
                "signing_address": sig["signing_address"],
                "fetched_at": fetched_at,
                "candidates": [c.id for c in result.candidates],
                "nras_http_status": nras.status_code,
            },
            indent=2,
        )
        + "\n"
    )
    content = json.loads(completion.response_bytes)["choices"][0]["message"].get("content")
    print(f"{src.name}: verified and saved. Model answer: {content}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--model", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("inputs", nargs="+")
    args = parser.parse_args()

    key = os.environ.get("NEARAI_API_KEY")
    if not key:
        sys.exit("set NEARAI_API_KEY")
    headers = {"Authorization": f"Bearer {key}", "Accept-Encoding": "identity"}
    timeout = httpx.Timeout(300, connect=30)
    with httpx.Client(base_url=BASE_URL, headers=headers, timeout=timeout) as http:
        for src in map(Path, args.inputs):
            record(http, args.model, src, Path(args.out) / src.name)


if __name__ == "__main__":
    main()
