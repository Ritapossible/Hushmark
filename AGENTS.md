# AGENTS.md: project memory

This file is the shared memory for every AI agent working in this repository (Claude, Grok,
Codex, or others). Read it before doing anything. Update the **Decision log** and **Current
state** sections when something changes. Keep it short: link to the docs rather than
copying them.

## What Hushmark is

A GitHub check that stops hidden instructions aimed at AI agents from being merged. It runs
on every pull request, scans the whole diff, title, body and agent rules files with
deterministic detectors, and sends only the suspicious excerpts to a model in a NEAR AI Cloud
TEE. It shows a model finding only when the attestation and signature verify. Full design:
`docs/ARCHITECTURE.md`. Goal: a product teams adopt, not a demo.

**The claim:** the review code has no shell, so nothing in a pull request can make it run
code. A finding is shown only if it was signed inside a NEAR AI Cloud TEE for that exact
input. This is about our code, not the host (see `THREAT_MODEL.md`). Never word it more
strongly than that.

## Hard rules

These are not up for debate during the hackathon. Changing one needs an ADR in `docs/adr/`.

1. **Never execute the diff.** The core package must not import `subprocess`, `os.system`,
   `pty`, `multiprocessing` or anything that spawns a process. Enforced by a ruff banned-API
   rule and a runtime audit hook in tests.
2. **Never send `tools` to the model.** No tool use, no function calling.
3. **Never store or log the diff, or the text of findings.** Receipts and logs hold hashes only.
4. **Fail closed.** If any verification check fails, nothing is published.
5. **Refuse, never truncate.** Detectors scan everything. Over 20 candidates or 200 excerpt
   lines, refuse with `too_many_candidates`. If GitHub cannot return the full diff, refuse
   with `diff_unavailable`.
6. **Never mock a signature or attestation in a fixture that claims to be real.** Fixtures
   built from recorded evidence say so. Tampered fixtures say exactly what was changed.
7. **Do not write a quote parser.** Quote parsing and verification go through `dcap-qvl`,
   GPU evidence through NVIDIA NRAS with its JWT signature verified. We port NEAR's
   reference checks so that each one raises; a failure is a refusal. See ADR-0006.
8. **Keep the diff's exact bytes.** Do not re-serialize request or response JSON before
   hashing.
9. **Never commit secrets.** No GitHub App private key, webhook secret, NEAR key or
   NEAR AI Cloud key in the repository. Use environment variables.
10. **Scope is fixed.** One finding kind (`injection`, covering hidden instructions). No
    dashboard, no second finding kind, no deployment during the hackathon. New ideas go
    to `ROADMAP.md`.
11. **Excerpts only leave the service.** The full diff, title and body never go to the model
    or anywhere else; only candidate excerpts go to the attested TEE.
12. **Config comes from the base commit.** Never read `.hushmark.yml` from the PR head.
13. **No model call without candidates.** A PR with no hidden regions costs nothing.

## Hackathon rules for agents (from HACKATHON.md)

Never do any of these without Rita's explicit confirmation in the conversation:
submit the hackathon form, post on X or elsewhere, change the repository's visibility,
force-push, sign transactions, spend tokens, deploy to mainnet, or commit secrets.
An agent may prepare the submission payload, but must print it and wait.

## Stack (planned)

- Python 3.12, managed with `uv`, dependencies pinned in `uv.lock`
- FastAPI and httpx, pydantic v2 in strict mode at every boundary
- GitHub Checks API for all output (no comments, no advisories)
- SQLite for state
- `dcap-qvl` (pinned `0.7.0`) for TDX quotes; NVIDIA NRAS for GPU evidence
- Model: `Qwen/Qwen3.8-27B` (model TEE attestation confirmed); fallback `z-ai/glm-5.3-flash`
- `eth-account` for EIP-191 signature recovery
- NEAR contract in Rust (`near-sdk`), deployed to **testnet**
- Tooling: ruff, `mypy --strict`, pytest with recorded HTTP (respx)

## Commands

```sh
make install       # uv sync --locked
make lint          # ruff + format check + mypy --strict
make test          # all tests
make verify        # all offline fixtures, no key, no network
make verify-live   # (planned) re-verify recorded evidence online
```

## Current state

- **Phase:** building v0.1. Design settled by ADR-0007 (2026-11-01). No more design docs.
- **Built (branch `build/foundation`):** tooling and CI; attestation checks a–e (offline part)
  tested on two real recorded reports; scanner (all detectors, title, body, rules files);
  `.hushmark.yml` parser. 44 tests, lint and `mypy --strict` clean.
- **Blocked on the API key:** `scripts/day1_check.py` (completion signature, check f), then
  recordings R1–R3. Still the go/no-go for the end of 2 November.

## Decision log

Newest first. One line each, with a link when there is an ADR.

- 2026-11-01: Built key-independent parts while waiting for NEAR AI credit. New reason code
  `signer_not_bound` (check c) and `config_invalid`.
- 2026-11-01: Redesigned for team adoption: automatic check on every PR, excerpts only to
  the model, one Check Run output with warn/block, PR title/body and rules files scanned,
  config from base. Drops `/advisory` and draft advisories. HACKATHON.md rules added.
  See [ADR-0007](docs/adr/0007-automatic-check-with-excerpts.md).
- 2026-11-01: Commits are authored by Rita (repository owner); Claude is co-author.
- 2026-11-01: Attestation verified for real, no key needed: Qwen3.8-27B and GLM-5.3-flash
  quotes `UpToDate` from saved collateral, report data binds signer and nonce, GPU nonce
  matches. NEAR's verifier prints instead of failing, so we wrap `dcap-qvl` directly.
  See [ADR-0006](docs/adr/0006-wrap-dcap-qvl-directly.md).
- 2026-11-01: Design review applied. Claim narrowed to the code, not the host. Privacy is
  the primary track, security second. The NEAR anchor is never cut; the live app is cut
  first, then the public-advisory path. The private path stays: NEAR's own idea list asks
  for private PR review. The 200-line cap is stated in the demo, not designed around.
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
- Every refusal has a stable reason code (`not_maintainer`, `too_many_candidates`,
  `diff_unavailable`, `budget_exceeded`, `no_attestation`, `signature_mismatch`,
  `nonce_mismatch`, ...). Tests assert on codes,
  never on message text.
- Logs are structured JSON with `delivery_id` and `receipt_id`. Never log diff content.
- Commits: imperative mood, one change per commit.
