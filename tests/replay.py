"""Replays real recorded NEAR AI Cloud, Intel and NVIDIA evidence for pipeline tests.

Nothing here invents a response. `RecordedTee.complete` returns the recorded answer only for
the exact request bytes that were recorded, so a test passes only if the pipeline rebuilds that
request byte for byte from the fixture pull request.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from hushmark.infer import Completion
from hushmark.pipeline import PullRequestInput
from tests.conftest import FIXTURES


class Recording:
    def __init__(self, name: str) -> None:
        self.root: Path = FIXTURES / "recordings" / name
        self.src: Path = FIXTURES / "inputs" / name
        self.meta: dict[str, Any] = json.loads((self.root / "meta.json").read_text())
        self.request = (self.root / "request.json").read_bytes()
        self.response = (self.root / "response.json").read_bytes()

    def pr(self) -> PullRequestInput:
        k = self.meta["key"]
        return PullRequestInput(
            repo_id=k["repo_id"],
            pr=k["pr"],
            base_sha=k["base_sha"],
            head_sha=k["head_sha"],
            diff=(self.src / "diff.patch").read_text(),
            title=(self.src / "title.txt").read_text(),
            body=(self.src / "body.txt").read_text(),
        )

    def boundary(self) -> str:
        content = json.loads(self.request)["messages"][1]["content"]
        found = re.findall(r"<<<EXCERPTS-([0-9a-f]+)>>>", content)
        assert len(found) == 1
        return str(found[0])

    def salt(self) -> bytes:
        return bytes.fromhex(self.meta["nonce_salt"])


class RecordedTee:
    def __init__(self, rec: Recording, response: bytes | None = None) -> None:
        self.rec = rec
        self.response = rec.response if response is None else response
        self.calls = 0

    def complete(self, request_bytes: bytes) -> Completion:
        self.calls += 1
        assert request_bytes == self.rec.request, "pipeline did not rebuild the recorded request"
        return Completion(request_bytes, self.response, self.rec.meta["chat_id"])

    def signature(self, chat_id: str) -> dict[str, Any]:
        sig: dict[str, Any] = json.loads((self.rec.root / "signature.json").read_text())
        return sig

    def attestation(self, nonce: str, signing_address: str) -> bytes:
        return (self.rec.root / "attestation.json").read_bytes()


class RecordedEvidence:
    def __init__(self, rec: Recording) -> None:
        self.rec = rec

    def collateral(self, raw_quote: bytes) -> str:
        return (self.rec.root / "collateral.json").read_text()

    def nras(self, gpu_payload: dict[str, Any]) -> Any:
        return json.loads((self.rec.root / "nras.json").read_text())

    def jwks(self) -> dict[str, Any]:
        keys: dict[str, Any] = json.loads((FIXTURES / "nvidia" / "jwks.json").read_text())
        return keys
