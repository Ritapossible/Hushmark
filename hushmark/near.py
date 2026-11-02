"""Live adapters for the pipeline: NEAR AI Cloud, Intel PCS and NVIDIA NRAS."""

from __future__ import annotations

import asyncio
import time
from typing import Any

import dcap_qvl
import httpx

from hushmark.infer import BASE_URL, Completion, complete
from hushmark.refusal import Refused

NRAS_URL = "https://nras.attestation.nvidia.com/v3/attest/gpu"
JWKS_URL = "https://nras.attestation.nvidia.com/.well-known/jwks.json"


class NearAiCloud:
    """NEAR AI Cloud over HTTPS. Model TEEs can take minutes on a cold start."""

    def __init__(self, api_key: str, model: str, http: httpx.Client | None = None) -> None:
        self.model = model
        self.http = http or httpx.Client(
            base_url=BASE_URL,
            headers={"Authorization": f"Bearer {api_key}", "Accept-Encoding": "identity"},
            timeout=httpx.Timeout(300, connect=30),
        )

    def complete(self, request_bytes: bytes) -> Completion:
        return complete(self.http, request_bytes)

    def signature(self, chat_id: str) -> dict[str, Any]:
        # The signature can lag the response briefly; a missing one is a refusal.
        for attempt in range(6):
            r = self.http.get(
                f"/signature/{chat_id}", params={"model": self.model, "signing_algo": "ecdsa"}
            )
            if r.status_code == 200:
                body: dict[str, Any] = r.json()
                if "signature" in body:
                    return body
            time.sleep(1 + attempt)
        raise Refused("signature_mismatch", f"no signature for {chat_id}")

    def attestation(self, nonce: str, signing_address: str) -> bytes:
        r = self.http.get(
            "/attestation/report",
            params={
                "model": self.model,
                "nonce": nonce,
                "signing_algo": "ecdsa",
                "signing_address": signing_address,
            },
        )
        if r.status_code != 200:
            raise Refused("no_attestation", f"HTTP {r.status_code}")
        return r.content


class LiveEvidence:
    """Intel collateral and NVIDIA's verdict, fetched fresh for every review."""

    def __init__(self, http: httpx.Client | None = None) -> None:
        self.http = http or httpx.Client(timeout=60)
        self._jwks: dict[str, Any] | None = None

    def collateral(self, raw_quote: bytes) -> str:
        return str(asyncio.run(dcap_qvl.get_collateral_from_pcs(raw_quote)).to_json())

    def nras(self, gpu_payload: dict[str, Any]) -> Any:
        r = self.http.post(NRAS_URL, json=gpu_payload)
        r.raise_for_status()
        return r.json()

    def jwks(self) -> dict[str, Any]:
        if self._jwks is None:
            r = self.http.get(JWKS_URL)
            r.raise_for_status()
            self._jwks = r.json()
        return self._jwks
