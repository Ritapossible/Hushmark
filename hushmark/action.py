"""Run Hushmark as a GitHub Action on `pull_request_target` (ADR-0009).

    python -m hushmark.action

The workflow checks out Hushmark from the base branch only. The pull request is never checked
out or run: its diff, title and body arrive through the GitHub API as text. The Check Run is
posted with the workflow's own token; the receipt and its attestation report are written to
`$RUNNER_TEMP/hushmark/` for the workflow to keep as an artifact.
"""

from __future__ import annotations

import json
import os
import sys
import time
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

from hushmark.anchor import TESTNET_RPC, NearAnchor
from hushmark.github import GitHubClient
from hushmark.infer import Completion
from hushmark.near import LiveEvidence, NearAiCloud
from hushmark.nonce import key_hash
from hushmark.pipeline import EvidenceSources, Reviewed, Tee
from hushmark.refusal import Refused
from hushmark.service import CheckResult, run_check

DEFAULT_MODEL = "z-ai/glm-5.3-flash"
# Worst case per review at GLM-5.3-flash's listed price: 200 excerpt lines in, 4,096 tokens out,
# about $0.0025. 50 a day caps a repository at about $0.13 a day. Clean PRs never count.
DEFAULT_DAILY_REVIEWS = 50
RECEIPT_ARTIFACT_PREFIX = "hushmark-receipt-"


class NoKeyTee:
    """Used when NEARAI_API_KEY is absent: any review refuses instead of guessing."""

    def complete(self, request_bytes: bytes) -> Completion:
        raise Refused("tee_unavailable", "NEARAI_API_KEY is not set")

    def signature(self, chat_id: str) -> dict[str, Any]:
        raise Refused("tee_unavailable", "NEARAI_API_KEY is not set")

    def attestation(self, nonce: str, signing_address: str) -> bytes:
        raise Refused("tee_unavailable", "NEARAI_API_KEY is not set")


class BudgetedTee:
    """Refuses with `budget_exceeded` before the model call once today's reviews hit the cap.

    The Action keeps no database, so it counts today's receipt artifacts (one per reviewed run).
    The count is checked only when a review would call the model, so clean PRs cost nothing.
    """

    def __init__(self, tee: Tee, used_today: Callable[[], int], limit: int) -> None:
        self.tee, self.used_today, self.limit = tee, used_today, limit

    def complete(self, request_bytes: bytes) -> Completion:
        used = self.used_today()
        if used >= self.limit:
            raise Refused("budget_exceeded", f"{used} reviews today, limit {self.limit}")
        return self.tee.complete(request_bytes)

    def signature(self, chat_id: str) -> dict[str, Any]:
        return self.tee.signature(chat_id)

    def attestation(self, nonce: str, signing_address: str) -> bytes:
        return self.tee.attestation(nonce, signing_address)


def near_anchor(env: Mapping[str, str]) -> Callable[[Reviewed], str] | None:
    """Anchor on NEAR when NEAR_ANCHOR_ACCOUNT and NEAR_ANCHOR_KEY are configured."""
    account, secret = env.get("NEAR_ANCHOR_ACCOUNT"), env.get("NEAR_ANCHOR_KEY")
    if not account or not secret:
        return None
    client = NearAnchor(account, secret, rpc=env.get("NEAR_RPC_URL") or TESTNET_RPC)

    def anchor(outcome: Reviewed) -> str:
        result = client.anchor(key_hash(outcome.key), outcome.receipt.receipt_id)
        if result.status == "already_anchored":
            return "NEAR anchor: this review was already anchored; the contract refused a second."
        return f"Anchored on NEAR testnet: [{result.tx_hash[:12]}…]({result.url})"

    return anchor


def run(
    event: Mapping[str, Any],
    env: Mapping[str, str],
    gh: GitHubClient | None = None,
    tee: Tee | None = None,
    sources: EvidenceSources | None = None,
) -> CheckResult:
    pull = event["pull_request"]
    repo = event["repository"]
    model = env.get("HUSHMARK_MODEL") or DEFAULT_MODEL
    key = env.get("NEARAI_API_KEY")
    gh = gh or GitHubClient(env["GITHUB_TOKEN"])
    owner, name = str(repo["owner"]["login"]), str(repo["name"])
    limit = int(env.get("HUSHMARK_DAILY_REVIEWS") or DEFAULT_DAILY_REVIEWS)
    midnight = time.strftime("%Y-%m-%dT00:00:00Z", time.gmtime())
    budgeted = BudgetedTee(
        tee or (NearAiCloud(key, model) if key else NoKeyTee()),
        lambda: gh.reviews_since(owner, name, midnight, RECEIPT_ARTIFACT_PREFIX),
        limit,
    )
    result = run_check(
        gh,
        owner=owner,
        repo=name,
        repo_id=int(repo["id"]),
        number=int(pull["number"]),
        model=model,
        tee=budgeted,
        sources=sources or LiveEvidence(),
        now=lambda: int(time.time()),
        anchor=near_anchor(env),
    )
    out_dir = env.get("RUNNER_TEMP")
    if out_dir and isinstance(result.outcome, Reviewed):
        save_receipt(result.outcome, Path(out_dir) / "hushmark")
    return result


def save_receipt(outcome: Reviewed, out: Path) -> None:
    """Receipts hold hashes only (RECEIPT.md); the attestation is kept beside it by hash."""
    out.mkdir(parents=True, exist_ok=True)
    (out / f"receipt-{outcome.receipt.receipt_id}.json").write_bytes(outcome.receipt.body)
    (out / "attestation.json").write_bytes(outcome.attestation)


def main() -> int:
    event = json.loads(Path(os.environ["GITHUB_EVENT_PATH"]).read_text())
    result = run(event, os.environ)
    print(f"Hushmark: {result.output.conclusion}: {result.output.title}")
    # The Check Run carries the verdict; the job itself only fails if Hushmark itself failed.
    return 0


if __name__ == "__main__":
    sys.exit(main())
