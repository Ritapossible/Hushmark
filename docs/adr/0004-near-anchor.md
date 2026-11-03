# ADR-0004: Anchor receipt hashes on NEAR, best effort

- Status: accepted
- Date: 2026-11-01

## Context

Judges should be able to see the NEAR part. Receipts should also be timestamped somewhere we do
not control, and one commit should be reviewed once.

## Decision

A NEAR contract on **testnet** for v0.1 with `anchor(key_hash, receipt_hash)`. It panics if
`key_hash` already exists. The service calls it with a function-call access key limited to
`anchor`, with zero deposit. If the anchor fails, publishing still happens. The run records the
failure and retries.

## Consequences

- The database is the record; the chain is a public copy. One-review-per-commit is enforced by
  the database first and by the contract as a second layer.
- A stolen server key can only add anchors. It cannot move funds.
- Only hashes go on chain. No repository names or usernames.
- Testnet costs nothing. Mainnet is ROADMAP v0.2.

## Implementation (2026-11-02)

- Contract: `contract/` (`near-sdk` 5.30, built with `cargo-near`), deployed on its own
  sub-account `anchor.hushmark.testnet`. Only that account may call `anchor`; `get` is public.
- Caller: `hushmark/anchor.py` signs the call with a function-call access key held as the
  `NEAR_ANCHOR_KEY` secret. The Action adds the transaction link to the check summary, or a
  note when anchoring fails; the check is never blocked.
- `key_hash = SHA-256(JCS(idempotency key))`; `receipt_hash = receipt_id`.
