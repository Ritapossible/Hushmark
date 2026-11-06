"""`.hushmark.yml`, read from the base commit only (AGENTS.md hard rule 12).

The caller fetches the file at `base_sha`; this module only parses it. A pull request can
never change how it is judged, because its own copy of the file is never read.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import yaml

from hushmark.refusal import Refused

Mode = Literal["warn", "block"]


MAX_IGNORE_PATTERNS = 50


@dataclass(frozen=True)
class Config:
    mode: Mode = "warn"
    ignore: tuple[str, ...] = ()  # fnmatch patterns; `*` also matches `/` (ADR-0011)


def _ignore(value: object) -> tuple[str, ...]:
    if value is None:
        return ()
    if not isinstance(value, list) or not all(isinstance(p, str) and p.strip() for p in value):
        raise Refused("config_invalid", "ignore must be a list of path patterns")
    if len(value) > MAX_IGNORE_PATTERNS:
        raise Refused("config_invalid", f"at most {MAX_IGNORE_PATTERNS} ignore patterns")
    return tuple(p.strip() for p in value)


def parse_config(text: str | None) -> Config:
    """Parse the base branch's `.hushmark.yml`. Missing file means defaults."""
    if text is None or not text.strip():
        return Config()
    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError as e:
        raise Refused("config_invalid", f"not valid YAML: {e}") from e
    if not isinstance(data, dict):
        raise Refused("config_invalid", "expected a mapping")
    unknown = set(data) - {"mode", "ignore"}
    if unknown:
        raise Refused("config_invalid", f"unknown keys: {sorted(unknown)}")
    mode = data.get("mode", "warn")
    if mode not in ("warn", "block"):
        raise Refused("config_invalid", f"mode must be warn or block, not {mode!r}")
    return Config(mode=mode, ignore=_ignore(data.get("ignore")))
