"""Check g: parse the model's answer strictly and keep only findings we can ground.

The model may only name a `candidate_id` from this run. File and line always come from our
own scan, so a finding can never point anywhere the scanner did not look. A finding that names
an unknown or repeated candidate is dropped and counted; an answer that does not match the
schema at all refuses the run.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from hushmark.refusal import Refused
from hushmark.scan import Candidate


class _ModelFinding(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")
    candidate_id: str
    kind: Literal["injection"]
    severity: Literal["high", "medium", "low"]
    rationale: str = Field(max_length=500)


class _ModelAnswer(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")
    findings: list[_ModelFinding]


@dataclass(frozen=True)
class Finding:
    candidate: Candidate
    severity: str
    rationale: str


@dataclass(frozen=True)
class Grounded:
    findings: tuple[Finding, ...]
    rejected_ungrounded: int


def _answer_text(response_bytes: bytes) -> str:
    try:
        content = json.loads(response_bytes)["choices"][0]["message"]["content"]
    except (ValueError, KeyError, IndexError, TypeError) as e:
        raise Refused("model_output_invalid", f"not a chat completion: {e}") from e
    if not isinstance(content, str):
        raise Refused("model_output_invalid", "the model gave no answer")
    text = content.strip()
    if text.startswith("```"):  # tolerate one Markdown code fence around the JSON
        text = text.split("\n", 1)[1] if "\n" in text else ""
        text = text.rsplit("```", 1)[0]
    return text


def ground(response_bytes: bytes, candidates: Sequence[Candidate]) -> Grounded:
    """Return the grounded findings. Raises `model_output_invalid` on a malformed answer."""
    try:
        answer = _ModelAnswer.model_validate_json(_answer_text(response_bytes))
    except ValidationError as e:
        raise Refused("model_output_invalid", f"answer does not match the schema: {e}") from e

    by_id = {c.id: c for c in candidates}
    kept: dict[str, Finding] = {}
    rejected = 0
    for f in answer.findings:
        candidate = by_id.get(f.candidate_id)
        if candidate is None or f.candidate_id in kept:
            rejected += 1
            continue
        kept[f.candidate_id] = Finding(candidate, f.severity, f.rationale)
    return Grounded(tuple(kept.values()), rejected)
