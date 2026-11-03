# ADR-0010: Build the GitHub App server and an MCP server during the hackathon

- Status: accepted
- Date: 2026-11-03
- Decided by: Rita

## Context

Rule 10 in `AGENTS.md` said "no deployment during the hackathon", and ADR-0009 shipped v0.1
as a GitHub Action for that reason. That rule was ours, not the hackathon's. Re-reading the
official rules (https://nearhackathon.com/HACKATHON.md) on 2026-11-03 showed the opposite:
a hosted demo is a plus, and it must stay up until at least 18 November.

The goal is a product teams would consider, not a demo. Two things stand between v0.1 and
that:

- **The GitHub App.** Teams install apps, not copied workflow files: one click for many
  repositories, and `/hushmark` re-runs by a maintainer. Its client code (app token, webhook
  signature check, maintainer check) is already built and tested in `github.py` and
  `service.py`; only the server and the registration are missing.
- **Agents.** Today Hushmark guards what gets merged. Agents also read issues, dependency
  READMEs and other tools' output before acting. An MCP server lets an agent check that text
  itself, which brings ROADMAP v0.3 ("agent input firewall") forward.

## Decision

Lift rule 10's "no deployment" for exactly these two components, built on the weekend of
7–8 November:

1. **GitHub App webhook server.** A small HTTPS server that verifies each webhook
   (`verify_webhook`, `webhook_invalid`), gets an installation token and calls the same
   `service.run_check` the Action uses. `/hushmark` re-runs need admin or maintain
   (`not_maintainer`). Secrets (app private key, webhook secret, NEAR AI key, anchor key)
   live only in the host's environment. It stays up until at least 25 November.
2. **MCP server, run locally by the agent** (stdio, no hosting). Tools:
   - `scan`: the deterministic detectors on any text or diff. Offline and free.
   - `review`: excerpts only to the attested TEE, checks a–g, a receipt. Needs a NEAR AI key
     and stays under the daily budget.
   - `verify_receipt`: checks a receipt and its attestation offline.

Everything else in `AGENTS.md` stands: one finding kind, no dashboard, never run the diff,
never send tools to the model, excerpts only, hashes only, config from the base commit.

## Consequences

- MCP results go straight into an agent's context, so they never return hidden text raw:
  locations, detector names and excerpts with invisible characters written as visible tags,
  and any link in a model rationale shown as "link".
- The App server is a new attack surface holding secrets. It verifies every webhook before
  reading it, and the webhook secret and private key are never logged.
- Without a database, the App behaves like the Action on re-runs (a new review and receipt;
  the contract refuses a second anchor). A database waits for the hosted service in v0.2.
- If the weekend runs short, the MCP server ships first (no hosting risk); the Action keeps
  covering pull requests.
- The Action (ADR-0009) stays supported: both paths run the same code.
