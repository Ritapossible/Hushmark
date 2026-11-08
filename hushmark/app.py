"""The GitHub App: turn one verified webhook delivery into at most one review (ADR-0010).

`server.py` checks the delivery's signature, answers GitHub at once, and hands the payload
here. Everything below runs the same `service.run_check` as the GitHub Action, so both paths
give the same Check Run, receipt and anchor.

Triggers:
- `pull_request` opened, synchronize, reopened or edited: review the pull request.
- `issue_comment` created on a pull request whose whole body is `/hushmark`: re-run, but only
  for someone with admin or maintain permission (`not_maintainer` otherwise, and nothing is
  posted, so a stranger cannot spend the budget or change the check).
"""

from __future__ import annotations

import threading
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any

from hushmark.action import DEFAULT_DAILY_REVIEWS, DEFAULT_MODEL, NoKeyTee, near_anchor
from hushmark.github import GitHubApp, GitHubClient
from hushmark.infer import Completion
from hushmark.near import LiveEvidence, NearAiCloud
from hushmark.pipeline import EvidenceSources, Tee
from hushmark.refusal import Refused
from hushmark.service import CheckResult, may_rerun, run_check

PULL_REQUEST_ACTIONS = frozenset({"opened", "synchronize", "reopened", "edited"})
# All installations share one NEAR AI key: about $1 a day at most (action.DEFAULT_DAILY_REVIEWS).
DEFAULT_TOTAL_DAILY_REVIEWS = 100
RERUN_COMMAND = "/hushmark"


@dataclass(frozen=True)
class Job:
    installation_id: int
    owner: str
    repo: str
    repo_id: int
    number: int
    trigger: str  # "pull_request.<action>" or "rerun"
    requested_by: str | None = None  # the commenter, for a re-run
    requested_by_bot: bool = False

    @property
    def key(self) -> tuple[int, int]:
        """One pending review per pull request: a queued job already reads the latest head."""
        return (self.repo_id, self.number)


def route(event: str, payload: Mapping[str, Any]) -> Job | None:
    """The review this delivery asks for, or None when it asks for nothing."""
    installation = payload.get("installation") or {}
    repository = payload.get("repository") or {}
    if not installation.get("id") or not repository.get("id"):
        return None
    installation_id = int(installation["id"])
    owner, repo = str(repository["owner"]["login"]), str(repository["name"])
    repo_id = int(repository["id"])
    action = str(payload.get("action", ""))

    if event == "pull_request" and action in PULL_REQUEST_ACTIONS:
        number = int(payload["pull_request"]["number"])
        return Job(installation_id, owner, repo, repo_id, number, f"pull_request.{action}")

    if event == "issue_comment" and action == "created":
        issue = payload.get("issue") or {}
        comment = payload.get("comment") or {}
        body = str(comment.get("body") or "")
        if "pull_request" not in issue or body.strip() != RERUN_COMMAND:
            return None
        user = comment.get("user") or {}
        return Job(
            installation_id,
            owner,
            repo,
            repo_id,
            int(issue["number"]),
            "rerun",
            requested_by=str(user.get("login", "")),
            requested_by_bot=str(user.get("type", "")) == "Bot",
        )
    return None


class DailyBudget:
    """Model-calling reviews per repository, and in total, per UTC day, kept in memory.

    The App keeps no database (ADR-0010), so the count starts again if the server restarts.
    Clean pull requests never reach the model, so they never count. Every installation spends
    the same NEAR AI key, so `total_limit` caps all repositories together.
    """

    def __init__(
        self,
        limit: int,
        today: Callable[[], str] | None = None,
        total_limit: int | None = None,
    ) -> None:
        self.limit, self.total_limit = limit, total_limit
        self._today = today or (lambda: time.strftime("%Y-%m-%d", time.gmtime()))
        self._counts: dict[tuple[str, int], int] = {}
        self._lock = threading.Lock()

    def spend(self, repo_id: int) -> None:
        """Count one model call, or refuse with `budget_exceeded` before it is made."""
        key = (self._today(), repo_id)
        with self._lock:
            self._counts = {k: v for k, v in self._counts.items() if k[0] == key[0]}
            used = self._counts.get(key, 0)
            if used >= self.limit:
                raise Refused("budget_exceeded", f"{used} reviews today, limit {self.limit}")
            total = sum(self._counts.values())
            if self.total_limit is not None and total >= self.total_limit:
                raise Refused("budget_exceeded", f"{total} reviews today across repositories")
            self._counts[key] = used + 1


class SpendingTee:
    """Counts each model call against the daily budget, refusing before the call when spent."""

    def __init__(self, tee: Tee, budget: DailyBudget, repo_id: int) -> None:
        self.tee, self.budget, self.repo_id = tee, budget, repo_id

    def complete(self, request_bytes: bytes) -> Completion:
        self.budget.spend(self.repo_id)
        return self.tee.complete(request_bytes)

    def signature(self, chat_id: str) -> dict[str, Any]:
        return self.tee.signature(chat_id)

    def attestation(self, nonce: str, signing_address: str) -> bytes:
        return self.tee.attestation(nonce, signing_address)


class HushmarkApp:
    """Everything a review needs, built once when the server starts."""

    def __init__(
        self,
        github: GitHubApp,
        env: Mapping[str, str],
        tee: Tee | None = None,
        sources: EvidenceSources | None = None,
        budget: DailyBudget | None = None,
    ) -> None:
        self.github = github
        self.model = env.get("HUSHMARK_MODEL") or DEFAULT_MODEL
        key = env.get("NEARAI_API_KEY")
        self.tee: Tee = tee or (NearAiCloud(key, self.model) if key else NoKeyTee())
        self.sources = sources or LiveEvidence()
        self.budget = budget or DailyBudget(
            int(env.get("HUSHMARK_DAILY_REVIEWS") or DEFAULT_DAILY_REVIEWS),
            total_limit=int(env.get("HUSHMARK_TOTAL_DAILY_REVIEWS") or DEFAULT_TOTAL_DAILY_REVIEWS),
        )
        self.anchor = near_anchor(env)

    def handle(self, job: Job, gh: GitHubClient | None = None) -> CheckResult | None:
        """Run one review. Returns None when a re-run is refused (`not_maintainer`)."""
        gh = gh or self.github.installation(job.installation_id)
        if job.trigger == "rerun":
            try:
                may_rerun(gh, job.owner, job.repo, job.requested_by or "", job.requested_by_bot)
            except Refused as e:
                if e.code != "not_maintainer":
                    raise
                return None
        return run_check(
            gh,
            owner=job.owner,
            repo=job.repo,
            repo_id=job.repo_id,
            number=job.number,
            model=self.model,
            tee=SpendingTee(self.tee, self.budget, job.repo_id),
            sources=self.sources,
            now=lambda: int(time.time()),
            anchor=self.anchor,
        )
