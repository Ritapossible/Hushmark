# Roadmap

Each phase has a **gate**: something true in the real world before the next phase starts.
Features without gates are how products get built that nobody uses.

## v0.1: hackathon (1–14 November 2026)

See `docs/PLAN.md`. One finding kind, pull requests only, diffs up to 200 lines, NEAR testnet
anchor, offline fixtures.

## v0.2: complete the trust claim (December 2026 – January 2027)

- Run the Hushmark service inside a confidential VM, so the diff never sits on a host
  outside a TEE. **This is the most important item on this roadmap.**
- Public verifier: a CLI and a web page where anyone pastes a receipt and sees each check.
- Anchors on NEAR mainnet.
- Diffs over 200 lines: split into chunks, one receipt per chunk, plus a receipt over all of
  them.
- Look at GitHub's own hidden-text warnings and drop any detector they make redundant.

**Gate:** three repositories we do not own have installed it and run it more than once.

## v0.3: from pull request reviewer to agent input firewall (Q1 2027)

- Scan more of what agents read: PR descriptions, issues, linked docs, dependency READMEs,
  agent rules files (`.cursorrules`, `CLAUDE.md`, `AGENTS.md`).
- API and middleware that check MCP tool results before an agent reads them.
- `.hushmark.yml` policy file: block, warn or log, per path.
- Results as a GitHub Check that shows the same output whatever the result.

**Gate:** one design partner, a company with an internal AI agent rollout, using it weekly.

## v1.0: a product people pay for (Q2 2027)

- GitLab support. Self-hosted or customer-cloud deployment.
- Organization view: receipts, findings over time, audit export for compliance.
- Pricing: free for public repositories, paid for private ones.
- SOC 2 readiness checklist (not yet the audit).

**Gate:** first paying customer.

## Not on the roadmap

General code-quality review, general vulnerability finding, running or sandboxing code.
Saying no to these is what keeps Hushmark different from every general AI reviewer.
