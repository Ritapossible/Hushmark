# ADR-0011: Path ignores in `.hushmark.yml`

- Status: accepted
- Date: 2026-11-06
- Decided by: Rita (docs/UPGRADES.md, upgrade 3)

## Context

Hard rule 5 says the detectors scan everything. On a real repository that includes vendored
code, generated documentation and test fixtures that contain hidden content on purpose. On
this repository, PR #15's check reviewed 8 such regions (test strings and documentation
examples) and spent a model call on them. A large repository hits the 20-region cap and is
refused outright. Teams need to say "not here", without opening a hole.

## Decision

`.hushmark.yml` gains `ignore`, a list of at most 50 path patterns (`fnmatch`; `*` also
matches `/`), read from the **base commit only** (rule 12), like `mode`.

- A file whose path matches is not scanned.
- **Agent rules files are never ignored**, whatever the patterns say (`AGENTS.md`, `CLAUDE.md`,
  `.cursorrules`, `.cursor/rules/*`, ... in any folder where the scanner recognises them). A
  pull request cannot hide a rules-file change behind `**`.
- **The PR title and body are always scanned.**
- **Nothing is skipped silently:** the check summary lists the files that were not scanned
  (the first ten by name, and the count).
- A bad list (not a list of non-empty strings, or more than 50) is `config_invalid`.

Rule 5 becomes: detectors scan everything except files the base branch's `ignore` skips.

## Consequences

- A pull request cannot widen `ignore` for itself: the config comes from the base commit. A
  maintainer who merges a wider `ignore` is making a reviewed, visible decision.
- Hidden content in an ignored file is not reviewed. The summary names those files, so a
  reviewer still sees that they changed.
- `input_sha256` and the receipt still cover the whole diff, and the key's `base_sha` names
  the config that applied.
