"""Step 4: one completion on NEAR AI Cloud, keeping the exact request and response bytes.

The request carries excerpts only (rule 11) and never a `tools` field (rule 2). The bytes are
serialized once and never re-serialized, because the TEE signs their SHA-256 (rule 8).
"""

from __future__ import annotations

import hashlib
import json
import secrets
from dataclasses import dataclass
from pathlib import Path

import httpx

from hushmark.excerpt import Excerpt, render

BASE_URL = "https://cloud-api.near.ai/v1"
PROMPT_PATH = Path(__file__).resolve().parent.parent / "prompts" / "v1.txt"
# A reasoning model spends tokens thinking before the JSON answer; leave room for both. At 4,096
# GLM-5.3-flash ran out while still reasoning about 3 regions (PR #20: finish_reason=length,
# no answer), so the review refused. Only the tokens used are billed.
MAX_TOKENS = 16384


@dataclass(frozen=True)
class Completion:
    request_bytes: bytes
    response_bytes: bytes
    chat_id: str


def load_prompt() -> tuple[str, str]:
    """Return (prompt text, prompt_hash)."""
    raw = PROMPT_PATH.read_bytes()
    return raw.decode(), hashlib.sha256(raw).hexdigest()


def build_request(
    model: str,
    excerpts: tuple[Excerpt, ...],
    boundary: str | None = None,
    max_tokens: int = MAX_TOKENS,
) -> bytes:
    prompt, _ = load_prompt()
    boundary = boundary or secrets.token_hex(8)
    body = {
        "model": model,
        "messages": [
            {"role": "system", "content": prompt},
            {"role": "user", "content": render(excerpts, boundary)},
        ],
        "temperature": 0,
        "max_tokens": max_tokens,
        "stream": False,
    }
    return json.dumps(body, ensure_ascii=False, separators=(",", ":")).encode()


def complete(http: httpx.Client, request_bytes: bytes) -> Completion:
    """POST the exact bytes. `http` carries the base URL, auth and timeouts."""
    r = http.post(
        "/chat/completions",
        content=request_bytes,
        headers={
            "Content-Type": "application/json",
            "Accept-Encoding": "identity",
            "x-no-aliasing": "true",
        },
    )
    r.raise_for_status()
    return Completion(request_bytes, r.content, str(json.loads(r.content)["id"]))
