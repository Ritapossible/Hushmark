# ADR-0009: Ship v0.1 as a GitHub Action on `pull_request_target`

- Status: accepted
- Date: 2026-11-02

## Context

The Check Run pipeline is built (`service.run_check`). To run on real pull requests it needs
GitHub's events. A GitHub App with a webhook server needs hosting, and rule 10 forbids
deployment during the hackathon. GitHub Actions needs no server.

A plain `pull_request` workflow runs the workflow file and code from the pull request itself:
a PR could rewrite Hushmark before Hushmark reviews it, and fork PRs get no secrets.

## Decision

Run Hushmark as `.github/workflows/hushmark.yml` on `pull_request_target`:

- The workflow file and Hushmark's code come from the **base** branch
  (`actions/checkout` with `ref: base.sha`, `persist-credentials: false`).
- The pull request is **never checked out or run**. Its diff, title and body are read through
  the API as text, exactly as in the App design. This is the property that makes
  `pull_request_target` safe here; for tools that build or run PR code it is not.
- Token permissions: `contents: read`, `pull-requests: read`, `checks: write`.
- `NEARAI_API_KEY` is a repository secret. Without it, hidden content is reported as not
  verified (`tee_unavailable`), never as a finding.
- The receipt and its attestation report are kept as a workflow artifact.
- `tests/test_action.py` fails if the workflow ever checks out the PR head or widens
  permissions.

## Consequences

- No server to host; rule 10 stands.
- Fork PRs are reviewed too, which can cost model calls. Bounded by: no call without hidden
  regions, the 20-candidate cap, and a daily budget of 50 model-calling reviews per repository
  (`HUSHMARK_DAILY_REVIEWS`), counted from today's receipt artifacts (`actions: read`). Worst
  case about $0.0025 a review, about $0.13 a day. The count is approximate under concurrent
  runs, and a refused review that already called the model is not counted.
- In branch protection, require the `Hushmark` check from GitHub Actions as its source.
- The GitHub App and webhook server (`/hushmark` re-runs, multi-repo installs) stay on the
  roadmap; `service.py` is shared, so both paths run the same code.
