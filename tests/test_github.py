"""The GitHub client and one full Check Run, against a mocked GitHub API (fixtures 02, 12)."""

from __future__ import annotations

import hashlib
import hmac
import json

import httpx
import jwt
import pytest
import respx
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from hushmark.github import API, GitHubApp, GitHubClient, verify_webhook
from hushmark.refusal import Refused
from hushmark.service import load_config, may_rerun, run_check
from tests.replay import RecordedEvidence, RecordedTee, Recording

OWNER, REPO = "acme", "widgets"
BASE = f"{API}/repos/{OWNER}/{REPO}"


def client() -> GitHubClient:
    return GitHubClient("ghs_test", httpx.Client(base_url=API))


def test_webhook_signature_is_checked() -> None:
    body = b'{"action":"opened"}'
    good = "sha256=" + hmac.new(b"s3cret", body, hashlib.sha256).hexdigest()
    verify_webhook(b"s3cret", body, good)
    for bad in [None, "sha256=00", good.replace("a", "b", 1)]:
        with pytest.raises(Refused) as e:
            verify_webhook(b"s3cret", body, bad)
        assert e.value.code == "webhook_invalid"


def test_app_jwt_is_rs256_and_short_lived() -> None:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pem = key.private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()
    ).decode()
    token = GitHubApp("12345", pem).app_jwt(now=1_800_000_000)
    claims = jwt.decode(
        token,
        key.public_key(),
        algorithms=["RS256"],
        options={"verify_exp": False, "verify_iat": False},
    )
    assert claims == {"iat": 1_799_999_940, "exp": 1_800_000_540, "iss": "12345"}


@respx.mock
def test_config_comes_from_the_base_commit_only() -> None:
    # Fixture 12: the PR head turns block off; the base keeps it on.
    base = respx.get(f"{BASE}/contents/.hushmark.yml", params={"ref": "base1"}).respond(
        200, text="mode: block\n"
    )
    head = respx.get(f"{BASE}/contents/.hushmark.yml", params={"ref": "head1"}).respond(
        200, text="mode: warn\n"
    )
    assert load_config(client(), OWNER, REPO, "base1").mode == "block"
    assert base.called and not head.called


@respx.mock
def test_missing_config_means_warn() -> None:
    respx.get(f"{BASE}/contents/.hushmark.yml").respond(404)
    assert load_config(client(), OWNER, REPO, "base1").mode == "warn"


@respx.mock
@pytest.mark.parametrize(
    ("role", "allowed"), [("admin", True), ("maintain", True), ("write", False), ("read", False)]
)
def test_only_maintainers_may_rerun(role: str, allowed: bool) -> None:
    # Fixture 02.
    respx.get(f"{BASE}/collaborators/someone/permission").respond(200, json={"role_name": role})
    if allowed:
        may_rerun(client(), OWNER, REPO, "someone", is_bot=False)
    else:
        with pytest.raises(Refused) as e:
            may_rerun(client(), OWNER, REPO, "someone", is_bot=False)
        assert e.value.code == "not_maintainer"


@respx.mock
def test_bots_may_not_rerun() -> None:
    with pytest.raises(Refused):
        may_rerun(client(), OWNER, REPO, "dependabot[bot]", is_bot=True)


@respx.mock
def test_diff_that_github_cannot_return_is_refused() -> None:
    respx.get(f"{BASE}/compare/b...h").respond(406)
    with pytest.raises(Refused) as e:
        client().diff(OWNER, REPO, "b", "h")
    assert e.value.code == "diff_unavailable"


@respx.mock
def test_full_check_run_for_r1_in_block_mode() -> None:
    rec = Recording("r1")
    pr = rec.pr()
    respx.get(f"{BASE}/pulls/1").respond(
        200,
        json={
            "base": {"sha": pr.base_sha},
            "head": {"sha": pr.head_sha},
            "title": pr.title,
            "body": pr.body,
        },
    )
    start = respx.post(f"{BASE}/check-runs").respond(201, json={"id": 77})
    respx.get(f"{BASE}/contents/.hushmark.yml", params={"ref": pr.base_sha}).respond(
        200, text="mode: block\n"
    )
    compare = respx.get(f"{BASE}/compare/{pr.base_sha}...{pr.head_sha}").respond(200, text=pr.diff)
    finish = respx.patch(f"{BASE}/check-runs/77").respond(200, json={})

    out = run_check(
        client(),
        owner=OWNER,
        repo=REPO,
        repo_id=pr.repo_id,
        number=1,
        model="z-ai/glm-5.3-flash",
        tee=RecordedTee(rec),
        sources=RecordedEvidence(rec),
        now=lambda: rec.meta["fetched_at"],
        salt=rec.salt(),
        boundary=rec.boundary(),
    )
    assert out.conclusion == "failure"
    assert json.loads(start.calls.last.request.content) == {
        "name": "Hushmark", "head_sha": pr.head_sha, "status": "in_progress"
    }  # fmt: skip
    assert compare.calls.last.request.headers["Accept"] == "application/vnd.github.diff"
    sent = json.loads(finish.calls.last.request.content)
    assert sent["status"] == "completed" and sent["conclusion"] == "failure"
    assert [a["path"] for a in sent["output"]["annotations"]] == ["docs/setup.md"]
