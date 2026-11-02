"""One pull request, from Check Run start to finish. The webhook server calls this."""

from __future__ import annotations

from collections.abc import Callable

from hushmark.config import Config, parse_config
from hushmark.github import GitHubClient
from hushmark.pipeline import EvidenceSources, PullRequestInput, Refusal, Tee, review
from hushmark.refusal import Refused
from hushmark.report import CheckOutput, render

MAINTAINER_ROLES = frozenset({"admin", "maintain"})


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
) -> CheckOutput:
    """Start the Check Run first, so the PR shows Hushmark is working, then finish it.

    `salt` and `boundary` are fixed only when replaying a recording.
    """
    pull = gh.pull(owner, repo, number)
    base_sha, head_sha = str(pull["base"]["sha"]), str(pull["head"]["sha"])
    check_id = gh.start_check(owner, repo, head_sha)
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
        )
        outcome = review(
            pr, model=model, tee=tee, sources=sources, now=now, salt=salt, boundary=boundary
        )
        out = render(outcome, config)
    except Refused as e:  # before review: config or diff
        out = render(Refusal(e.code, e.detail, ()), Config())
    gh.finish_check(owner, repo, check_id, out)
    return out
