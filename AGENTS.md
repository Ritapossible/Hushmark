# AGENTS.md: project memory

This file is the shared memory for every AI agent working in this repository (Claude, Grok,
Codex, or others). Read it before doing anything. Update the **Decision log** and **Current
state** sections when something changes. Keep it short: link to the docs rather than
copying them.

## What Hushmark is

A GitHub App that catches hidden instructions aimed at AI agents in pull requests. It reviews
the diff with a model on NEAR AI Cloud, verifies the TEE attestation and response signature,
and publishes only when every check passes. Full design: `docs/ARCHITECTURE.md`.

**The claim:** nobody can make this reviewer run your code. It has no shell, and its output
is only published if a NEAR AI Cloud TEE signed it.

## Hard rules

These are not up for debate during the hackathon. Changing one needs an ADR in `docs/adr/`.

1. **Never execute the diff.** The core package must not import `subprocess`, `os.system`,
   `pty`, `multiprocessing` or anything that spawns a process. Enforced by a ruff banned-API
   rule and a runtime audit hook in tests.
2. **Never send `tools` to the model.** No tool use, no function calling.
3. **Never store or log the diff, or the text of findings.** Receipts and logs hold hashes only.
4. **Fail closed.** If any verification check fails, nothing is published.
5. **Refuse, never truncate.** A diff over 200 lines is refused with a reason.
6. **Never mock a signature or attestation in a fixture that claims to be real.** Fixtures
   built from recorded evidence say so. Tampered fixtures say exactly what was changed.
7. **Do not write a quote parser.** TDX, RTMR3 and NVIDIA checks go through NEAR's
   verifier code. A verifier failure is a refusal.
8. **Keep the diff's exact bytes.** Do not re-serialize request or response JSON before
   hashing.
9. **Never commit secrets.** No GitHub App private key, webhook secret, NEAR key or
   NEAR AI Cloud key in the repository. Use environment variables.
10. **Scope is fixed.** One finding kind (`injection`, covering hidden instructions). No
    dashboard, no second finding kind, no deployment during the hackathon. New ideas go
    to `ROADMAP.md`.

## Stack (planned)

- Python 3.12, managed with `uv`, dependencies pinned in `uv.lock`
- FastAPI and httpx, pydantic v2 in strict mode at every boundary
- SQLite for state
- `dcap-qvl` and NEAR's verifier reference code for attestation
- `eth-account` for EIP-191 signature recovery
- NEAR contract in Rust (`near-sdk`), deployed to **testnet**
- Tooling: ruff, `mypy --strict`, pytest with recorded HTTP (respx)

## Commands (planned, not yet working)

```sh
make lint          # ruff + mypy --strict
make test          # unit tests
make verify        # all fixtures, offline
make verify-live   # re-verify recorded evidence online
```

## Current state

- **Phase:** design review. No application code.
- **Next:** day-one check from `docs/PLAN.md`: one NEAR AI Cloud test completion and
  its signature.

## Decision log

Newest first. One line each, with a link when there is an ADR.

- 2026-11-01: Repository created. Design docs written for review.
- 2026-11-01: Name chosen: Hushmark. Rejected Undertow (Red Hat's Java web server already
  uses it) and Sealwatch (taken on PyPI).
- 2026-10: Attestation nonce is `SHA-256(idempotency_key ‖ random_salt)`, salt stored in the
  receipt. NEAR requires 32 fresh bytes; this keeps freshness and binds the commit.
  See [ADR-0003](docs/adr/0003-nonce-binding.md).
- 2026-10: If the NEAR anchor fails, still publish. The database is the record; the chain
  holds a copy. See [ADR-0004](docs/adr/0004-near-anchor.md).
- 2026-10: Use NEAR's verifier code, never a custom quote parser.
  See [ADR-0002](docs/adr/0002-verify-with-near-verifier.md).
- 2026-10: Kill condition: no working NEAR AI Cloud key by the end of day two means
  stop. A mocked signature is a failed project.

## Style

- Match the surrounding code. Small modules, one job each.
- Every refusal has a stable reason code (`not_maintainer`, `diff_too_large`,
  `no_attestation`, `signature_mismatch`, `nonce_mismatch`, ...). Tests assert on codes,
  never on message text.
- Logs are structured JSON with `delivery_id` and `receipt_id`. Never log diff content.
- Commits: imperative mood, one change per commit.
