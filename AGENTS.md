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
- Model: `z-ai/glm-5.3-flash` (day-one GO, 2026-11-02). It is a reasoning model: give it
  enough `max_tokens` for reasoning plus the JSON answer. `Qwen/Qwen3.8-27B` timed out twice.
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
- **Built (merged in PR #1):** tooling and CI; attestation checks a–e (offline part)
  tested on two real recorded reports; scanner (all detectors, title, body, rules files);
  `.hushmark.yml` parser. 44 tests, lint and `mypy --strict` clean.
- **Day-one check: GO (2026-11-02)** on GitHub Actions with `z-ai/glm-5.3-flash`: `provider_tee`
  signature over our exact bytes, signer bound into an `UpToDate` TDX quote with our nonce.
  Evidence: artifact `day1-evidence` on Actions run 41432789466.
- **Key handling:** `NEARAI_API_KEY` is a GitHub Actions repository secret. Anything that
  needs the key runs as a manual workflow (`.github/workflows/day1-check.yml` is the pattern).
- **Recorded 2026-11-02:** R1–R3 (`fixtures/recordings/`, Actions run 41433656615) and a GLM
  attestation A2. Model answers: R1 two findings, R2 none (harmless TODO), R3 one. Check f
  (`verify/signature.py`) done; fixtures 01, 04, 05, 06, 07, 10 pass offline.
- **R4 (2026-11-02, run 41441898820):** ordinary `AGENTS.md` style rules, zero findings: the
  rules-file control for R3 (fixture 13). GitGuardian allowlist for `nras.json` added.
- **Branch `build/check-run` (2026-11-02):** check e complete (`verify/nras.py`, NVIDIA keys
  pinned in `fixtures/nvidia/jwks.json`), check g (`verify/grounding.py`, fixture 08),
  receipts (`receipt.py`). 98 tests.
- **No process starts at import:** `cffi` is pinned so pycryptodome never runs `file`; the
  test hook is strict before the first import.
- **Branch `build/site` (on top of `build/check-run`):** static landing page in `site/`
  (ADR-0008). Evidence data generated by `scripts/build_site_data.py`; `tests/test_site.py`
  fails on drift. Live at https://tryhushmark.vercel.app (Vercel, root `site`, security
  headers in `site/vercel.json`). Docs page: `site/docs.html`; keep it in step with the code
  and mark unbuilt features as planned.
- **Branch `build/pipeline` (2026-11-02):** `pipeline.py` (one review, checks a–g, receipt),
  `report.py` (Check Run output, warn/block), `github.py` (App JWT, webhook HMAC, pinned diff,
  config at base, permissions, Check Run calls), `service.py` (one PR end to end), `near.py`
  (live adapters). Tests replay R1–R4 byte for byte (`tests/replay.py`) and mock GitHub with
  respx. Fixtures 02 and 12 covered. 127 tests. New codes `tee_unavailable`, `webhook_invalid`.
- **GitHub Action (ADR-0009):** `.github/workflows/hushmark.yml` on `pull_request_target`
  runs `python -m hushmark.action` from the base branch; it never checks out the PR. Receipts
  are kept as workflow artifacts. `tests/test_action.py` guards the workflow. 131 tests.
- **Next:** merge, demo PR with a hidden instruction on this repo, then the NEAR contract.
  GitHub App and webhook server stay planned.

## Decision log

Newest first. One line each, with a link when there is an ADR.

- 2026-11-02: v0.1 ships as a GitHub Action on `pull_request_target` (no server; rule 10
  stands). See [ADR-0009](docs/adr/0009-github-action-pull-request-target.md).
- 2026-11-02: Check Run pipeline built and tested offline before the GitHub App exists, so
  going live is configuration. Docs page updated: built vs planned.
- 2026-11-02: PR #2 merged; site live on Vercel. Docs page added.
- 2026-11-02: Static landing page in the style Rita chose; own branding and content only.
  See [ADR-0008](docs/adr/0008-static-landing-page.md).
- 2026-11-02: PR #1 merged. Adding PyJWT brought `cffi`, which removed pycryptodome's
  import-time `file` call; `cffi` is now a direct dependency and the guard is strict from the
  first import. New reason code `model_output_invalid` (check g).
- 2026-11-02: Grok review: added R4 as the benign rules-file control before building the
  Check Run, and allowlisted the NVIDIA JWTs that GitGuardian flagged.
- 2026-11-02: Recordings R1–R3 done on GitHub Actions, verified before saving. Days 4–6 of
  the plan are complete ahead of schedule.
- 2026-11-02: Day-one go/no-go passed. Primary model switched to `z-ai/glm-5.3-flash`
  (answered in under 5 s; Qwen3.8-27B gave no answer within 2 or 5 minutes). $1 of credit
  bought with NEAR via PingPay; the NEAR Builders $10 credit is still pending.
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
