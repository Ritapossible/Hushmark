"""Step 4 input: excerpts around each candidate. Only these ever leave the service (rule 11).

Invisible characters are written out as visible tags such as `⟦U+200B⟧`, so the model can see
what a human reviewer could not. Line numbers come from our own scan, never from the model.
"""

from __future__ import annotations

from dataclasses import dataclass

from hushmark.refusal import Refused
from hushmark.scan import (
    BIDI,
    LINE_SEPARATORS,
    ZERO_WIDTH,
    Candidate,
    FileDiff,
    ScanResult,
    split_lines,
)

CONTEXT_LINES = 10
MAX_EXCERPT_LINES = 200


@dataclass(frozen=True)
class Excerpt:
    candidate: Candidate
    lines: tuple[tuple[int, bool, str], ...]  # (line number, inside the candidate, text)


def visible(text: str) -> str:
    out = []
    for ch in text:
        code = ord(ch)
        if ch in ZERO_WIDTH or ch in BIDI or ch in LINE_SEPARATORS or 0xE0000 <= code <= 0xE007F:
            out.append(f"⟦U+{code:04X}⟧")
        else:
            out.append(ch)
    return "".join(out)


def _window(numbered: list[tuple[int, str]], c: Candidate) -> tuple[tuple[int, bool, str], ...]:
    lo, hi = c.line - CONTEXT_LINES, c.end_line + CONTEXT_LINES
    return tuple(
        (n, c.line <= n <= c.end_line, visible(text)) for n, text in numbered if lo <= n <= hi
    )


def build_excerpts(result: ScanResult, title: str, body: str) -> tuple[Excerpt, ...]:
    """One excerpt per candidate. Refuses if the excerpts together exceed the line cap."""
    files: dict[str, FileDiff] = {f.path: f for f in result.files}
    excerpts = []
    for c in result.candidates:
        if c.source == "pr_title":
            numbered = [(1, title)]
        elif c.source == "pr_body":
            numbered = list(enumerate(split_lines(body), start=1))
        else:
            assert c.file is not None
            numbered = [(ln.number, ln.text) for ln in files[c.file].lines]
        excerpts.append(Excerpt(c, _window(numbered, c)))

    total = sum(len(e.lines) for e in excerpts)
    if total > MAX_EXCERPT_LINES:
        raise Refused("too_many_candidates", f"{total} excerpt lines, cap is {MAX_EXCERPT_LINES}")
    return tuple(excerpts)


def render(excerpts: tuple[Excerpt, ...], boundary: str) -> str:
    """The excerpt block placed in the prompt, fenced by an unguessable boundary."""
    parts = [f"<<<EXCERPTS-{boundary}>>>"]
    for e in excerpts:
        c = e.candidate
        where = {"pr_title": "PR title", "pr_body": "PR description"}.get(c.source, c.file)
        span = f"line {c.line}" if c.line == c.end_line else f"lines {c.line}-{c.end_line}"
        parts.append(f"### {c.id} | {where} | {span} | detectors: {', '.join(c.detectors)}")
        parts.extend(f"{'>' if inside else ' '}{n:5d} | {text}" for n, inside, text in e.lines)
    parts.append(f"<<<END-EXCERPTS-{boundary}>>>")
    return "\n".join(parts)
