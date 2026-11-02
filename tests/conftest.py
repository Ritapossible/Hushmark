"""Test-wide guard for AGENTS.md hard rule 1: nothing in the test process may start a process.

The audit hook is installed once for the whole session, so every test, including every
fixture run through the pipeline, fails if any code path tries to run a command.
The hook is strict from before the first dependency import, so an import that starts a
process also fails the run.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import pytest

SPAWN_EVENTS = frozenset(
    {"subprocess.Popen", "os.system", "os.exec", "os.posix_spawn", "os.spawn", "os.fork"}
)
FIXTURES = Path(__file__).resolve().parent.parent / "fixtures"


class ProcessSpawnAttempted(RuntimeError):
    pass


def _no_spawn(event: str, args: tuple[Any, ...]) -> None:
    if event in SPAWN_EVENTS:
        raise ProcessSpawnAttempted(event)


sys.addaudithook(_no_spawn)
# Import every dependency under the hook, so an import that starts a process fails loudly.
import dcap_qvl  # noqa: E402, F401
import eth_account  # noqa: E402, F401
import httpx  # noqa: E402, F401
import jwt  # noqa: E402, F401


class AttestationFixture:
    def __init__(self, name: str) -> None:
        root = FIXTURES / "attestation" / name
        self.report: dict[str, Any] = json.loads((root / "report.json").read_bytes())
        self.collateral_json = (root / "collateral.json").read_text()
        meta = json.loads((root / "meta.json").read_text())
        self.nonce: str = meta["nonce"]
        self.fetched_at: int = meta["fetched_at"]

    @property
    def attestation(self) -> dict[str, Any]:
        att: dict[str, Any] = self.report["model_attestations"][0]
        return att


@pytest.fixture
def a1() -> AttestationFixture:
    return AttestationFixture("a1")


@pytest.fixture
def a2() -> AttestationFixture:
    return AttestationFixture("a2")
