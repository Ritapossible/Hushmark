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
5. **Refuse, never truncate.** Detectors scan everything, except files the base branch's
   `ignore` skips (never agent rules files, the title or the body; ADR-0011). Over 20
   candidates or 200 excerpt lines, refuse with `too_many_candidates`. If GitHub cannot return the full diff, refuse
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
    dashboard, no second finding kind. Deployment only as ADR-0010 allows: the GitHub App's
    webhook server and the local MCP server. New ideas go to `ROADMAP.md`.
11. **Excerpts only leave the service.** The full diff, title and body never go to the model
    or anywhere else; only candidate excerpts go to the attested TEE.
12. **Config comes from the base commit.** Never read `.hushmark.yml` from the PR head.
13. **No model call without candidates.** A PR with no hidden regions costs nothing.

## Hackathon rules for agents (https://nearhackathon.com/HACKATHON.md, re-read 2026-11-03)

Never do any of these without Rita's explicit confirmation in the conversation: submit the
hackathon form, post on X or elsewhere, make the repository public, **push** or force-push,
sign transactions, spend tokens, deploy to mainnet, or commit secrets. An agent may prepare
the submission payload, but must print it and wait.

Working practice (2026-11-03): when Rita asks for a change, the agent may push it to a
working branch and open a pull request. Merging, pushing to `main`, force-pushing and
deleting branches each need her explicit "merge it" or equivalent.

What the official rules require:

- **Deadline:** 14 November 2026, 23:59 UTC. One submission per repository, and it **cannot
  be edited**. Rita submits next week, after the weekend build.
- **Repository:** public by the deadline and through judging, with a LICENSE. Code from
  19 October 2026 counts; this repository was created on 1 November, so all of it does.
  Libraries and AI-generated code are listed in the README.
- **Demo:** a reproducible README plus a **video** in the X post (screenshots alone are not
  enough). A hosted demo is a plus: keep it up until at least 18 November, ideally
  25 November.
- **X post:** says it was built at NEAR HACKATHON, tags @NEARProtocol and #NEARHackathon
  (optional @NearLegion, @NearBuilders). Posted by Rita.
- **Form:** needs a **mainnet** NEAR payout account (ours are testnet), tracks, the repository
  URL, the X post URL and a 20–2,000 character description.
- **Screening:** Claude Code and Codex check reproducibility and features first; humans decide.
  The README must match the code exactly.

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
- **Live 2026-11-02:** demo PR #6 (do not merge) got a real `Hushmark` check: 2 verified
  findings, receipt artifact checked (hashes only).
- **Branch `build/near-anchor`:** `contract/` (Rust, near-sdk 5.30, 5 unit tests, 106 KB wasm
  via `cargo-near`), `hushmark/anchor.py` (Borsh tx, Ed25519 signing, RPC), Action wiring
  (`NEAR_ANCHOR_ACCOUNT` variable, `NEAR_ANCHOR_KEY` secret). 142 tests.
- **Deployed 2026-11-02 (Rita's OK):** `hushmark.testnet` (faucet) and
  `anchor.hushmark.testnet` (contract; code hash matches the build). Function-call key
  `Gxpb82w5…` limited to `anchor`. PR #6's receipt anchored; a second anchor was refused on
  chain. Keys were handed to Rita; the Action needs secret `NEAR_ANCHOR_KEY` and variable
  `NEAR_ANCHOR_ACCOUNT`.
- **Daily budget:** 50 model-calling reviews per repo per day (`HUSHMARK_DAILY_REVIEWS`),
  counted from receipt artifacts; `budget_exceeded`. 145 tests.
- **Live 2026-11-03:** with `NEAR_ANCHOR_KEY` set, demo PR #8 failed in block mode (1 verified
  finding) and the Action anchored its receipt (tx `4aVFSs9k…`); contract `count` = 2. A
  malformed anchor key no longer crashes the check (PR #10).
- **README review (2026-11-03):** every test file reported; GitHub errors before the review
  now close the Check Run (`diff_unavailable` or new code `internal_error`) instead of
  leaving it in progress. PR #11.
- **Links (Grok review):** any URL or Markdown link in the model's rationale is rendered as
  the word "link" (`report.py`); the 500-character cap stays. 150 tests.
- **Weekend 7–8 November (ADR-0010):** GitHub App with a webhook server (`/hushmark` re-runs,
  one-click installs), and an MCP server so agents can call `scan`, `review` and
  `verify_receipt`. Then upgrades for team adoption.
- **Upgrades (2026-11-06, `docs/UPGRADES.md`):** five, in order. #1 GitHub App built: `app.py`
  (routing, `/hushmark` re-runs, in-memory daily budget), `server.py` (stdlib webhook server,
  signature first, one background worker), `render.yaml`, `Dockerfile`, CI image job, set-up
  guide `docs/github-app/README.md`. The receipt now also appears in the Check Run details.
  179 tests. Deploying it needs Rita (App registration, Render account).
- **Upgrade #2 MCP server (2026-11-06):** `hushmark/mcp.py` (stdlib JSON-RPC over stdio;
  `scan`, `review`, `verify_receipt`; no hidden text returned by default) and
  `hushmark/receipt_check.py` (checks a receipt without trusting us; reused by upgrade #4).
  `hushmark-mcp` command; `claude mcp list` shows it connected. Guide `docs/mcp/README.md`.
  205 tests.
- **Upgrade #3 path ignores (2026-11-06, ADR-0011):** `ignore:` in `.hushmark.yml` (base
  commit only, max 50 fnmatch patterns); rules files, title and body never ignored; skipped
  files named in the summary. This repo ignores `tests/*` and `fixtures/*`. 222 tests.
- **Upgrade #4 receipt verifier (2026-11-06):** `hushmark-verify` (CLI) and `site/verify.html`
  (browser: ID, nonce, TEE signature via vendored @noble bundle, NEAR anchor; CSP allows the
  testnet RPC). Every check's details link to it. PR #17's live receipt is
  `fixtures/receipts/pr17.json` and verifies, anchor included. 228 tests.
- **Upgrade #5 trust page (2026-11-06):** `site/trust.html`: proved / not proved / data flow /
  attackers, every claim linked to code and tests; every check summary ends with a link to it.
  All five upgrades built; the App still needs registering and deploying (Rita). 229 tests.
- **Feature freeze (2026-11-07, Grok review):** no new features. The Action is the demo; the
  submission must not depend on the App being hosted. Only fixes, the video, the X post and the
  submission remain.
- **App demo (Grok, 2026-11-07):** deploy the App and prove it on a repository Rita does not
  own: block-mode failure with a new testnet anchor, a maintainer `/hushmark` re-run, and a
  `not_maintainer` refusal (guide part 4). Put the two URLs in the README. If it is not up by
  Monday 9 November, drop the App from the pitch and submit the Action. Guide fixed: the App
  needs **Issues: Read-only** or GitHub never sends `/hushmark` comments.
- **App live (2026-11-07):** App "Hushmark Check" (ID 5657630) on Render (`hushmark-app.onrender.com`),
  installed on `Ritapossible/hushmark-demo` (block mode). PR #1 there: check failed with 1
  verified finding, receipt `144b8d26…` anchored at block 276,657,517 (signature and anchor
  checked with `hushmark-verify`); Rita's `/hushmark` re-ran it (contract refused a second anchor); a bot's
  `/hushmark` was refused. Gap vs Grok's ask: the demo repo is Rita's own, not a stranger's.
  Keep Render up until 25 November (UptimeRobot on `/healthz`).
- **Audit fixes (2026-11-08, Grok's go):** a self-audit found three breaks in the claim, all
  fixed with failing tests first: block mode passed refusals (`neutral`), one line separator
  hid the rest of a hunk, and the verifier said "Verified" for any self-signed receipt. Also
  whole HTML comments are one candidate, a global App cap, and the threat model no longer
  implies measurements are pinned. 279 tests.
- **Public (seen 2026-11-08):** `Ritapossible/Hushmark` and `Ritapossible/hushmark-demo` are
  public. Keep both public through judging (results by 18 November). The NEAR Builders $10
  NEAR AI credit has arrived; it is the operating budget for live reviews until 25 November.
- **HACKATHON.md re-read 2026-11-08:** README lists every library, service and the AI code;
  the no-key path is linked from Quick start. Submission fields: project name, lead name,
  email, team size (`1`, `2 - 4`, `4 - 6`, `6 - 8`, `8+`), tracks (`privacy`, `security`),
  mainnet payout account (Rita creates it), repo URL, X post URL, description (20–2,000
  characters), consent. One submission per repository; fixes go through request-changes.
- **Next (all need Rita):** mainnet payout account, demo video, X post, then the submission
  before 14 November 23:59 UTC.

## Decision log

Newest first. One line each, with a link when there is an ADR.

- 2026-11-08: Re-read HACKATHON.md against the repo: completed the README's library list
  (`@noble/*`, `esbuild`, `cffi`, fonts, hosting), linked the offline path from Quick start.
  Suggested lowering `HUSHMARK_DAILY_REVIEWS` to 20 now that the repo is public.
- 2026-11-08: Grok review of the self-audit: in block mode any refusal fails (a review that
  could not finish is not a clean review); split diffs on `\n` only; "Verified" only when the
  attestation passed; flag whole HTML comments; keep one anchor per key and say so for
  re-runs; reword, not pin, the measurements this week; the longer detector list waits.
- 2026-11-07: PR #21's check refused with `gpu_evidence_invalid: NRAS token outside its
  validity window`: NVIDIA stamps `nbf` just after our verification time. 120 s leeway on `nbf`
  only (`verify/nras.py`); expired verdicts are still refused. A fix, allowed in the freeze.
- 2026-11-07: PR #20's check refused with `no answer (finish_reason=length)`: GLM spent all
  4,096 tokens reasoning about 3 regions. `max_tokens` is now 16,384 and the TEE timeout 600 s
  (replays pin the recorded 4,096). Worst case about $0.01 a review. A fix, allowed in the freeze.
- 2026-11-07: Grok review: freeze now (all five upgrades merged, PRs #14–#19). The Action is
  the demo; the App's hosting is optional. MCP keeps returning locations only by default.
  The video is the work that changes the score.
- 2026-11-06: Rita: build all five upgrades in `docs/UPGRADES.md`, starting with the GitHub
  App. The App uses the standard library server (no web framework dependency) and Render's
  free plan; use the App or the Action on a repository, not both.
- 2026-11-03: Re-read the official HACKATHON.md: a hosted demo is a plus, so rule 10's "no
  deployment" is lifted for the GitHub App server and a local MCP server. Our agent rules
  now include "push". See [ADR-0010](docs/adr/0010-github-app-and-mcp-server.md).
- 2026-11-03: Grok review: re-runs stay as they are (a new model call is a new receipt; the
  contract refuses a second anchor); no database, since that means hosting.
- 2026-11-03: This repository runs Hushmark in `mode: block` (`.hushmark.yml` on `main`), so a
  verified finding fails the check. Demo PR #8 shows it; PR #6 stays open too.
- 2026-11-02: Grok review: stop site work; deploy the anchor (done, second anchor refused on
  chain) and cap the paid key before leaving `pull_request_target` on (50/day).
- 2026-11-02: Anchor contract on its own sub-account; only the contract account may write;
  the service key is a function-call key limited to `anchor`.
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
