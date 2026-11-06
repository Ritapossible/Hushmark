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
