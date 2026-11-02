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


@dataclass(frozen=True)
class Config:
    mode: Mode = "warn"


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
    unknown = set(data) - {"mode"}
    if unknown:
        raise Refused("config_invalid", f"unknown keys: {sorted(unknown)}")
    mode = data.get("mode", "warn")
    if mode == "warn":
        return Config(mode="warn")
    if mode == "block":
        return Config(mode="block")
    raise Refused("config_invalid", f"mode must be warn or block, not {mode!r}")
