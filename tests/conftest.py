"""Test-wide guard for AGENTS.md hard rule 1: nothing in the test process may start a process.

The audit hook is installed once for the whole session, so every test, including every
fixture run through the pipeline, fails if any code path tries to run a command.

One known exception happens before any input exists: importing `eth_account` loads
pycryptodome, which calls `platform.architecture()`, which runs `file -b <python>`. Imports are
done first with the hook in recording mode; `test_no_shell.py` pins that list to exactly that
one fixed command. After that the hook is strict.
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


IMPORT_TIME_SPAWNS: list[tuple[str, Any]] = []
_strict = False


def _no_spawn(event: str, args: tuple[Any, ...]) -> None:
    if event not in SPAWN_EVENTS:
        return
    if not _strict:
        IMPORT_TIME_SPAWNS.append((event, args[1] if event == "subprocess.Popen" else args))
        return
    raise ProcessSpawnAttempted(event)


sys.addaudithook(_no_spawn)
import dcap_qvl  # noqa: E402, F401
import eth_account  # noqa: E402, F401
import httpx  # noqa: E402, F401

_strict = True


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
