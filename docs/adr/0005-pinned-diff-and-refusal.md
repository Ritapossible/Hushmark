# ADR-0005: Review a pinned diff, refuse rather than truncate

- Status: accepted
- Date: 2026-11-01

## Context

A pull request can change while a review runs, and a large diff may not fit the prompt.

## Decision

Fetch `compare/{base_sha}...{head_sha}` with both SHAs pinned at trigger time. If the diff has
more than 200 lines, refuse with `diff_too_large`. Never review part of a diff silently.

## Consequences

- The receipt covers exactly the bytes that were reviewed.
- Large pull requests are not reviewed in v0.1. Chunking with per-chunk receipts is ROADMAP v0.2.
- A refusal is visible to the operator and in logs, never hidden behind a partial "clean" result.
