"""How each outcome appears on GitHub, in warn and block mode."""

from __future__ import annotations

import pytest

from hushmark.config import Config
from hushmark.pipeline import NoCandidates, Refusal
from hushmark.report import render
from hushmark.scan import scan
from tests.test_pipeline import replay
from tests.test_scan import make_diff

WARN, BLOCK = Config("warn"), Config("block")


def test_no_candidates_is_success() -> None:
    out = render(NoCandidates(scan("")), BLOCK)
    assert out.conclusion == "success" and out.annotations == []


@pytest.mark.parametrize(
    ("config", "conclusion", "level"), [(WARN, "neutral", "warning"), (BLOCK, "failure", "failure")]
)
def test_r1_findings_by_mode(config: Config, conclusion: str, level: str) -> None:
    outcome, _ = replay("r1")
    out = render(outcome, config)
    assert out.conclusion == conclusion
    # The doc finding is a line annotation; the PR-description finding is in the summary.
    assert [(a["path"], a["start_line"], a["annotation_level"]) for a in out.annotations] == [
        ("docs/setup.md", 5, level)
    ]
    assert "the PR description, line 2" in out.summary
    assert "receipt: `" + outcome.receipt.receipt_id + "`" in out.summary


@pytest.mark.parametrize("name", ["r2", "r4"])
def test_reviewed_without_findings_is_success_even_in_block_mode(name: str) -> None:
    outcome, _ = replay(name)
    out = render(outcome, BLOCK)
    assert out.conclusion == "success" and out.annotations == []
    assert outcome.receipt.receipt_id in out.summary


def test_rules_file_finding_spans_the_block() -> None:
    outcome, _ = replay("r3")
    [a] = render(outcome, BLOCK).annotations
    assert (a["path"], a["start_line"], a["end_line"]) == ("AGENTS.md", 6, 8)


def test_refusal_is_neutral_with_unconfirmed_hits_only() -> None:
    candidates = scan(make_diff("docs/a.md", ["<!-- x -->"])).candidates
    out = render(Refusal("signature_mismatch", "", candidates), BLOCK)
    assert out.conclusion == "neutral"
    assert "`signature_mismatch`" in out.summary
    assert [a["annotation_level"] for a in out.annotations] == ["notice"]
    assert "not a finding" in out.annotations[0]["message"]


def test_links_in_the_model_rationale_are_not_rendered() -> None:
    """The rationale describes attacker text, so a link in it is never shown as one."""
    from dataclasses import replace

    outcome, _ = replay("r1")
    tricky = (
        "Hidden note. See [the fix](https://evil.example/x) or ![img](http://a.b/c.png), "
        "<https://evil.example>, https://evil.example/run.sh and www.evil.example now."
    )
    findings = tuple(replace(f, rationale=tricky) for f in outcome.grounded.findings)
    outcome = replace(outcome, grounded=replace(outcome.grounded, findings=findings))
    out = render(outcome, BLOCK)
    shown = out.summary + "".join(a["message"] for a in out.annotations)
    for gone in ["http", "www.", "evil.example", "](", "<https"]:
        assert gone not in shown, gone
    assert "Hidden note. See link or link, link, link and link now." in out.summary
    assert out.annotations[0]["message"].startswith("Hidden note. See link")
