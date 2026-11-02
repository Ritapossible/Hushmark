"""The guard in conftest.py really blocks process creation (AGENTS.md hard rule 1)."""

from __future__ import annotations

import os
import sys

import pytest

from tests.conftest import IMPORT_TIME_SPAWNS, ProcessSpawnAttempted


def test_audit_hook_blocks_shell_commands() -> None:
    with pytest.raises(ProcessSpawnAttempted):
        os.system("true")  # noqa: TID251, S605, S607 - proving the guard works


def test_audit_hook_blocks_subprocess() -> None:
    import subprocess  # noqa: TID251 - proving the guard works

    with pytest.raises(ProcessSpawnAttempted):
        subprocess.run(["true"], check=False)  # noqa: S603, S607


def test_only_the_known_import_time_spawn_happened() -> None:
    # pycryptodome (via eth_account) asks `file` whether Python is 32- or 64-bit, once, at
    # import, with fixed arguments. Anything else here means a dependency changed.
    python = os.path.realpath(sys.executable)  # platform resolves the venv symlink
    assert IMPORT_TIME_SPAWNS == [("subprocess.Popen", ["file", "-b", python])]
