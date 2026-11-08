"""Scan a folder of public agent rules files with Hushmark's own detectors, offline.

    uv run python scripts/scan_rules_corpus.py DIR [DIR ...] > results.json

Every Markdown-like file under each DIR (`.md`, `.mdc`, `.cursorrules`) is read as text and
scanned the way Hushmark scans a pull request description: HTML comments (as whole spans),
invisible, bidi and tag characters, line separators and hidden HTML. No model is called and
nothing is sent anywhere. The output names files, line ranges and detectors only, never the
text, so it can be published as it is (AGENTS.md rule 3).

Used for docs/findings/public-rules-scan.md.
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

from hushmark.scan import scan

SUFFIXES = (".md", ".mdc", ".cursorrules")


def scan_corpus(root: Path) -> dict[str, object]:
    files = sorted(p for p in root.rglob("*") if p.is_file() and p.name.lower().endswith(SUFFIXES))
    flagged = []
    detectors: Counter[str] = Counter()
    for path in files:
        text = path.read_text(encoding="utf-8", errors="replace")
        result = scan("", body=text)
        if not result.candidates:
            continue
        regions = []
        for c in result.candidates:
            detectors.update(c.detectors)
            regions.append({"lines": [c.line, c.end_line], "detectors": list(c.detectors)})
        flagged.append({"file": str(path.relative_to(root)), "regions": regions})
    return {
        "root": root.name,
        "files": len(files),
        "files_flagged": len(flagged),
        "detectors": dict(sorted(detectors.items())),
        "flagged": flagged,
    }


def main(argv: list[str]) -> int:
    if not argv:
        print(__doc__, file=sys.stderr)
        return 2
    print(json.dumps([scan_corpus(Path(a)) for a in argv], indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
