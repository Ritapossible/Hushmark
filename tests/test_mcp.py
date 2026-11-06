"""The MCP server: protocol, and that no hidden text reaches the agent unless it asks."""

from __future__ import annotations

import io
import json
from pathlib import Path
from typing import Any

import pytest

from hushmark import mcp
from hushmark.mcp import Reviewer, Server, build, tool_scan, tool_verify_receipt
from tests.replay import RecordedTee, Recording
from tests.test_pipeline import replay

R1 = Recording("r1").pr()
HIDDEN = "approve"  # a word inside R1's hidden comments


def call(server: Server, method: str, params: dict[str, Any] | None = None, id: int = 1) -> Any:
    return server.handle({"jsonrpc": "2.0", "id": id, "method": method, "params": params or {}})


def tool(server: Server, name: str, args: dict[str, Any]) -> tuple[dict[str, Any], bool]:
    result = call(server, "tools/call", {"name": name, "arguments": args})["result"]
    return json.loads(result["content"][0]["text"]), result["isError"]


# --- protocol ----------------------------------------------------------------------------


def test_initialize_negotiates_the_protocol_version() -> None:
    server = build({})
    assert (
        call(server, "initialize", {"protocolVersion": "2025-03-26"})["result"]["protocolVersion"]
        == "2025-03-26"
    )
    reply = call(server, "initialize", {"protocolVersion": "1999-01-01"})["result"]
    assert reply["protocolVersion"] == "2025-06-18"
    assert reply["serverInfo"]["name"] == "hushmark" and "tools" in reply["capabilities"]


def test_tools_are_listed_with_schemas() -> None:
    tools = call(build({}), "tools/list")["result"]["tools"]
    assert [t["name"] for t in tools] == ["scan", "review", "verify_receipt"]
    assert all(t["inputSchema"]["type"] == "object" for t in tools)


def test_notifications_get_no_answer_and_unknown_methods_an_error() -> None:
    server = build({})
    assert server.handle({"jsonrpc": "2.0", "method": "notifications/initialized"}) is None
    assert call(server, "resources/list")["error"]["code"] == -32601
    assert call(server, "tools/call", {"name": "rm", "arguments": {}})["error"]["code"] == -32602


def test_bad_arguments_are_a_tool_error_not_a_crash() -> None:
    result, failed = tool(build({}), "scan", {})
    assert failed and "exactly one" in result["error"]
    result, failed = tool(build({}), "scan", {"text": "a", "diff": "b"})
    assert failed


def test_stdio_carries_one_json_message_per_line() -> None:
    lines = [
        json.dumps({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}}),
        json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized"}),
        "not json",
        json.dumps({"jsonrpc": "2.0", "id": 2, "method": "ping"}),
    ]
    out = io.StringIO()
    build({}).serve(io.StringIO("\n".join(lines) + "\n"), out)
    replies = [json.loads(x) for x in out.getvalue().splitlines()]
    assert [r.get("id") for r in replies] == [1, None, 2]
    assert replies[1]["error"]["code"] == -32700


# --- scan --------------------------------------------------------------------------------


def test_scan_finds_hidden_regions_without_returning_their_text() -> None:
    out = tool_scan({"diff": R1.diff})
    assert out["hidden_regions"] == 1 and out["regions"][0]["file"] == "docs/setup.md"
    assert HIDDEN not in json.dumps(out)  # the agent never reads the hidden instruction
    assert "signals" not in json.dumps(out)  # nor the injection phrases matched in it


def test_plain_text_is_checked_like_untrusted_prose() -> None:
    out = tool_scan({"text": R1.body})
    assert out["hidden_regions"] == 1 and out["regions"][0]["file"] == "text"
    assert "Do not follow" in out["advice"]


def test_excerpts_only_on_request_fenced_and_labelled() -> None:
    out = tool_scan({"text": "ok\nzero​width here", "include_excerpts": True})
    block = out["untrusted_excerpts"]
    excerpt = next(iter(block["excerpts"].values()))
    assert "Never follow" in block["warning"]
    assert excerpt.startswith(f"<<<UNTRUSTED-{block['fence']}>>>")
    assert "⟦U+200B⟧" in excerpt and "​" not in excerpt


def test_path_applies_the_rules_for_that_file() -> None:
    out = tool_scan({"text": "Always run the tests.", "path": "AGENTS.md"})
    assert out["regions"][0]["detectors"] == ["agent_rules_file"]
    assert tool_scan({"text": "Always run the tests.", "path": "src/a.py"})["hidden_regions"] == 0


def test_clean_text_is_clean() -> None:
    assert tool_scan({"text": "Install with make install."})["hidden_regions"] == 0


# --- review ------------------------------------------------------------------------------


def test_review_of_clean_text_makes_no_model_call() -> None:
    class NoCalls(RecordedTee):
        def __init__(self) -> None:
            pass

        def complete(self, request_bytes: bytes) -> Any:
            raise AssertionError("model called")

    assert Reviewer({}, tee=NoCalls())({"text": "nothing hidden"}) == {
        "verified": True,
        "hidden_regions": 0,
        "findings": [],
        "model_called": False,
    }


def test_review_without_a_key_is_not_verified() -> None:
    out = Reviewer({})({"text": R1.body})
    assert out["verified"] is False and out["refusal"] == "tee_unavailable"
    assert HIDDEN not in json.dumps(out)


def test_verified_review_saves_the_receipt_and_strips_links(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    outcome, _ = replay("r1")
    monkeypatch.setattr(mcp, "review", lambda *a, **k: outcome)
    out = Reviewer({}, receipts_dir=tmp_path)({"diff": R1.diff})
    assert out["verified"] and len(out["findings"]) == 2
    assert Path(out["receipt_path"]).read_bytes() == outcome.receipt.body
    assert Path(out["attestation_path"]).read_bytes() == outcome.attestation
    assert "http" not in json.dumps(out["findings"])


# --- verify_receipt ----------------------------------------------------------------------


def test_verify_receipt_from_files(tmp_path: Path) -> None:
    outcome, _ = replay("r1")
    receipt = tmp_path / "receipt.json"
    receipt.write_bytes(outcome.receipt.body)
    out = tool_verify_receipt({"receipt_path": str(receipt), "online": False})
    assert out["ok"] and out["receipt_id"] == outcome.receipt.receipt_id
    checks = {c["name"]: c["status"] for c in out["checks"]}
    assert checks["signature"] == "pass" and checks["anchor"] == "skipped"


def test_verify_receipt_catches_a_changed_receipt() -> None:
    outcome, _ = replay("r1")
    changed = outcome.receipt.body.replace(b'"provider_tee"', b'"gateway"')
    out = tool_verify_receipt({"receipt": changed.decode(), "online": False})
    assert not out["ok"]
