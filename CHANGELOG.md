# Changelog

Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/). Versions follow SemVer.

## [Unreleased]

### Added
- Design documents for review: architecture, threat model, receipt format v1, fixtures,
  build plan, roadmap, ADRs 0001–0005, open questions, agent memory (`AGENTS.md`).
- Project tooling: uv, ruff with banned process APIs, mypy --strict, pytest audit hook, CI.
- Offline attestation verification (checks a–e, NRAS pending) with two real NEAR fixtures.
- Scanner for hidden content in the diff, PR title, PR body and agent rules files.
- `.hushmark.yml` parser (base branch only).
- Manual `day1-check` workflow; day-one go/no-go passed with `z-ai/glm-5.3-flash`.
- Excerpts, nonce derivation, prompt v1, inference call, signature check (check f).
- Real recordings R1–R3 and a GLM attestation A2, verified offline in tests.

### Changed
- Applied design review: claim narrowed to the code, privacy as primary track, NEAR anchor
  never cut, private-repository path kept over the public-advisory path.
- ADR-0007: automatic required check on every pull request, excerpts only to the model,
  one Check Run output with warn/block mode, PR title/body and agent rules files scanned.
- README rewritten to HACKATHON.md's "do X, see Y" format, with NEAR tools, libraries and
  AI-generated code listed.
