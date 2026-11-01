"""`.hushmark.yml` parsing. Fixture 12 (head config ignored) is enforced where it is fetched."""

from __future__ import annotations

import pytest

from hushmark.config import Config, parse_config
from hushmark.refusal import Refused


@pytest.mark.parametrize("text", [None, "", "  \n"])
def test_missing_or_empty_means_warn(text: str | None) -> None:
    assert parse_config(text) == Config(mode="warn")


def test_block_mode() -> None:
    assert parse_config("mode: block\n") == Config(mode="block")


@pytest.mark.parametrize(
    "text", ["mode: strict", "mode: [block]", "- block", "mode: block\nextra: 1", "mode: :"]
)
def test_anything_else_is_refused(text: str) -> None:
    with pytest.raises(Refused) as e:
        parse_config(text)
    assert e.value.code == "config_invalid"
