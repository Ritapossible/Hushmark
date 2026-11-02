# Real recordings R1–R4

Recorded unedited from NEAR AI Cloud (`z-ai/glm-5.3-flash`) on 2026-11-02 by
`scripts/record_completion.py`, running on GitHub Actions with the project's API key: R1–R3 in run
41433656615, R4 in run 41441898820. Inputs are `fixtures/inputs/r1..r4`. Each run's signature and attestation were
verified before saving.

Per recording: `request.json` and `response.json` (exact bytes), `signature.json`,
`attestation.json` (exact bytes, fetched with the nonce in `meta.json`), `collateral.json`
(Intel PCS, same time), `nras.json` (NVIDIA NRAS response), `meta.json`.

The attestation reports contain NEAR's public deployment template, which names environment
variables such as `BEARER_TOKEN=${BEARER_TOKEN}`. Those are placeholders, not values.
