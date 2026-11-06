"""Check a Hushmark receipt without trusting Hushmark (RECEIPT.md, "Verify a receipt").

Used by the MCP server's `verify_receipt` tool and the public verifier (docs/UPGRADES.md #4).
Every check reports pass, fail or skipped, and why; nothing here trusts the receipt's own
claims. The receipt holds hashes only, so the model's request and response bytes cannot be
re-hashed here; what is checked is that the signature covers those hashes and that the
attested TEE made it.

1. `receipt_id`: the SHA-256 of the receipt's canonical bytes, and the bytes are canonical.
2. `nonce`: recomputed from the key and `nonce_salt`.
3. `signature` (check f): `provider_tee`, over `model:request_sha256:response_sha256`,
   recovering to `signing_address`.
4. `attestation_file`: the report's SHA-256 is `attestation_sha256`.
5. `attestation` (checks a–d): the Intel quote with fresh collateral, signer and nonce bound,
   measurements replayed. Evidence is checked as of now, not as of the review.
6. `gpu` (check e): NVIDIA's signed verdict for that nonce.
7. `anchor`: the NEAR contract holds this receipt's hash for this key. A different receipt
   anchored for the same key fails (one input, one anchored verdict); no anchor, or no
   network, is skipped.
"""

from __future__ import annotations

import hashlib
import json
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from eth_account import Account
from eth_account.messages import encode_defunct

from hushmark.anchor import TESTNET_RPC, lookup
from hushmark.nonce import IdempotencyKey, canonical_json, derive_nonce, key_hash
from hushmark.pipeline import EvidenceSources
from hushmark.refusal import Refused
from hushmark.verify.attestation import select_model_attestation, verify_attestation
from hushmark.verify.nras import verify_nras

DEFAULT_ANCHOR_ACCOUNT = "anchor.hushmark.testnet"


@dataclass(frozen=True)
class Check:
    name: str
    status: str  # pass | fail | skipped
    detail: str


@dataclass(frozen=True)
class ReceiptReport:
    receipt_id: str
    checks: tuple[Check, ...]

    @property
    def ok(self) -> bool:
        """True when nothing failed and the receipt's own checks (1–3) passed."""
        by_name = {c.name: c.status for c in self.checks}
        core = all(by_name.get(n) == "pass" for n in ("receipt_id", "nonce", "signature"))
        return core and all(c.status != "fail" for c in self.checks)

    def as_dict(self) -> dict[str, Any]:
        return {
            "receipt_id": self.receipt_id,
            "ok": self.ok,
            "checks": [
                {"name": c.name, "status": c.status, "detail": c.detail} for c in self.checks
            ],
        }


def _run(name: str, fn: Callable[[], str]) -> Check:
    try:
        return Check(name, "pass", fn())
    except Refused as e:
        return Check(name, "fail", e.code)
    except Exception as e:  # malformed input of any kind is a failure, never a crash
        return Check(name, "fail", type(e).__name__)


def check_receipt(
    receipt_bytes: bytes,
    attestation_bytes: bytes | None = None,
    *,
    sources: EvidenceSources | None = None,
    anchor_account: str | None = DEFAULT_ANCHOR_ACCOUNT,
    rpc: str = TESTNET_RPC,
    now: Callable[[], int] = lambda: int(time.time()),
) -> ReceiptReport:
    """Run every check that the inputs allow. `sources=None` skips the online TEE checks."""
    receipt_id = hashlib.sha256(receipt_bytes).hexdigest()
    checks: list[Check] = []
    try:
        receipt: dict[str, Any] = json.loads(receipt_bytes)
        key = IdempotencyKey(**receipt["key"])
    except Exception as e:
        return ReceiptReport(receipt_id, (Check("receipt_id", "fail", type(e).__name__),))

    def canonical() -> str:
        if canonical_json(receipt) != receipt_bytes:
            raise Refused("receipt_not_canonical", "")
        return f"receipt_id {receipt_id}"

    def nonce() -> str:
        expected, _ = derive_nonce(key, bytes.fromhex(str(receipt["nonce_salt"])))
        if expected != receipt["nonce"]:
            raise Refused("nonce_mismatch", "")
        return "nonce = SHA-256(key ‖ salt)"

    def signature() -> str:
        sig = receipt["signature"]
        text = f"{key.model}:{receipt['request_sha256']}:{receipt['response_sha256']}"
        if sig.get("kind") != "provider_tee" or sig.get("algo") != "ecdsa":
            raise Refused("signature_mismatch", "")
        if sig.get("text") != text:
            raise Refused("signature_mismatch", "")
        signer = Account.recover_message(encode_defunct(text=text), signature=str(sig["sig"]))
        if signer.lower() != str(sig["signing_address"]).lower():
            raise Refused("signature_mismatch", "")
        return f"signed in the TEE by {sig['signing_address']}"

    checks += [_run("receipt_id", canonical), _run("nonce", nonce), _run("signature", signature)]

    if attestation_bytes is None:
        checks.append(Check("attestation_file", "skipped", "no attestation report given"))
    else:

        def attestation_file() -> str:
            if hashlib.sha256(attestation_bytes).hexdigest() != receipt["attestation_sha256"]:
                raise Refused("attestation_mismatch", "")
            return "the report is the one the receipt names"

        checks.append(_run("attestation_file", attestation_file))

    if attestation_bytes is None or sources is None or checks[-1].status != "pass":
        reason = "needs the attestation report and network access"
        checks += [Check("attestation", "skipped", reason), Check("gpu", "skipped", reason)]
    else:
        report = json.loads(attestation_bytes)
        signer = str(receipt["signature"]["signing_address"])

        def attestation() -> str:
            quote_hex = str(select_model_attestation(report, signer)["intel_quote"])
            collateral = sources.collateral(bytes.fromhex(quote_hex))
            quote = verify_attestation(report, receipt["nonce"], collateral, now(), signer)
            return f"Intel TDX quote {quote.tcb_status}; signer and nonce bound; measurements match"

        def gpu() -> str:
            payload = json.loads(str(select_model_attestation(report, signer)["nvidia_payload"]))
            verify_nras(sources.nras(payload), receipt["nonce"], sources.jwks(), now())
            return "NVIDIA attested every GPU for this nonce"

        checks += [_run("attestation", attestation), _run("gpu", gpu)]

    if anchor_account is None:
        checks.append(Check("anchor", "skipped", "no anchor account given"))
    else:
        try:
            found = lookup(anchor_account, key_hash(key), rpc)
        except Exception as e:  # unreachable RPC: say so, never call it a failure
            checks.append(Check("anchor", "skipped", f"NEAR RPC unavailable ({type(e).__name__})"))
        else:
            if found is None:
                checks.append(Check("anchor", "skipped", "no anchor for this review key"))
            elif found.get("receipt_hash") != receipt_id:
                # One input, one anchored verdict: a re-run's receipt is not the anchored one.
                checks.append(Check("anchor", "fail", "anchor_mismatch"))
            else:
                block = found.get("block_height")
                checks.append(
                    Check("anchor", "pass", f"anchored on {anchor_account}, block {block}")
                )

    return ReceiptReport(receipt_id, tuple(checks))
