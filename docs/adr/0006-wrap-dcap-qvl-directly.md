# ADR-0006: Wrap `dcap-qvl` and NRAS directly; NEAR's verifier is a reference

- Status: accepted
- Date: 2026-11-01
- Supersedes: the "call NEAR's verifier" part of ADR-0002

## Context

ADR-0002 planned to call `nearai-cloud-verifier` and treat any failure as a refusal. Reading
it showed that it is a set of demo scripts, not a package: checks print `True`/`False` and
carry on, an `OutOfDate` TCB status is accepted, and the NVIDIA NRAS JWT is base64-decoded
without verifying its signature. There is nothing to "fail closed" on.

## Decision

- Quote: call `dcap-qvl` (pinned `0.7.0`) directly: `get_collateral_from_pcs` when recording,
  `verify(raw_quote, collateral, now_secs)` everywhere else. Still no quote parsing of ours.
- Port NEAR's reference checks (report data binding, nonce echo, GPU nonce, MRCONFIGID and
  RTMR3) as small functions that **raise** with a reason code.
- Verify the NRAS JWT signature against NVIDIA's published keys, pinned in the repository.
- TCB status allowlist: `UpToDate` only for recordings; `OutOfDate` is reported, not accepted
  silently. Revisit if the recording on day 5 is `OutOfDate`.
- Credit `nearai-cloud-verifier` (MIT) in the README.

## Consequences

- Slightly more of our code (simple comparisons), but every check fails closed.
- Offline verification is confirmed: a live NEAR quote verified `UpToDate` from collateral
  rebuilt from JSON.
