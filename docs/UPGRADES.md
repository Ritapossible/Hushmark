# Upgrades: from a working check to a product teams adopt

Decided by Rita on 2026-11-06. Built in this order; each one ships as its own pull request
and is done only when its "done when" is true. Update the **Status** column as work lands.
Background: [ADR-0010](adr/0010-github-app-and-mcp-server.md).

| # | Upgrade | Why a team needs it | Status |
|---|---|---|---|
| 1 | **One-click install: the GitHub App** | Teams install apps, not copied workflow files | built and tested (PR #14); deploy needs Rita |
| 2 | **MCP server for agents** | Agents can check what they read before acting on it | not started |
| 3 | **Path ignores in `.hushmark.yml`** | Big repositories (vendored code, generated docs) stop hitting the 20-region cap | not started |
| 4 | **Public receipt verifier** | Anyone can check a receipt without trusting us; makes "verifiable" tangible | not started |
| 5 | **"How to trust this" page** | Security reviewers get what is and is not proved in one page, linked from every check | not started |

Feature freeze: **Monday 9 November**. Submission: before **14 November 23:59 UTC**.

## 1. One-click install: the GitHub App

- A webhook server (`hushmark/app.py` for the logic, `hushmark/server.py` for HTTP) that
  verifies every delivery's signature before reading it, answers GitHub at once, and reviews
  in a background worker with the same `service.run_check` as the Action.
- Events: `pull_request` (opened, synchronize, reopened, edited) and `issue_comment` with
  `/hushmark` from someone with admin or maintain permission (`not_maintainer` otherwise).
- An app manifest, so creating the App is one click, and a deploy file for a free host.
- The receipt (hashes only) goes into the Check Run's details, since the App keeps no
  artifacts.
- Daily budget per installation, kept in memory (resets when the server restarts; stated).

**Done when:** a PR on a repository other than this one gets a `Hushmark` check through the
App, and a `/hushmark` comment from a maintainer re-runs it. The server stays up until at
least 25 November.

## 2. MCP server for agents

- Run locally by the agent over stdio. Tools: `scan` (offline, free), `review` (excerpts
  only to the TEE, checks a–g, a receipt), `verify_receipt` (offline).
- Never returns hidden text raw: locations, detector names, excerpts with invisible
  characters as visible tags, links in a rationale shown as "link".
- Install snippets for Claude Code and Cursor.

**Done when:** an agent calls `scan` on R1's input and gets both regions; `verify_receipt`
passes R1's receipt and refuses a tampered one.

## 3. Path ignores

- `.hushmark.yml` gains `ignore:` (glob patterns), still read from the base commit only.
- Agent rules files can never be ignored: an ignore pattern that matches one is
  `config_invalid`, so a PR cannot hide a rules-file change behind a broad pattern.
- The PR title and body are always scanned.

**Done when:** a diff with 25 hidden regions under `vendor/` passes with `ignore: [vendor/**]`,
and `ignore: ["**"]` still reviews `AGENTS.md`.

## 4. Public receipt verifier

- A command (`python -m hushmark.verify_receipt receipt.json attestation.json`) and a page on
  the website that runs the same checks in the browser where possible, and says which checks
  need the command.
- Shows each check (nonce, signature, attestation a–e) passing or failing, and the NEAR anchor
  lookup for the receipt's key.

**Done when:** PR #8's receipt verifies end to end, and changing one byte fails a named check.

## 5. "How to trust this" page

- One page for security reviewers: what is proved, what is not, what each check means, how to
  verify a receipt yourself, and the threat model in plain words.
- Linked from every Check Run summary.

**Done when:** every Check Run links to it, and every claim on it links to the code or test
that backs it.
