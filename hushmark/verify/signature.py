"""Check f of docs/ARCHITECTURE.md step 5: the TEE signed exactly the bytes we sent and got.

NEAR AI Cloud signs `<model>:<sha256(request)>:<sha256(response)>` with an EIP-191 key whose
address the attestation binds (check c). Only `provider_tee` signatures are accepted: a
`gateway` signature binds the gateway, not the model's TEE.
"""

from __future__ import annotations

import hashlib
from collections.abc import Mapping
from typing import Any

from eth_account import Account
from eth_account.messages import encode_defunct

from hushmark.refusal import Refused


def check_signature(
    signature: Mapping[str, Any], model: str, request_bytes: bytes, response_bytes: bytes
) -> str:
    """Raise `signature_mismatch` unless the signature covers these exact bytes.

    Returns the signing address, to be matched against the attestation (check a).
    """
    if signature.get("signature_kind") != "provider_tee":
        raise Refused("signature_mismatch", f"kind {signature.get('signature_kind')!r}")
    if signature.get("signing_algo") != "ecdsa":
        raise Refused("signature_mismatch", f"algo {signature.get('signing_algo')!r}")

    expected = (
        f"{model}:{hashlib.sha256(request_bytes).hexdigest()}"
        f":{hashlib.sha256(response_bytes).hexdigest()}"
    )
    if signature.get("text") != expected:
        raise Refused("signature_mismatch", "signed text does not cover our exact bytes")

    try:
        signer = Account.recover_message(
            encode_defunct(text=expected), signature=str(signature["signature"])
        )
    except Exception as e:  # malformed signatures raise a variety of errors
        raise Refused("signature_mismatch", f"unrecoverable signature: {e}") from e
    address = str(signature.get("signing_address", ""))
    if signer.lower() != address.lower():
        raise Refused("signature_mismatch", "recovered signer is not the signing address")
    return address
