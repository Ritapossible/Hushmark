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
        choice = json.loads(response_bytes)["choices"][0]
        content = choice["message"]["content"]
    except (ValueError, KeyError, IndexError, TypeError) as e:
        raise Refused("model_output_invalid", f"not a chat completion ({type(e).__name__})") from e
    finish = str(choice.get("finish_reason"))
    if not isinstance(content, str):
        raise Refused("model_output_invalid", f"no answer (finish_reason={finish})")
    if finish == "length":
        raise Refused("model_output_invalid", "answer cut off at max_tokens (finish_reason=length)")
    text = content.strip()
    if text.startswith("```"):  # tolerate one Markdown code fence around the JSON
        text = text.split("\n", 1)[1] if "\n" in text else ""
        text = text.rsplit("```", 1)[0]
    return text


def schema_errors(e: ValidationError) -> str:
    """Where and how the answer broke the schema, never what it said (AGENTS.md rule 3).

    For example `findings.0.rationale: string_too_long`. Safe to log.
    """
    parts = [
        ".".join(str(p) for p in err["loc"]) + ": " + str(err["type"])
        for err in e.errors(include_input=False, include_url=False)
    ]
    return (
        "schema: " + "; ".join(parts[:5]) + (f" (+{len(parts) - 5} more)" if len(parts) > 5 else "")
    )


def ground(response_bytes: bytes, candidates: Sequence[Candidate]) -> Grounded:
    """Return the grounded findings. Raises `model_output_invalid` on a malformed answer."""
    try:
        answer = _ModelAnswer.model_validate_json(_answer_text(response_bytes))
    except ValidationError as e:
        raise Refused("model_output_invalid", schema_errors(e)) from e

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
