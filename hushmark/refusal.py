"""Refusals: every way a run can stop, each with a stable reason code."""

from __future__ import annotations


class Refused(Exception):
    """A run stopped on purpose. Tests assert on `code`, never on the message."""

    def __init__(self, code: str, detail: str = "") -> None:
        super().__init__(f"{code}: {detail}" if detail else code)
        self.code = code
        self.detail = detail
