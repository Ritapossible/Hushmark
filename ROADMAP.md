# Roadmap

Each phase has a **gate**: something true in the real world before the next phase starts.
Features without gates are how products get built that nobody uses.

## v0.1: hackathon (1–14 November 2026)

See `docs/PLAN.md`. Automatic required check on every pull request; diff, title, body and
agent rules files scanned; excerpts only to the model; warn or block mode; NEAR testnet
anchor; offline fixtures.

Weekend of 7–8 November ([ADR-0010](docs/adr/0010-github-app-and-mcp-server.md)): the GitHub
App with a webhook server (one-click installs, `/hushmark` re-runs), and an **MCP server** so
agents can call `scan`, `review` and `verify_receipt` themselves. The MCP server brings part
of v0.3 forward.

## v0.2: complete the trust claim (December 2026 – January 2027)

- Run the Hushmark service inside a confidential VM, so the diff never sits on a host
  outside a TEE. **This is the most important item on this roadmap.**
- Public verifier: a CLI and a web page where anyone pastes a receipt and sees each check.
- Anchors on NEAR mainnet.
- **Free open-source CLI and pre-commit hook** with the same detectors, offline, no account.
  This is the adoption funnel: developers meet Hushmark locally, teams add the app for
  attested review.
- GitHub Marketplace listing with a free tier for public repositories.
- Look at GitHub's own hidden-text warnings and drop any detector they make redundant.

**Gate:** three repositories we do not own have installed it and run it more than once.

## v0.3: from pull request reviewer to agent input firewall (Q1 2027)

- Scan more of what agents read: issues and issue comments, linked docs, dependency READMEs.
- API and middleware that check MCP tool results before an agent reads them.
- `.hushmark.yml`: path ignores and per-path modes.

**Gate:** one design partner, a company with an internal AI agent rollout, using it weekly.

## v1.0: a product people pay for (Q2 2027)

- GitLab support. Self-hosted or customer-cloud deployment.
- Organization view: receipts, findings over time, audit export for compliance.
- Pricing: free for public repositories, paid for private ones. Option to explore: prepaid
  scan credits held in the NEAR contract and debited per anchored receipt, so teams and their
  agents can pay in NEAR or stablecoins.
- SOC 2 readiness checklist (not yet the audit).

**Gate:** first paying customer.

## Distribution (from v0.1 onward)

- Post write-ups of real hidden-instruction attacks with the fixture and the receipt.
- NEAR community: NEAR Legion, NEAR developer channels.
- Product Hunt after v0.2, when the server runs in a TEE and the claim covers the host.
- Wallet connectors (e.g. Aurora Intent Connect) do not apply: Hushmark has no wallet flow.

## Not on the roadmap

General code-quality review, general vulnerability finding, running or sandboxing code.
Saying no to these is what keeps Hushmark different from every general AI reviewer.
