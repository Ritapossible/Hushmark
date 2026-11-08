"""Step 3: deterministic detectors over the whole diff, the PR title and the PR body.

Only added lines are scanned: removed lines are not merged. The scanner never decides whether
something is an attack. It finds regions a human reviewer cannot see, or text written for
agents, and hands them to the model as candidates (docs/ARCHITECTURE.md step 3).
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Iterator, Sequence
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
# Characters other programs treat as line breaks but git does not. Inside a line they can hide
# what follows from a reader, and Python's splitlines() would split on them.
LINE_SEPARATORS = frozenset("\r\x0b\x0c\x1c\x1d\x1e\x85\u2028\u2029")
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
    ignored_files: tuple[str, ...] = ()  # skipped by the base branch's `ignore` patterns


_HUNK = re.compile(r"^@@ -\d+(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")


def split_lines(text: str) -> list[str]:
    """Split on "\n" only, as git does, dropping one "\r" of a Windows line ending.

    Never `str.splitlines()`: it also splits on U+2028, form feed and others, which shifted
    the hunk counts and hid every later line of the hunk (audit 2026-11-08).
    """
    lines = text.split("\n")
    if lines and lines[-1] == "":
        lines.pop()
    return [ln[:-1] if ln.endswith("\r") else ln for ln in lines]


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

    for raw in split_lines(diff):
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
    if chars & LINE_SEPARATORS:
        found.append("line_separator")
    if markup:
        if "<!--" in text:
            found.append("html_comment")
        if HIDDEN_HTML.search(text) or LONG_ALT.search(text) or LONG_LINK_TITLE.search(text):
            found.append("hidden_html")
    return found


def _signals(texts: Iterable[str]) -> tuple[str, ...]:
    return tuple(sorted({m.group(0).lower() for t in texts for m in AGENT_PHRASES.finditer(t)}))


def _ends_with_close(text: str) -> bool:
    """A line ending in "-->" closes a comment opened above what the diff shows. Only at the
    end of the line, so a Mermaid arrow such as `A --> B` is not mistaken for one."""
    return text.rstrip().endswith("-->")


def _comment_spans(lines: Sequence[DiffLine]) -> list[tuple[int, int]]:
    """Index ranges of HTML comments, from "<!--" through "-->", merged where they touch.

    A comment can open on an unchanged line and gain added lines inside it, so context lines
    count too. Each hunk starts outside a comment, except that a closing marker with no
    visible opening means the comment began before the hunk.
    """
    spans: list[tuple[int, int]] = []
    inside, start, hunk_start = False, 0, 0
    for i, line in enumerate(lines):
        if i and line.number != lines[i - 1].number + 1:  # a new hunk
            if inside:
                spans.append((start, i - 1))
            inside, hunk_start = False, i
        text, pos = line.text, 0
        if not inside and "<!--" not in text and _ends_with_close(text):
            spans.append((hunk_start, i))
            continue
        while True:
            if inside:
                k = text.find("-->", pos)
                if k < 0:
                    break
                spans.append((start, i))
                inside, pos = False, k + 3
            else:
                k = text.find("<!--", pos)
                if k < 0:
                    break
                inside, start, pos = True, i, k + 4
    if inside:
        spans.append((start, len(lines) - 1))

    merged: list[tuple[int, int]] = []
    for lo, hi in sorted(spans):
        if merged and lo <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(hi, merged[-1][1]))
        else:
            merged.append((lo, hi))
    return merged


def _hits(lines: Sequence[DiffLine], markup: bool) -> Iterator[tuple[int, int, list[str]]]:
    """(first line, last line, detectors) for the added lines of an ordinary file or text.

    In markup, a whole HTML comment is one candidate when any of its lines is added; the
    instruction can sit many lines below the "<!--" (audit 2026-11-08).
    """
    spans = _comment_spans(lines) if markup else []
    covered = {i for lo, hi in spans for i in range(lo, hi + 1)}
    found: list[tuple[int, int, list[str]]] = []
    for lo, hi in spans:
        block = lines[lo : hi + 1]
        if not any(ln.added for ln in block):
            continue
        detectors: list[str] = []
        for ln in block:
            if ln.added:
                detectors += [d for d in _line_detectors(ln.text, markup) if d not in detectors]
        if "html_comment" not in detectors:
            detectors.append("html_comment")
        found.append((block[0].number, block[-1].number, detectors))
    for i, ln in enumerate(lines):
        if i not in covered and ln.added and (detectors := _line_detectors(ln.text, markup)):
            found.append((ln.number, ln.number, detectors))
    yield from sorted(found, key=lambda h: (h[0], h[1]))


def _scan_text(source: Source, text: str) -> Iterator[Hit]:
    lines = [DiffLine(n, t, added=True) for n, t in enumerate(split_lines(text), start=1)]
    for start, end, detectors in _hits(lines, markup=True):
        yield source, None, start, end, detectors


def _scan_file(f: FileDiff) -> Iterator[Hit]:
    markup = f.path.lower().endswith(MARKUP_SUFFIXES)
    if not _is_rules_file(f.path):
        for start, end, detectors in _hits(f.lines, markup):
            yield "diff", f.path, start, end, detectors
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
        return split_lines(body)[start - 1 : end]
    return [ln.text for ln in files[file].lines if start <= ln.number <= end] if file else []


def is_ignored(path: str, ignore: Sequence[str]) -> bool:
    """True when the base branch's `.hushmark.yml` skips this file (ADR-0011).

    Agent rules files are never skipped, whatever the patterns say: a pull request must not be
    able to hide a rules-file change behind a broad pattern such as `**`.
    """
    return not _is_rules_file(path) and any(fnmatchcase(path, p) for p in ignore)


def scan(diff: str, title: str = "", body: str = "", ignore: Sequence[str] = ()) -> ScanResult:
    """Find every candidate region. Never truncates; the cap is enforced separately.

    `ignore` (from the base branch's config only) skips matching files; the title, the body
    and agent rules files are always scanned.
    """
    files = parse_diff(diff)
    by_path = {f.path: f for f in files}
    hits: list[Hit] = [*_scan_text("pr_title", title), *_scan_text("pr_body", body)]
    ignored = tuple(f.path for f in files if is_ignored(f.path, ignore))
    for f in files:
        if f.path not in ignored:
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
    return ScanResult(files=files, candidates=tuple(candidates), ignored_files=ignored)


def ensure_within_cap(result: ScanResult) -> None:
    """Refuse instead of reviewing part of a pull request (AGENTS.md hard rule 5)."""
    if len(result.candidates) > MAX_CANDIDATES:
        raise Refused(
            "too_many_candidates", f"{len(result.candidates)} regions, cap is {MAX_CANDIDATES}"
        )
