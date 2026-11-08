# Changelog

Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/). Versions follow SemVer.

## [Unreleased]

### Added
- GitHub App webhook server (`hushmark/app.py`, `hushmark/server.py`): one-click installs,
  `/hushmark` re-runs by maintainers, Render blueprint, Dockerfile, set-up guide.
- The receipt (hashes only) is shown in the Check Run details.
- `docs/UPGRADES.md`: the five upgrades for team adoption, in order.
- MCP server for agents (`hushmark/mcp.py`, `hushmark-mcp`): `scan`, `review`,
  `verify_receipt`; no hidden text returned by default.
- `ignore:` path patterns in `.hushmark.yml` (ADR-0011); agent rules files, title and body
  are never ignored, and skipped files are named in the check.
- Site: a Products section on the landing page (GitHub Action, GitHub App, MCP server), and
  the GitHub App and MCP server each have their own docs section and sidebar entry.
- "How to trust a result" page for security reviewers, linked from every check.
- Receipt verifier: `hushmark-verify` command and a verify page on the website; every check's
  details say where to verify its receipt.
- `hushmark/receipt_check.py`: check a receipt without trusting Hushmark, including the NEAR
  anchor lookup (`anchor.lookup`).
- Design documents for review: architecture, threat model, receipt format v1, fixtures,
  build plan, roadmap, ADRs 0001–0005, open questions, agent memory (`AGENTS.md`).
- Project tooling: uv, ruff with banned process APIs, mypy --strict, pytest audit hook, CI.
- Offline attestation verification (checks a–e, NRAS pending) with two real NEAR fixtures.
- Scanner for hidden content in the diff, PR title, PR body and agent rules files.
- `.hushmark.yml` parser (base branch only).
- Manual `day1-check` workflow; day-one go/no-go passed with `z-ai/glm-5.3-flash`.
- Excerpts, nonce derivation, prompt v1, inference call, signature check (check f).
- Real recordings R1–R3 and a GLM attestation A2, verified offline in tests.
- Recording R4 (benign rules-file control) and a GitGuardian allowlist for NRAS tokens.
- NVIDIA NRAS JWT verification with pinned keys (rest of check e), grounding (check g),
  receipts.
- Landing page (`site/`), live on Vercel, and a documentation page (`site/docs.html`).
- Review pipeline, Check Run output (warn/block), GitHub App client and per-PR service,
  tested by replaying the real recordings byte for byte.
- GitHub Action on `pull_request_target` (ADR-0009); first live check on demo PR #6.
- NEAR anchor contract (`contract/`) and the Action's anchor call; deployed to
  `anchor.hushmark.testnet`.
- Daily review budget for the Action (default 50 per repository).
- Block mode on this repository; anatomy figure in the README and docs.
- Refusal code `internal_error`.

### Fixed
- README: the NEAR section explains what each piece does and why the chain holds only two
  hashes (privacy), what the anchor guarantees and what it does not.
- Roadmap: v0.1 lists what shipped; the public verifier (already built) left v0.2; the
  audit's deferred detectors, `make verify-live` and durable App state are planned; the docs
  page mirrors `ROADMAP.md`.
- README: every library, service and tool is listed (HACKATHON.md Q-005), and Quick start
  points judges without a NEAR AI key to the offline path.
- Audit 2026-11-08, block mode: a refusal ended `neutral`, which GitHub counts as passing, so an
  author could merge by provoking one (twenty harmless comments gave `too_many_candidates`).
  In block mode every refusal now fails, and an unreadable config is treated as block.
- Audit 2026-11-08, scanner: the diff was split with `splitlines()`, which also breaks on
  U+2028, `\r`, form feed and others; one such character hid the rest of its hunk. Lines are
  now split on `\n` only, and those characters are a new `line_separator` detector.
- Audit 2026-11-08, scanner: only the `<!--` line of an HTML comment was flagged, so an
  instruction further down never reached the model. The whole comment, through `-->`, is now
  one candidate, including lines added inside a comment that opened on an unchanged line.
- Audit 2026-11-08, receipt verifier: a receipt signed with any key showed "Verified". Without
  the attestation report the verdict is now "signature only; TEE not checked"
  (`hushmark-verify` exits 3), and the browser verifier never says "Verified". A re-run's
  receipt says a different receipt is the anchored one.
- The GitHub App caps model-calling reviews across all repositories
  (`HUSHMARK_TOTAL_DAILY_REVIEWS`, default 100), since every installation spends one key.
- The MCP server answers malformed `arguments` with a tool error instead of exiting.
- `THREAT_MODEL.md` and the trust page no longer imply the TEE's measurements are compared
  with NEAR AI Cloud's published values; they are not, yet (roadmap v0.2).
- Site: inline code showed `<!--` as an arrow ligature; the `font` shorthand had reset
  `font-variant-ligatures`.
- The App server answered HEAD requests with 501, so uptime monitors reported it down and
  stopped keeping Render's free instance awake. `/` now says what the server is.
- A fresh NVIDIA verdict stamped a few seconds after Hushmark's verification time was refused
  as `gpu_evidence_invalid`; `nbf` now allows 120 s of clock skew (expiry is still strict).
- Reviews of several hidden regions no longer refuse with `model_output_invalid`: the model
  had no tokens left to answer after reasoning (`max_tokens` 4,096 → 16,384; timeout 600 s).
- `model_output_invalid` now says where the answer broke (schema location and error type, or
  `finish_reason`) without its content, and the Action and App print refusal details.
- Links in the model's rationale are no longer rendered in the check (shown as "link").
- A GitHub error before the review no longer leaves the `Hushmark` check in progress.
- A malformed `NEAR_ANCHOR_KEY` no longer crashes the check.

### Changed
- Applied design review: claim narrowed to the code, privacy as primary track, NEAR anchor
  never cut, private-repository path kept over the public-advisory path.
- ADR-0007: automatic required check on every pull request, excerpts only to the model,
  one Check Run output with warn/block mode, PR title/body and agent rules files scanned.
- README rewritten to HACKATHON.md's "do X, see Y" format, with NEAR tools, libraries and
  AI-generated code listed.
