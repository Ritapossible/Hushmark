# ADR-0001: Prove the review with NEAR AI Cloud TEE attestation

- Status: accepted
- Date: 2026-11-01

## Context

Hushmark must show that a finding came from a specific model run on a specific commit, without
publishing the diff. Options: trust our server, a ZK proof of inference, or TEE attestation.

## Decision

Use NEAR AI Cloud. Its model TEEs return an attestation report (Intel TDX quote plus NVIDIA GPU
evidence) and sign each response over `model:sha256(request):sha256(response)`.

## Consequences

- The proof covers the model run, not our server. Our server still sees the diff (see
  `THREAT_MODEL.md`; fixed in ROADMAP v0.2).
- Trust rests on Intel and NVIDIA hardware and on NEAR's published measurements.
- ZK proof of LLM inference is not practical at this size today.
- The design depends on NEAR AI Cloud. That is intentional: at a NEAR hackathon, the project
  must not work without NEAR.
