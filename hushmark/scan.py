"""Step 3: deterministic detectors over the whole diff, the PR title and the PR body.

Only added lines are scanned: removed lines are not merged. The scanner never decides whether
something is an attack. It finds regions a human reviewer cannot see, or text written for
agents, and hands them to the model as candidates (docs/ARCHITECTURE.md step 3).
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Iterator
from dataclasses import dataclass, field
from fnmatch import fnmatchcase
from typing import Literal

from hushmark.refusal import Refused

DETECTORS_VERSION = "1"
MAX_CANDIDATES = 20

Source = Literal["diff", "pr_title", "pr_body"]
# (source, file, first line, last line, detectors)
Hit = tuple[Source, str | None, int, int, list[str]]

ZERO_WIDTH = frozenset("​‌‍⁠﻿")
BIDI = frozenset("‪‫‬‭‮⁦⁧⁨⁩")
MARKUP_SUFFIXES = (".md", ".mdx", ".markdown", ".rst", ".html", ".htm")
AGENT_RULES_FILES = (
    "AGENTS.md",
    "*/AGENTS.md",
    "CLAUDE.md",
    "*/CLAUDE.md",
    "GEMINI.md",
    "*/GEMINI.md",
    ".cursorrules",
    ".cursor/rules/*",
    ".windsurfrules",
    ".github/copilot-instructions.md",
)
# Text that is invisible when rendered. Alt text and link titles only count when long enough
# to carry an instruction; short ones are ordinary documentation.
HIDDEN_HTML = re.compile(
    r"display\s*:\s*none|visibility\s*:\s*hidden|font-size\s*:\s*0|<\w+[^>]*\shidden[\s>/]"
    r"|<details[\s>]",
    re.IGNORECASE,
)
LONG_ALT = re.compile(r"""\balt\s*=\s*["'][^"']{40,}["']|!\[[^\]]{40,}\]""", re.IGNORECASE)
LONG_LINK_TITLE = re.compile(r"""\]\([^)\s]+\s+["'][^"']{40,}["']\)""")
AGENT_PHRASES = re.compile(
    r"ignore (all )?(previous|prior|above) instructions|you are an? (ai|assistant|agent)"
    r"|\bAI agents?\b|curl [^|\n]*\|\s*(ba)?sh|do not (tell|inform|mention)",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class DiffLine:
    number: int  # line number in the new file
    text: str
    added: bool


@dataclass(frozen=True)
class FileDiff:
    path: str
    lines: tuple[DiffLine, ...]  # context and added lines, in hunk order


@dataclass(frozen=True)
class Candidate:
    id: str
    source: Source
    file: str | None
    line: int
    end_line: int
    detectors: tuple[str, ...]
    signals: tuple[str, ...] = field(default=())


@dataclass(frozen=True)
class ScanResult:
    files: tuple[FileDiff, ...]
    candidates: tuple[Candidate, ...]


_HUNK = re.compile(r"^@@ -\d+(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")


def _unquote_path(raw: str) -> str:
    if raw.startswith('"') and raw.endswith('"'):
        raw = raw[1:-1].encode("latin-1").decode("unicode_escape").encode("latin-1").decode()
    return raw


def parse_diff(diff: str) -> tuple[FileDiff, ...]:
    """Parse a unified git diff into the new-side lines of each file."""
    files: list[FileDiff] = []
    path: str | None = None
    lines: list[DiffLine] = []
    old_left = new_left = 0
    new_no = 0

    def flush() -> None:
        if path is not None and lines:
            files.append(FileDiff(path, tuple(lines)))

    for raw in diff.splitlines():
        if old_left > 0 or new_left > 0:  # inside a hunk: counts decide, not prefixes
            tag, text = raw[:1], raw[1:]
            if tag == "+":
                lines.append(DiffLine(new_no, text, added=True))
                new_no += 1
                new_left -= 1
            elif tag == "-":
                old_left -= 1
            elif tag == "\\":
                pass  # "\ No newline at end of file"
            else:
                lines.append(DiffLine(new_no, text, added=False))
                new_no += 1
                new_left -= 1
                old_left -= 1
            continue
        if raw.startswith("diff --git "):
            flush()
            path, lines = None, []
        elif raw.startswith("+++ "):
            target = raw[4:].rstrip("\t")
            path = None if target == "/dev/null" else _unquote_path(target).removeprefix("b/")
        elif m := _HUNK.match(raw):
            old_left = int(m.group(1)) if m.group(1) is not None else 1
            new_no = int(m.group(2))
            new_left = int(m.group(3)) if m.group(3) is not None else 1
    flush()
    return tuple(files)


def _is_rules_file(path: str) -> bool:
    return any(fnmatchcase(path, pattern) for pattern in AGENT_RULES_FILES)


def _line_detectors(text: str, markup: bool) -> list[str]:
    found: list[str] = []
    chars = set(text)
    if chars & ZERO_WIDTH:
        found.append("zero_width")
    if chars & BIDI:
        found.append("bidi")
    if any(0xE0000 <= ord(c) <= 0xE007F for c in text):
        found.append("tag_chars")
    if markup:
        if "<!--" in text:
            found.append("html_comment")
        if HIDDEN_HTML.search(text) or LONG_ALT.search(text) or LONG_LINK_TITLE.search(text):
            found.append("hidden_html")
    return found


def _signals(texts: Iterable[str]) -> tuple[str, ...]:
    return tuple(sorted({m.group(0).lower() for t in texts for m in AGENT_PHRASES.finditer(t)}))


def _scan_text(source: Source, text: str) -> Iterator[Hit]:
    for number, line in enumerate(text.splitlines(), start=1):
        if detectors := _line_detectors(line, markup=True):
            yield source, None, number, number, detectors


def _scan_file(f: FileDiff) -> Iterator[Hit]:
    markup = f.path.lower().endswith(MARKUP_SUFFIXES)
    if not _is_rules_file(f.path):
        for line in f.lines:
            if line.added and (detectors := _line_detectors(line.text, markup)):
                yield "diff", f.path, line.number, line.number, detectors
        return

    # Agent rules files: every run of added lines is one candidate, whatever it contains.
    # Hidden characters inside the run are reported on that candidate, not separately.
    block: list[DiffLine] = []

    def emit() -> Hit:
        found = ["agent_rules_file"]
        for ln in block:
            found += [d for d in _line_detectors(ln.text, markup) if d not in found]
        return "diff", f.path, block[0].number, block[-1].number, found

    for line in f.lines:
        if line.added and block and line.number == block[-1].number + 1:
            block.append(line)
        elif line.added and line.text.strip():
            if block:
                yield emit()
            block = [line]
        elif not line.added and block:
            yield emit()
            block = []
    if block:
        yield emit()


def _region_text(
    files: dict[str, FileDiff],
    file: str | None,
    start: int,
    end: int,
    source: Source,
    title: str,
    body: str,
) -> list[str]:
    if source == "pr_title":
        return [title]
    if source == "pr_body":
        return body.splitlines()[start - 1 : end]
    return [ln.text for ln in files[file].lines if start <= ln.number <= end] if file else []


def scan(diff: str, title: str = "", body: str = "") -> ScanResult:
    """Find every candidate region. Never truncates; the cap is enforced separately."""
    files = parse_diff(diff)
    by_path = {f.path: f for f in files}
    hits: list[Hit] = [*_scan_text("pr_title", title), *_scan_text("pr_body", body)]
    for f in files:
        hits.extend(_scan_file(f))

    candidates = []
    for n, (source, file, start, end, detectors) in enumerate(hits, start=1):
        text = _region_text(by_path, file, start, end, source, title, body)
        candidates.append(
            Candidate(
                id=f"c{n}",
                source=source,
                file=file,
                line=start,
                end_line=end,
                detectors=tuple(detectors),
                signals=_signals(text),
            )
        )
    return ScanResult(files=files, candidates=tuple(candidates))


def ensure_within_cap(result: ScanResult) -> None:
    """Refuse instead of reviewing part of a pull request (AGENTS.md hard rule 5)."""
    if len(result.candidates) > MAX_CANDIDATES:
        raise Refused(
            "too_many_candidates", f"{len(result.candidates)} regions, cap is {MAX_CANDIDATES}"
        )
