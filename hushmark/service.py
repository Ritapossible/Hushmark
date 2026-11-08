"""One pull request, from Check Run start to finish. The webhook server calls this."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, replace

import httpx

from hushmark.config import Config, parse_config
from hushmark.github import GitHubClient
from hushmark.infer import MAX_TOKENS
from hushmark.pipeline import (
    EvidenceSources,
    Outcome,
    PullRequestInput,
    Refusal,
    Reviewed,
    Tee,
    review,
)
from hushmark.refusal import Refused
from hushmark.report import CheckOutput, render

MAINTAINER_ROLES = frozenset({"admin", "maintain"})
UNKNOWN_MODE = Config(mode="block")


@dataclass(frozen=True)
class CheckResult:
    output: CheckOutput
    outcome: Outcome


def load_config(gh: GitHubClient, owner: str, repo: str, base_sha: str) -> Config:
    """Rule 12: read `.hushmark.yml` at the base commit only, never the PR head."""
    return parse_config(gh.file_at(owner, repo, ".hushmark.yml", base_sha))


def may_rerun(gh: GitHubClient, owner: str, repo: str, login: str, is_bot: bool) -> None:
    """A `/hushmark` re-run needs admin or maintain permission."""
    if is_bot or gh.role(owner, repo, login) not in MAINTAINER_ROLES:
        raise Refused("not_maintainer", f"{login} may not re-run Hushmark")


def run_check(
    gh: GitHubClient,
    *,
    owner: str,
    repo: str,
    repo_id: int,
    number: int,
    model: str,
    tee: Tee,
    sources: EvidenceSources,
    now: Callable[[], int],
    salt: bytes | None = None,
    boundary: str | None = None,
    max_tokens: int = MAX_TOKENS,
    anchor: Callable[[Reviewed], str] | None = None,
) -> CheckResult:
    """Start the Check Run first, so the PR shows Hushmark is working, then finish it.

    `salt`, `boundary` and `max_tokens` are fixed only when replaying a recording. `anchor`, if
    given, records a verified review's receipt on NEAR and returns a line for the summary; it
    never blocks the check (ADR-0004).
    """
    pull = gh.pull(owner, repo, number)
    base_sha, head_sha = str(pull["base"]["sha"]), str(pull["head"]["sha"])
    check_id = gh.start_check(owner, repo, head_sha)
    # Until the base branch's config is read, the mode is unknown: fail closed as block, so a
    # refusal before the review never passes a repository that blocks.
    config = UNKNOWN_MODE
    try:
        config = load_config(gh, owner, repo, base_sha)
        pr = PullRequestInput(
            repo_id=repo_id,
            pr=number,
            base_sha=base_sha,
            head_sha=head_sha,
            diff=gh.diff(owner, repo, base_sha, head_sha),
            title=str(pull.get("title") or ""),
            body=str(pull.get("body") or ""),
            ignore=config.ignore,
        )
        outcome = review(
            pr,
            model=model,
            tee=tee,
            sources=sources,
            now=now,
            salt=salt,
            boundary=boundary,
            max_tokens=max_tokens,
        )
    except Refused as e:  # before review: config or diff
        outcome = Refusal(e.code, e.detail, ())
    except httpx.HTTPError as e:  # GitHub failed mid-fetch: nothing was reviewed
        outcome = Refusal("diff_unavailable", type(e).__name__, ())
    except Exception:
        # Never leave the Check Run stuck "in progress": close it as not verified, then let
        # the job fail so the error is visible in the Actions log.
        gh.finish_check(owner, repo, check_id, render(Refusal("internal_error", "", ()), config))
        raise
    out = render(outcome, config)
    if anchor is not None and isinstance(outcome, Reviewed):
        out = replace(out, summary=out.summary + "\n\n" + _anchor_note(anchor, outcome))
    gh.finish_check(owner, repo, check_id, out)
    return CheckResult(out, outcome)


def _anchor_note(anchor: Callable[[Reviewed], str], outcome: Reviewed) -> str:
    try:
        return anchor(outcome)
    except Exception as e:  # any failure: publish anyway, say so (ADR-0004)
        return (
            f"NEAR anchor: not recorded this time ({type(e).__name__}). The receipt is still valid."
        )
