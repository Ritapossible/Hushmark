# Build plan: 1–14 November 2026

One person, fourteen days. **Submit on 13 November**, after a clean clone passes. The deadline
is 14 November 23:59 UTC; the 14th is a buffer only.

## Go/no-go conditions

| When | Condition | If it fails |
|---|---|---|
| End of day 2 | A NEAR AI Cloud completion returns a `provider_tee` signature that verifies against the attested signing address | **Stop.** A mocked signature is a failed project. Pick a different idea. |
| End of day 2 | Know whether NEAR's verifier runs offline | Move checks b, d, e to `make verify-live` (see `ARCHITECTURE.md` §6) |
| End of day 9 | Fixtures 01–12 pass locally | Cut the live app, then `mode: block`. Keep the anchor. |
| Day 13 | Fresh clone on a clean machine passes `make verify` | Fix before submitting. Do not submit red. |

## Order of work

Recording first, web app last.

| Day | Date | Deliverable | Done when |
|---|---|---|---|
| 1 | 1 Nov | NEAR AI Cloud key works. `scripts/day1_check.py` passes. Read `nearai-cloud-verifier`. **Nothing else today.** | Signature recovers to the attested address |
| 2 | 2 Nov | Repo tooling: `uv`, ruff, mypy, pytest, CI, Makefile. GitHub App registered with the ADR-0007 permissions. A Check Run with one annotation posted by hand from the app. | CI green on an empty package. Q4 answered. |
| 3 | 3 Nov | `scan.py`: every detector over diff, title and body, including `agent_rules_file`; `config.py` (base branch only) | Unit tests per detector, including the harmless TODO; fixtures 09, 11, 12 |
| 4 | 4 Nov | Demo repository with the three PRs (R1–R3). `excerpt.py` and `infer.py` with raw-bytes capture. | Request holds excerpts only, no `tools`, exact bytes saved |
| 5 | 5 Nov | **Record R1, R2, R3, A1, A2** (`docs/FIXTURES.md`) | Evidence committed under `fixtures/` |
| 6 | 6 Nov | `verify/signature.py` (check f) and report-data and nonce binding (check c) | Fixtures 05, 06 pass |
| 7 | 7 Nov | `verify/attestation.py` on `dcap-qvl` and NRAS, NEAR's checks ported to raise (checks a, b, d, e; ADR-0006) | Fixture 04 passes; every failure maps to a reason code |
| 8 | 8 Nov | `verify/grounding.py` (check g) and output schema | Fixture 08 passes |
| 9 | 9 Nov | `receipt.py`, idempotency, `trigger.py`, budget | Fixtures 01, 02, 03, 07, 10 pass. Audit-hook test passes. |
| 10 | 10 Nov | `report.py`: one Check Run per head SHA, annotations, warn/block | End-to-end on the demo repository |
| 11 | 11 Nov | NEAR contract on testnet, function-call key, `anchor.py` | Second anchor for the same key panics. **Never cut.** |
| 12 | 12 Nov | README final, demo video, threat model reviewed against the code | Video under 90 seconds, states the excerpt cap plainly |
| 13 | 13 Nov | Fresh clone test, tag `v0.1.0`, X post, **submit** | Form sent |
| 14 | 14 Nov | Buffer only | |

## Cut list, in order

If behind schedule, cut from the top:

1. Live GitHub App demo (keep offline fixtures; HACKATHON.md Q-012 allows a local demo)
2. `mode: block` (keep `warn`)
3. `/hushmark` manual re-run (keep automatic runs)

Never cut fixtures, the verification checks, the threat model, or the NEAR anchor. The demo
needs one happy path where the second `anchor` for the same key panics.

## Submission checklist

- [ ] Repository public, `make verify` green on a fresh clone
- [ ] README follows HACKATHON.md: "do X, see Y" steps, no marketing, NEAR tools named,
      libraries and AI-generated code listed (Q-005)
- [ ] X post (posted by Rita, not an agent): says it was built at NEAR HACKATHON, tags
      @NEARProtocol and #NEARHackathon, leads with the user problem, shows one complete
      moment, says what NEAR does in it, ends with a next step. Optional: @NearLegion,
      @NearBuilders
- [ ] Form fields: project name, lead name, email, size `1`, tracks `privacy` and
      `security`, a **mainnet** NEAR payout account, repository URL, X post URL,
      20–2,000 character description
- [ ] Consent, verbatim: "I agree that the organizers may use these details to review our
      submission and contact us about this hackathon."
- [ ] An agent may prepare the payload but must print it and wait for Rita's confirmation.
      The form cannot be edited after sending. Read it twice.
