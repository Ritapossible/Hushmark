# ADR-0002: Verify attestation with NEAR's verifier code, never our own parser

- Status: accepted
- Date: 2026-11-01

## Context

Verifying a report means checking an Intel TDX quote and its collateral, the TCB status, the
debug bit, MRCONFIGID against `app_compose`, an RTMR3 event-log replay, and NVIDIA GPU
evidence. Writing this ourselves would take longer than the hackathon and would likely be wrong.

## Decision

Call NEAR's verifier code (`nearai-cloud-verifier`, and `dcap-qvl` for the quote). Our code
only adds what is specific to Hushmark: the nonce derivation, the signature-to-address match,
and grounding. Any verifier error or failure becomes a refusal with a reason code.

## Consequences

- We inherit the verifier's correctness and its limits, including whether it can run offline
  (`OPEN_QUESTIONS.md` Q3).
- Upgrading the verifier is a dependency bump, pinned in `uv.lock`.
