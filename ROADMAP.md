# Roadmap

**Where Hushmark is today:** v0.1 is live. It reviews pull requests as a GitHub Action and as a
GitHub App, agents can call it over MCP, and anyone can check a receipt. Everything below v0.1 is
planned.

Each later phase has a **gate**: something true in the real world before the next phase
starts. Features without gates are how products get built that nobody uses.

## v0.1: shipped (NEAR HACKATHON, 1–14 November 2026)

Built and live; see the [README](README.md) for how to try each one.

- **The check:** every pull request's diff, title, body and agent rules files are scanned;
  only the flagged excerpts go to a model in a NEAR AI Cloud TEE; a finding is shown only when
  the attestation and signature verify; warn or block mode, read from the base branch.
- **GitHub Action** on `pull_request_target`, running on this repository
  ([ADR-0009](docs/adr/0009-github-action-pull-request-target.md)).
- **GitHub App** with one-click installs and `/hushmark` re-runs by maintainers, live on
  [hushmark-demo](https://github.com/Ritapossible/hushmark-demo/pull/1)
  ([ADR-0010](docs/adr/0010-github-app-and-mcp-server.md)).
- **MCP server** so agents can call `scan`, `review` and `verify_receipt` themselves
  ([`docs/mcp/README.md`](docs/mcp/README.md)).
- **Receipts anchored on NEAR testnet** (`anchor.hushmark.testnet`), with two verifiers:
  `hushmark-verify` (full check, the TEE included) and a browser page (signature and anchor).
- **Path ignores** in `.hushmark.yml` ([ADR-0011](docs/adr/0011-path-ignores.md)), and a
  [trust page](https://tryhushmark.vercel.app/trust) linking every claim to its code and tests.
- **Self-audit (8 November):** block mode now fails on every refusal, line separators can no
  longer hide a hunk, whole HTML comments are one candidate, and "Verified" requires the TEE
  checks ([`CHANGELOG.md`](CHANGELOG.md)).

## v0.2: complete the trust claim (December 2026 – January 2027)

- Run the Hushmark service inside a confidential VM, so the diff never sits on a host
  outside a TEE. **This is the most important item on this roadmap.**
- Pin the TEE's measurements (MRTD, RTMR0–3, the app compose) to the values NEAR AI Cloud
  publishes, so the attestation names the software, not only genuine hardware
  ([`THREAT_MODEL.md`](THREAT_MODEL.md)).
- Check the TEE in the browser verifier too (Intel's quote and NVIDIA's verdict), so a full
  verdict no longer needs the command line.
- `make verify-live`: re-check the recorded evidence against Intel and NVIDIA online.
- Anchors on NEAR mainnet.
- Durable state for the GitHub App: daily budgets that survive a restart, a bounded review
  queue with one lane per installation, so one busy repository cannot delay the others.
- **Free open-source CLI and pre-commit hook** with the same detectors, offline, no account.
  This is the adoption funnel: developers meet Hushmark locally, teams add the app for
  attested review.
- GitHub Marketplace listing with a free tier for public repositories.

**Gate:** three repositories we do not own have installed it and run it more than once.

## v0.3: from pull request reviewer to agent input firewall (Q1 2027)

- More hidden forms, each added with a fixture of the attack it catches: Markdown comments
  written as link definitions (`[//]: # (...)`), text smuggled in variation selectors, and
  more invisible and direction characters.
- More files agents treat as instructions: `.claude/` (settings, commands, skills),
  `.mcp.json`, `.github/instructions/`, `.clinerules` and others, each scanned as a whole.
- Scan more of what agents read: issues and issue comments, linked docs, dependency READMEs.
- Middleware that checks MCP tool results automatically before an agent reads them, instead
  of waiting for the agent to call `scan`; it also flags plainly visible injections, which the
  scanner deliberately leaves to the model today.
- Per-path modes in `.hushmark.yml`.
- Compare with GitHub's own hidden-text warnings and drop any detector they make redundant.

**Gate:** one design partner, a company with an internal AI agent rollout, using it weekly.

## v1.0: a product teams pay for (Q2 2027)

- GitLab support. Self-hosted or customer-cloud deployment.
- Organization view: receipts, findings over time, audit export for compliance.
- Pricing: free for public repositories, paid for private ones. Option to explore: prepaid
  scan credits held in the NEAR contract and debited per anchored receipt, so teams and their
  agents can pay in NEAR or stablecoins.
- SOC 2 readiness checklist (not yet the audit).

**Gate:** first paying customer.

## Distribution (from v0.1 onward)

- Write-ups of real hidden-instruction attacks, each with its fixture and receipt.
- NEAR community: NEAR Legion, NEAR Builders and the NEAR developer channels.
- List the MCP server on NEAR's Agent Market, so agents can find and use it.
- Product Hunt after v0.2, when the service runs in a TEE and the claim covers the host.

## Not on the roadmap

General code-quality review, general vulnerability finding, running or sandboxing code.
Saying no to these is what keeps Hushmark different from every general AI reviewer.
