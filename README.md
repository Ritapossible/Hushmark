# Hushmark

**Catches hidden instructions aimed at AI agents in pull requests, and proves it never ran your code.**

> **Status: design review.** No application code yet. This repository holds the plan,
> architecture, threat model and receipt format for review before the build starts on
> 1 November 2026. Built for the NEAR Hackathon (tracks: *Privacy & Private AI*,
> *AI Security & Defense*).

## The claim

> Nobody can make this reviewer run your code. It has no shell, and its output is only
> published if a NEAR AI Cloud TEE signed it.

Every component exists to make one half of that sentence true and checkable.
`THREAT_MODEL.md` states exactly what is proved and what is not.

## What it does

1. A repository admin or maintainer comments `/advisory` on a pull request.
2. Hushmark fetches the diff, pinned to the exact base and head commits. It never checks out
   or runs the code.
3. Deterministic detectors find hidden content: HTML comments, zero-width characters,
   bidi controls, hidden HTML.
4. A model on NEAR AI Cloud decides whether each hidden region is an instruction aimed at
   an AI agent.
5. Hushmark verifies the TEE attestation, the response signature, and that every finding
   points at a real line in the diff. If any check fails, nothing is published.
6. It writes a receipt that holds hashes only, never the diff, and anchors the receipt's
   hash on NEAR.
7. Public repository: a draft security advisory. Private repository: one review comment
   on the pull request.

## Read in this order

| File | What it is |
|---|---|
| [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) | Pipeline, trust boundaries, every verification check |
| [`THREAT_MODEL.md`](THREAT_MODEL.md) | Attackers, assets, what is and is not proved |
| [`RECEIPT.md`](RECEIPT.md) | Receipt format v1, so anyone can write a verifier |
| [`docs/FIXTURES.md`](docs/FIXTURES.md) | The nine fixtures that make up the judged path |
| [`docs/PLAN.md`](docs/PLAN.md) | The 14-day build plan, with go/no-go conditions |
| [`ROADMAP.md`](ROADMAP.md) | What comes after the hackathon, gated by real use |
| [`docs/adr/`](docs/adr/) | Architecture decision records |
| [`docs/OPEN_QUESTIONS.md`](docs/OPEN_QUESTIONS.md) | Unknowns to settle before or during the build |
| [`docs/REVIEW_REQUEST.md`](docs/REVIEW_REQUEST.md) | What reviewers should challenge, and how to respond |
| [`AGENTS.md`](AGENTS.md) | Project memory and rules for AI agents working in this repo |

## How judges will check it (planned)

```sh
git clone https://github.com/Ritapossible/hushmark && cd hushmark
make verify        # offline: every fixture, no API key, no network
make verify-live   # optional: re-checks the recorded attestation against Intel and NVIDIA
```

The live GitHub App is optional and documented separately.

## License

Apache-2.0. See [`LICENSE`](LICENSE).
