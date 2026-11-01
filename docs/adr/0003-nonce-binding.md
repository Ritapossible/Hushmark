# ADR-0003: Nonce = SHA-256(idempotency key ‖ fresh salt)

- Status: accepted
- Date: 2026-11-01

## Context

NEAR's attestation report embeds a 32-byte client nonce in the quote's report data. Its docs say
to generate 32 fresh random bytes. We also want the report tied to the commit reviewed.

## Decision

`nonce = SHA-256(JCS(idempotency_key) || salt)`, where `salt` is 16 fresh random bytes per run.
Both the salt and the nonce are stored in the receipt.

## Consequences

- Fresh on every run, so an old report cannot be replayed (fixture 06).
- Anyone with the receipt can recompute the nonce and see it was derived from that commit's key.
- A deterministic nonce (key only) was rejected: a rerun would reuse the nonce and lose freshness.
