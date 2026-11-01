# Build plan: 1–14 November 2026

One person, fourteen days. **Submit on 13 November**, after a clean clone passes. The deadline
is 14 November 23:59 UTC; the 14th is a buffer only.

## Go/no-go conditions

| When | Condition | If it fails |
|---|---|---|
| End of day 2 | A NEAR AI Cloud completion returns a `provider_tee` signature that verifies against the attested signing address | **Stop.** A mocked signature is a failed project. Pick a different idea. |
| End of day 2 | Know whether NEAR's verifier runs offline | Move checks b, d, e to `make verify-live` (see `ARCHITECTURE.md` §6) |
| End of day 9 | Fixtures 01–09 pass locally | Cut the live app, then the public-advisory path. Keep the anchor. |
| Day 13 | Fresh clone on a clean machine passes `make verify` | Fix before submitting. Do not submit red. |

## Order of work

Recording first, web app last.

| Day | Date | Deliverable | Done when |
|---|---|---|---|
| 1 | 1 Nov | NEAR AI Cloud key works. `scripts/day1_check.py` passes. Read `nearai-cloud-verifier`. **Nothing else today.** | Signature recovers to the attested address |
| 2 | 2 Nov | Repo tooling: `uv`, ruff, mypy, pytest, CI, Makefile. GitHub App registered. Draft advisory created by hand on a public and a private test repo. | CI green on an empty package. Private-repo advisory answer recorded in `OPEN_QUESTIONS.md` |
| 3 | 3 Nov | `scan.py` with every detector | Unit tests per detector, including the harmless TODO |
| 4 | 4 Nov | Demo repository with the injection PR and the clean PR. `infer.py` with raw-bytes capture. | Request body has no `tools`, exact bytes saved |
| 5 | 5 Nov | **Record R1, R2, A1, A2** (`docs/FIXTURES.md`) | Evidence committed under `fixtures/` |
| 6 | 6 Nov | `verify/signature.py` (check f) and report-data and nonce binding (check c) | Fixtures 05, 06 pass |
| 7 | 7 Nov | `verify/attestation.py` wrapping NEAR's verifier (checks a, b, d, e) | Fixture 04 passes; verifier failure maps to a reason code |
| 8 | 8 Nov | `verify/grounding.py` (check g) and output schema | Fixture 08 passes |
| 9 | 9 Nov | `receipt.py`, idempotency, `gate.py`, size cap | Fixtures 01, 02, 03, 07, 09 pass. Audit-hook test passes. |
| 10 | 10 Nov | `publish.py` for both paths, with marker de-duplication | End-to-end on the demo repository |
| 11 | 11 Nov | NEAR contract on testnet, function-call key, `anchor.py` | Second anchor for the same key panics. **Never cut.** |
| 12 | 12 Nov | README final, demo video, threat model reviewed against the code | Video under 90 seconds, states the 200-line cap plainly |
| 13 | 13 Nov | Fresh clone test, tag `v0.1.0`, X post, **submit** | Form sent |
| 14 | 14 Nov | Buffer only | |

## Cut list, in order

If behind schedule, cut from the top:

1. Live GitHub App demo (keep offline fixtures)
2. Public-repository advisory path (keep the private review comment: private PR review is
   what NEAR's own idea list asks for)

Never cut fixtures, the verification checks, the threat model, or the NEAR anchor. The demo
needs one happy path where the second `anchor` for the same key panics.

## Submission checklist

- [ ] Repository public, `make verify` green on a fresh clone
- [ ] X post says it was built at NEAR HACKATHON, includes the demo video
- [ ] Form: team size solo, tracks *Privacy & Private AI* (primary) and *AI Security & Defense*,
      NEAR wallet address, repository link, post link, 20–2,000 character description
- [ ] Consent box ticked (copy the wording from the form itself)
- [ ] The form cannot be edited after sending. Read it twice.
