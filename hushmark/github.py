"""A small GitHub App client: only the calls Hushmark needs, with the permissions in ADR-0007.

Contents read (the pinned diff, `.hushmark.yml` at the base commit), pull requests read,
checks write. Nothing here can push, comment or change settings.
"""

from __future__ import annotations

import hashlib
import hmac
import time
from typing import Any

import httpx
import jwt

from hushmark.refusal import Refused
from hushmark.report import CHECK_NAME, CheckOutput

API = "https://api.github.com"
API_VERSION = "2022-11-28"


def verify_webhook(secret: bytes, body: bytes, signature_header: str | None) -> None:
    """Raise unless `X-Hub-Signature-256` is GitHub's HMAC of this exact body."""
    expected = "sha256=" + hmac.new(secret, body, hashlib.sha256).hexdigest()
    if not signature_header or not hmac.compare_digest(expected, signature_header):
        raise Refused("webhook_invalid", "bad X-Hub-Signature-256")


class GitHubApp:
    """Authenticates as the app, then hands out per-installation clients."""

    def __init__(self, app_id: str, private_key_pem: str, http: httpx.Client | None = None):
        self.app_id = app_id
        self.private_key_pem = private_key_pem
        self.http = http or httpx.Client(base_url=API, timeout=30)

    def app_jwt(self, now: int | None = None) -> str:
        now = int(time.time()) if now is None else now
        # GitHub allows at most 10 minutes; backdate a minute for clock drift.
        claims = {"iat": now - 60, "exp": now + 540, "iss": self.app_id}
        return jwt.encode(claims, self.private_key_pem, algorithm="RS256")

    def installation(self, installation_id: int) -> GitHubClient:
        r = self.http.post(
            f"/app/installations/{installation_id}/access_tokens",
            headers={
                "Authorization": f"Bearer {self.app_jwt()}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": API_VERSION,
            },
        )
        r.raise_for_status()
        return GitHubClient(str(r.json()["token"]), self.http)


class GitHubClient:
    def __init__(self, token: str, http: httpx.Client | None = None) -> None:
        self.http = http or httpx.Client(base_url=API, timeout=30)
        self.headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": API_VERSION,
        }

    def _get(self, path: str, accept: str | None = None, **params: str) -> httpx.Response:
        headers = dict(self.headers, Accept=accept) if accept else self.headers
        return self.http.get(path, headers=headers, params=params)

    def pull(self, owner: str, repo: str, number: int) -> dict[str, Any]:
        r = self._get(f"/repos/{owner}/{repo}/pulls/{number}")
        r.raise_for_status()
        pull: dict[str, Any] = r.json()
        return pull

    def diff(self, owner: str, repo: str, base_sha: str, head_sha: str) -> str:
        """The diff between two pinned commits. Refuses rather than scanning part of it."""
        r = self._get(
            f"/repos/{owner}/{repo}/compare/{base_sha}...{head_sha}",
            accept="application/vnd.github.diff",
        )
        if r.status_code != 200:
            raise Refused("diff_unavailable", f"compare returned HTTP {r.status_code}")
        return r.text

    def file_at(self, owner: str, repo: str, path: str, ref: str) -> str | None:
        r = self._get(
            f"/repos/{owner}/{repo}/contents/{path}", accept="application/vnd.github.raw", ref=ref
        )
        if r.status_code == 404:
            return None
        r.raise_for_status()
        return r.text

    def role(self, owner: str, repo: str, login: str) -> str:
        r = self._get(f"/repos/{owner}/{repo}/collaborators/{login}/permission")
        if r.status_code == 404:
            return "none"
        r.raise_for_status()
        return str(r.json().get("role_name", "none"))

    def start_check(self, owner: str, repo: str, head_sha: str) -> int:
        r = self.http.post(
            f"/repos/{owner}/{repo}/check-runs",
            headers=self.headers,
            json={"name": CHECK_NAME, "head_sha": head_sha, "status": "in_progress"},
        )
        r.raise_for_status()
        return int(r.json()["id"])

    def finish_check(self, owner: str, repo: str, check_run_id: int, out: CheckOutput) -> None:
        r = self.http.patch(
            f"/repos/{owner}/{repo}/check-runs/{check_run_id}",
            headers=self.headers,
            json={
                "status": "completed",
                "conclusion": out.conclusion,
                "output": {
                    "title": out.title,
                    "summary": out.summary,
                    "annotations": out.annotations,
                },
            },
        )
        r.raise_for_status()
