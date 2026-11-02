"""Check g on real recordings, and fixture 08 as a unit test of grounding alone.

Fixture 08 cannot use recorded evidence: adding a finding to a response changes its bytes,
so the signature check would refuse it first and the test would pass for the wrong reason.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from hushmark.refusal import Refused
from hushmark.scan import Candidate, scan
from hushmark.verify.grounding import ground
from tests.conftest import FIXTURES


def candidates(name: str) -> tuple[Candidate, ...]:
    d: Path = FIXTURES / "inputs" / name
    return scan(
        (d / "diff.patch").read_text(), (d / "title.txt").read_text(), (d / "body.txt").read_text()
    ).candidates


def recorded(name: str) -> bytes:
    return (FIXTURES / "recordings" / name / "response.json").read_bytes()


def answer(content: object) -> bytes:
    return json.dumps({"choices": [{"message": {"content": content}}]}).encode()


def finding(cid: str) -> dict[str, str]:
    return {"candidate_id": cid, "kind": "injection", "severity": "high", "rationale": "x"}


def test_r1_grounds_both_findings_at_our_own_locations() -> None:
    grounded = ground(recorded("r1"), candidates("r1"))
    places = sorted(
        (f.candidate.source, f.candidate.file, f.candidate.line) for f in grounded.findings
    )
    assert places == [("diff", "docs/setup.md", 5), ("pr_body", None, 2)]
    assert grounded.rejected_ungrounded == 0


@pytest.mark.parametrize(("name", "count"), [("r2", 0), ("r3", 1), ("r4", 0)])
def test_other_recordings_ground_as_expected(name: str, count: int) -> None:
    assert len(ground(recorded(name), candidates(name)).findings) == count


def test_fixture_08_unknown_candidate_is_dropped_and_counted() -> None:
    body = json.dumps({"findings": [finding("c2"), finding("c9")]})
    grounded = ground(answer(body), candidates("r1"))
    assert [f.candidate.id for f in grounded.findings] == ["c2"]
    assert grounded.rejected_ungrounded == 1


def test_repeated_candidate_counts_once() -> None:
    body = json.dumps({"findings": [finding("c1"), finding("c1")]})
    grounded = ground(answer(body), candidates("r1"))
    assert len(grounded.findings) == 1
    assert grounded.rejected_ungrounded == 1


def test_code_fence_is_tolerated() -> None:
    body = "```json\n" + json.dumps({"findings": [finding("c1")]}) + "\n```"
    assert len(ground(answer(body), candidates("r1")).findings) == 1


@pytest.mark.parametrize(
    "content",
    [
        None,
        "not json",
        json.dumps({"findings": [dict(finding("c1"), line=99)]}),  # extra field
        json.dumps({"findings": [dict(finding("c1"), kind="secret")]}),  # second finding kind
        json.dumps({"findings": [dict(finding("c1"), rationale="x" * 501)]}),
        json.dumps({"results": []}),
    ],
)
def test_malformed_answer_refuses_the_run(content: object) -> None:
    with pytest.raises(Refused) as e:
        ground(answer(content), candidates("r1"))
    assert e.value.code == "model_output_invalid"
