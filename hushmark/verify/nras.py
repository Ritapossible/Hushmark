"""Check e, second half: NVIDIA's signed verdict on the GPU evidence (ADR-0006).

NVIDIA NRAS answers with an overall token and one token per GPU, all ES384 JWTs. NEAR's
reference decodes them without checking the signature; we verify every signature against
NVIDIA's key set (pinned in `fixtures/nvidia/jwks.json` for offline runs), the issuer, the
time window, our nonce, the overall verdict, and that the overall token commits to each GPU
token by SHA-256.
"""

from __future__ import annotations

import hashlib
from collections.abc import Mapping
from typing import Any

import jwt

from hushmark.refusal import Refused

ISSUER = "https://nras.attestation.nvidia.com"


def _verify_token(token: str, keys: Mapping[str, Any], now_secs: int) -> dict[str, Any]:
    try:
        kid = jwt.get_unverified_header(token).get("kid")
        if not isinstance(kid, str) or kid not in keys:
            raise Refused("gpu_evidence_invalid", f"token signed by unknown key {kid!r}")
        claims: dict[str, Any] = jwt.decode(
            token,
            key=jwt.PyJWK(keys[kid]).key,
            algorithms=["ES384"],
            issuer=ISSUER,
            # Time is checked below against the pinned verification time, not the clock.
            options={"verify_exp": False, "verify_nbf": False, "verify_iat": False},
        )
    except jwt.PyJWTError as e:
        raise Refused("gpu_evidence_invalid", f"bad NRAS token: {e}") from e
    if not claims.get("nbf", 0) <= now_secs <= claims.get("exp", 0):
        raise Refused("gpu_evidence_invalid", "NRAS token outside its validity window")
    return claims


def verify_nras(
    response: Any, nonce_hex: str, jwks: Mapping[str, Any], now_secs: int
) -> dict[str, Any]:
    """Raise `gpu_evidence_invalid` unless NVIDIA attested every GPU for our nonce."""
    keys = {k["kid"]: k for k in jwks.get("keys", [])}
    try:
        (label, overall), gpu_tokens = response
        if label != "JWT" or not isinstance(gpu_tokens, dict) or not gpu_tokens:
            raise ValueError("unexpected layout")
    except (TypeError, ValueError) as e:
        raise Refused("gpu_evidence_invalid", f"unexpected NRAS response: {e}") from e

    claims = _verify_token(str(overall), keys, now_secs)
    if claims.get("x-nvidia-overall-att-result") is not True:
        raise Refused("gpu_evidence_invalid", "NVIDIA's overall verdict is not true")
    if str(claims.get("eat_nonce", "")).lower() != nonce_hex.lower():
        raise Refused("gpu_evidence_invalid", "NRAS verdict is not for our nonce")

    submods = claims.get("submods")
    if not isinstance(submods, dict) or set(submods) != set(gpu_tokens):
        raise Refused("gpu_evidence_invalid", "overall token does not list exactly these GPUs")
    for gpu, token in gpu_tokens.items():
        digest = hashlib.sha256(str(token).encode()).hexdigest()
        if submods[gpu] != ["DIGEST", ["SHA-256", digest]]:
            raise Refused("gpu_evidence_invalid", f"{gpu} token is not the one NVIDIA committed to")
        gpu_claims = _verify_token(str(token), keys, now_secs)
        if str(gpu_claims.get("eat_nonce", "")).lower() != nonce_hex.lower():
            raise Refused("gpu_evidence_invalid", f"{gpu} evidence is not for our nonce")
    return claims
