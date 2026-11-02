# Architecture decision records

One decision per file. Never edit an accepted ADR's decision; write a new one that supersedes it.

| ADR | Decision |
|---|---|
| [0001](0001-tee-attestation.md) | Prove the review with NEAR AI Cloud TEE attestation |
| [0002](0002-verify-with-near-verifier.md) | Use NEAR's verifier code, never our own quote parser |
| [0003](0003-nonce-binding.md) | Nonce = SHA-256(idempotency key ‖ fresh salt) |
| [0004](0004-near-anchor.md) | Anchor receipt hashes on NEAR testnet, best effort |
| [0005](0005-pinned-diff-and-refusal.md) | Pinned diff; refuse over 200 lines, never truncate |
| [0006](0006-wrap-dcap-qvl-directly.md) | Wrap `dcap-qvl` and NRAS directly; NEAR's verifier is a reference, not a library (supersedes part of 0002) |
| [0007](0007-automatic-check-with-excerpts.md) | Automatic required check, excerpts only, one Check Run output (supersedes the trigger and outputs, and part of 0005) |
| [0008](0008-static-landing-page.md) | A static landing page in `site/` is not a dashboard; its evidence is computed by our verifiers |
