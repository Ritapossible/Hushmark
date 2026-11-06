"""Step 7: turn a review outcome into the `Hushmark` Check Run (docs/ARCHITECTURE.md).

| Outcome                         | mode: warn | mode: block |
| no candidates                   | success    | success     |
| reviewed, no verified findings  | success    | success     |
| verified findings               | neutral    | failure     |
| refused                         | neutral    | neutral     |

A refusal never shows a model finding. It shows the scanner's own hits as *unconfirmed*, so a
reviewer still knows where to look.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from hushmark.config import Config
from hushmark.pipeline import NoCandidates, Outcome, Refusal, Reviewed
from hushmark.scan import Candidate

CHECK_NAME = "Hushmark"
MAX_ANNOTATIONS = 50  # GitHub accepts at most 50 per request; report.py stays under it

REFUSAL_TEXT = {
    "too_many_candidates": "Too many hidden regions to review safely. Review them by hand.",
    "config_invalid": ".hushmark.yml on the default branch is not valid.",
    "diff_unavailable": "GitHub could not return the full diff, so nothing was reviewed.",
    "no_attestation": "NEAR AI Cloud returned no attestation for the signer.",
    "quote_invalid": "The Intel TDX quote did not verify.",
    "signer_not_bound": "The attestation does not bind the signing key.",
    "nonce_mismatch": "The attestation was not produced for this review.",
    "measurement_mismatch": "The TEE's measurements do not match its published configuration.",
    "gpu_evidence_invalid": "NVIDIA's GPU attestation did not verify.",
    "signature_mismatch": "The model's answer was not signed by the attested TEE.",
    "model_output_invalid": "The model's answer was not in the expected format.",
    "tee_unavailable": "NEAR AI Cloud could not be reached.",
    "budget_exceeded": "Today's review budget for this repository is spent. Review by hand.",
    "internal_error": "Hushmark failed before it could review this pull request.",
}


@dataclass(frozen=True)
class CheckOutput:
    conclusion: str  # success | neutral | failure
    title: str
    summary: str
    annotations: list[dict[str, Any]] = field(default_factory=list)


# The rationale is the model's sentence about attacker-written text, so it may carry a link the
# attacker asked for. The file and line are the evidence; the sentence is only a hint. Any
# Markdown link, autolink or bare URL becomes the word "link" (the 500-character cap stays in
# grounding.py). Not a sanitizer: nothing else is rewritten.
_LINKS = re.compile(
    r"!?\[[^\]]*\]\([^)]*\)"  # [text](url) and ![alt](url)
    r"|<[a-z][a-z0-9+.-]*:[^>\s]*>"  # <scheme:...>
    r"|\b(?:[a-z][a-z0-9+.-]*://|www\.)\S+",  # bare URLs
    re.IGNORECASE,
)


def _no_links(text: str) -> str:
    return _LINKS.sub("link", text)


def _where(c: Candidate) -> str:
    if c.source == "pr_title":
        return "the PR title"
    if c.source == "pr_body":
        return f"the PR description, line {c.line}"
    return f"`{c.file}` line {c.line}"


def _annotation(c: Candidate, level: str, title: str, message: str) -> dict[str, Any]:
    return {
        "path": c.file,
        "start_line": c.line,
        "end_line": c.end_line,
        "annotation_level": level,
        "title": title,
        "message": message,
    }


def _unconfirmed(candidates: tuple[Candidate, ...]) -> list[dict[str, Any]]:
    return [
        _annotation(
            c,
            "notice",
            "Hidden content (unconfirmed)",
            f"Hushmark's scanner found: {', '.join(c.detectors)}. It was not reviewed by the "
            "model, so this is not a finding.",
        )
        for c in candidates
        if c.source == "diff"
    ][:MAX_ANNOTATIONS]


def render(outcome: Outcome, config: Config) -> CheckOutput:
    if isinstance(outcome, NoCandidates):
        return CheckOutput(
            "success", "No hidden content", "No hidden regions found. No model call was made."
        )

    if isinstance(outcome, Refusal):
        reason = REFUSAL_TEXT.get(outcome.code, "The review could not be verified.")
        summary = (
            f"**Not verified** (`{outcome.code}`). {reason}\n\n"
            f"No model finding is shown. The scanner found {len(outcome.candidates)} hidden "
            "region(s); they are marked below as unconfirmed."
        )
        return CheckOutput(
            "neutral", "Review not verified", summary, _unconfirmed(outcome.candidates)
        )

    assert isinstance(outcome, Reviewed)
    receipt = f"receipt: `{outcome.receipt.receipt_id}`"
    findings = outcome.grounded.findings
    if not findings:
        summary = (
            f"{len(outcome.candidates)} hidden region(s) reviewed inside a NEAR AI Cloud TEE; "
            f"none is aimed at AI agents. Signature and attestation verified.\n\n{receipt}"
        )
        return CheckOutput("success", "No instructions aimed at agents", summary)

    level = "failure" if config.mode == "block" else "warning"
    lines = [
        f"**{len(findings)} hidden instruction(s) aimed at AI agents.** Each was reviewed inside "
        "a NEAR AI Cloud TEE, and the signature and attestation verified.",
        "",
    ]
    annotations = []
    for f in findings:
        c = f.candidate
        rationale = _no_links(f.rationale)
        lines.append(f"- {_where(c)} ({f.severity}): {rationale}")
        if c.source == "diff":
            annotations.append(
                _annotation(c, level, f"Instruction aimed at AI agents ({f.severity})", rationale)
            )
    if outcome.grounded.rejected_ungrounded:
        lines.append(f"\n{outcome.grounded.rejected_ungrounded} ungrounded answer(s) ignored.")
    lines += ["", receipt]
    conclusion = "failure" if config.mode == "block" else "neutral"
    title = f"{len(findings)} instruction(s) aimed at AI agents"
    return CheckOutput(conclusion, title, "\n".join(lines), annotations[:MAX_ANNOTATIONS])
