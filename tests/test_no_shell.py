"""The guard in conftest.py really blocks process creation (AGENTS.md hard rule 1)."""

from __future__ import annotations

import os

import pytest

from tests.conftest import ProcessSpawnAttempted


def test_audit_hook_blocks_shell_commands() -> None:
    with pytest.raises(ProcessSpawnAttempted):
        os.system("true")  # noqa: TID251, S605, S607 - proving the guard works


def test_audit_hook_blocks_subprocess() -> None:
    import subprocess  # noqa: TID251 - proving the guard works

    with pytest.raises(ProcessSpawnAttempted):
        subprocess.run(["true"], check=False)  # noqa: S603, S607
