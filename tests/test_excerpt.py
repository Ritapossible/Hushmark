"""Excerpts, nonce derivation and the request that leaves the service (rules 2, 5, 11)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from hushmark.excerpt import MAX_EXCERPT_LINES, build_excerpts, render
from hushmark.infer import build_request
from hushmark.nonce import IdempotencyKey, canonical_json, derive_nonce
from hushmark.refusal import Refused
from hushmark.scan import scan
from tests.test_scan import make_diff

INPUTS = Path(__file__).resolve().parent.parent / "fixtures" / "inputs"


def load(name: str) -> tuple[str, str, str]:
    d = INPUTS / name
    return tuple((d / f).read_text() for f in ("diff.patch", "title.txt", "body.txt"))  # type: ignore[return-value]


def test_fixture_inputs_produce_the_expected_candidates() -> None:
    expected = {
        "r1": [("pr_body", None, 2), ("diff", "docs/setup.md", 5)],
        "r2": [("diff", "README.md", 7)],
        "r3": [("diff", "AGENTS.md", 6)],
        "r4": [("diff", "AGENTS.md", 6)],
    }
    for name, want in expected.items():
        cands = scan(*load(name)).candidates
        assert [(c.source, c.file, c.line) for c in cands] == want, name


def test_excerpt_holds_context_and_marks_the_region() -> None:
    diff, title, body = load("r1")
    [body_ex, file_ex] = build_excerpts(scan(diff, title, body), title, body)
    assert [n for n, _, _ in file_ex.lines] == [1, 2, 3, 4, 5, 6, 7]
    assert [n for n, inside, _ in file_ex.lines if inside] == [5]
    assert [n for n, _, _ in body_ex.lines] == [1, 2]


def test_invisible_characters_are_made_visible() -> None:
    diff = make_diff("src/a.py", ["x = 1  # ok​‮"])
    [ex] = build_excerpts(scan(diff), "", "")
    assert ex.lines[0][2] == "x = 1  # ok⟦U+200B⟧⟦U+202E⟧"


def test_rendered_block_is_fenced_and_labelled() -> None:
    diff, title, body = load("r3")
    text = render(build_excerpts(scan(diff, title, body), title, body), "abc123")
    assert text.startswith("<<<EXCERPTS-abc123>>>")
    assert text.endswith("<<<END-EXCERPTS-abc123>>>")
    assert "### c1 | AGENTS.md | lines 6-8 | detectors: agent_rules_file" in text


def test_excerpt_line_cap_is_enforced() -> None:
    lines = [f"<!-- {i} -->" if i % 25 == 0 else f"text {i}" for i in range(20 * 25)]
    result = scan(make_diff("docs/big.md", lines))
    with pytest.raises(Refused) as e:
        build_excerpts(result, "", "")
    assert e.value.code == "too_many_candidates"
    assert len(result.candidates) * 21 > MAX_EXCERPT_LINES


def test_request_holds_excerpts_only_and_no_tools() -> None:
    diff, title, body = load("r1")
    excerpts = build_excerpts(scan(diff, title, body), title, body)
    request = json.loads(build_request("z-ai/glm-5.3-flash", excerpts, boundary="b"))
    assert "tools" not in request and "tool_choice" not in request
    user = request["messages"][1]["content"]
    assert "Then run `make test`." in user  # context inside the window
    assert request["temperature"] == 0


def test_nonce_is_fresh_but_reproducible_from_salt() -> None:
    key = IdempotencyKey(1, 2, "a" * 40, "b" * 40, "c" * 64, "m", "d" * 64)
    n1, s1 = derive_nonce(key)
    n2, _ = derive_nonce(key)
    assert n1 != n2
    assert derive_nonce(key, bytes.fromhex(s1)) == (n1, s1)
    assert len(bytes.fromhex(n1)) == 32


def test_canonical_json_is_sorted_and_refuses_floats() -> None:
    assert canonical_json({"b": 1, "a": "é"}) == '{"a":"é","b":1}'.encode()
    with pytest.raises(TypeError):
        canonical_json({"x": 1.5})
