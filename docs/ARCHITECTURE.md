# Architecture

Status: design, v0.1 scope (ADR-0007). Facts about NEAR AI Cloud come from its verification
docs and from checks run on 2026-11-01 (links at the end). Anything not confirmed is marked
**unverified** and listed in `OPEN_QUESTIONS.md`.

## 1. Trust boundaries

```
 GitHub (untrusted input)             Hushmark service (our code)                NEAR AI Cloud (TEE)
 ┌───────────────────────┐  webhook  ┌──────────────────────────────────────┐  HTTPS  ┌──────────────────┐
 │ PR diff, title, body, │──(HMAC)─▶│ 1 Trigger   PR event or /hushmark      │         │ Gateway (TDX)    │
 │ comments, fork authors│           │ 2 Fetch     pinned diff + config(base) │         │ Model TEE (GPU)  │
 └───────────────────────┘           │ 3 Scan      detectors on ALL input     │         │                  │
            ▲                        │   └─ no candidates → success, no model │         │                  │
            │                        │ 4 Infer     excerpts only, diff = data │───────▶│ completion       │
            │ Check Run              │ 5 Verify    quote+nonce+sig+grounding  │◀───────│ signature        │
            │ (annotations)          │ 6 Receipt   canonical JSON, hashes only│         │ attestation      │
            └────────────────────────│ 7 Report    one Check Run per head SHA │         └──────────────────┘
                                     └────────────────┬─────────────────────┘
                                                      │ receipt hash
                                                      ▼
                                        NEAR testnet contract: anchor(key_hash, receipt_hash)
                                        called with a function-call access key
```

- **Everything from GitHub is untrusted.** The diff, title, body, comments, usernames, and
  anything in the pull request's head branch, including a changed `.hushmark.yml`.
- **The model's output is untrusted until step 5 passes.** The signature proves where it
  came from, not that it is right. Step 5 checks both.
- **Our service is trusted for the pipeline logic and it sees the full diff.** It is not
  inside a TEE in v0.1. `THREAT_MODEL.md` says so; `ROADMAP.md` v0.2 fixes it. Only
  excerpts ever leave our service, and only to an attested TEE.

## 2. Pipeline

### Step 1: Trigger (`.github/workflows/hushmark.yml`, or the App: `hushmark/app.py`, `hushmark/server.py`)
- **Automatic:** `pull_request` events `opened`, `synchronize`, `reopened`, `edited`
  (`edited` because the title and body are scanned). (`check_run` `rerequested` is not
  handled yet; use `/hushmark`.)
- **Manual re-run (GitHub App):** an `issue_comment` on a pull request whose body is exactly `/hushmark`.
  Only `role_name ∈ {admin, maintain}` from
  `GET /repos/{owner}/{repo}/collaborators/{login}/permission`; bots rejected.
  Refusal: `not_maintainer`, no model call.
- App: verify `X-Hub-Signature-256` with a constant-time compare (401 `webhook_invalid`).
  A redelivered `X-GitHub-Delivery` ID is acknowledged but not reviewed again.
- Immediately create the Check Run `Hushmark` on the head SHA with status `in_progress`.

### Step 2: Fetch (`hushmark/github.py`, `hushmark/service.py`)
- Read `base.sha`, `head.sha`, `title` and `body` from the pull request.
- Diff: `GET /repos/{owner}/{repo}/compare/{base_sha}...{head_sha}` with
  `Accept: application/vnd.github.diff`. Both SHAs pinned at trigger time.
- If GitHub cannot return the full diff (too large, or truncated), refuse with
  `diff_unavailable`. Never scan part of a diff silently.
- **Config from the base branch only:** `GET /repos/{owner}/{repo}/contents/.hushmark.yml?ref={base_sha}`.
  A pull request cannot change how it is judged. Missing file means defaults.
- `input_sha256 = SHA-256(diff bytes ‖ 0x00 ‖ title ‖ 0x00 ‖ body)`, all UTF-8.

### Step 3: Scan (`hushmark/scan.py`)
Deterministic detectors over the **whole** diff, the title and the body. No size cap here.
Each hit becomes a candidate `{id, source, file, line, span, detector}`, where `source` is
`diff`, `pr_title` or `pr_body`.

| Detector | Matches |
|---|---|
| `html_comment` | `<!-- ... -->` in `.md`, `.mdx`, `.rst`, `.html`, and in the PR body |
| `zero_width` | U+200B–U+200D, U+2060, U+FEFF, anywhere |
| `bidi` | U+202A–U+202E, U+2066–U+2069 (Trojan Source), anywhere |
| `tag_chars` | U+E0000–U+E007F (invisible "tag" characters), anywhere |
| `hidden_html` | `<details>`, the `hidden` attribute, `display:none`, `visibility:hidden`, `font-size:0`, and alt text or link titles of 40+ characters |
| `agent_rules_file` | every added line in `AGENTS.md`, `CLAUDE.md`, `.cursorrules`, `.cursor/rules/**`, `.github/copilot-instructions.md`, `.windsurfrules`, `GEMINI.md` |
| `agent_phrase` | weak signal only, inside the above: `ignore previous`, `you are`, `curl ... \| sh` |

- **No candidates:** Check Run `success`, "No hidden regions found." **No model call, no
  cost, no receipt.** This is the common case.
- **Over the cap** (more than 20 candidates, or more than 200 excerpt lines): refuse with
  `too_many_candidates`. Check Run `neutral`, with the scanner's hits as annotations marked
  *unconfirmed*. No model call.

### Step 4: Infer (`hushmark/infer.py`)
- **Excerpts only.** Each candidate plus up to 10 lines of context on each side, taken from
  the diff hunk (or from the title or body). The rest of the diff never leaves our service.
- Model: `z-ai/glm-5.3-flash` (`provider_tee` signature verified end to end 2026-11-02). It is
  a reasoning model, so `max_tokens` must leave room for reasoning before the JSON answer.
  It must return `signature_kind: provider_tee`.
  Canonical model ID, header `x-no-aliasing: true`.
- Fixed system prompt in `prompts/v1.txt`; its SHA-256 is `prompt_hash`.
- Excerpts go inside a random boundary (`<<<EXCERPTS-{16 random hex}>>>`). The prompt says
  everything inside it is data written by an adversary.
- `temperature: 0`, no `tools`, no streaming, `Accept-Encoding: identity`.
- Keep the **exact** request and response bytes for the signature check.
- **Budget:** at most N model calls per installation per day (default 200). Over budget:
  refuse with `budget_exceeded`, Check Run not verified with unconfirmed annotations
  (`neutral` in warn mode, `failure` in block mode).

Required output (validated in step 5g):
```json
{"findings":[{"candidate_id":"c3","kind":"injection",
              "rationale":"Instructs an AI agent to run a remote script.","severity":"high"}]}
```
The model returns only `candidate_id`. File and line come from our own candidate record, so
the model cannot point anywhere else.

### Step 5: Verify (`hushmark/verify/`)
Every check passes, or the run is refused with that check's reason code and no model
finding is shown.

| # | Check | Reason code |
|---|---|---|
| a | `GET /v1/attestation/report?model=...&nonce=...&signing_algo=ecdsa&signing_address=...` returns a model attestation for the signer | `no_attestation` |
| b | Intel TDX quote valid (`dcap-qvl`), TCB status in allowlist, debug bit off | `quote_invalid` |
| c | `report_data` = signing address right-padded to 32 bytes ‖ nonce; `request_nonce` echoes the nonce | `signer_not_bound` or `nonce_mismatch` |
| d | MRCONFIGID matches `app_compose`; RTMR3 replays from the event log | `measurement_mismatch` |
| e | NVIDIA GPU evidence carries our nonce; NRAS verdict true; every NRAS JWT (overall and per GPU) ES384-verified against NVIDIA's keys (pinned in `fixtures/nvidia/jwks.json` offline), nonce matches, overall token commits to each GPU token by SHA-256 | `gpu_evidence_invalid` |
| f | `GET /v1/signature/{chat_id}`: `text == "{model}:{sha256(req)}:{sha256(resp)}"`, EIP-191 signer equals the attested `signing_address`, `signature_kind == "provider_tee"` | `signature_mismatch` |
| g | Output parses against the schema (else the run is refused: `model_output_invalid`); every `candidate_id` exists in this run | unknown or repeated ids dropped and counted as `rejected_ungrounded` |

- The attestation report is fetched **after** the completion, for the signer that signed
  it. It needs no API key (confirmed 2026-11-01).
- Checks b–e use `dcap-qvl` and NVIDIA NRAS, with NEAR's reference checks ported so each one
  raises (ADR-0006). We do not parse quotes ourselves.
- **Nonce** (ADR-0003): `nonce = SHA-256(JCS(idempotency_key) ‖ salt)`, `salt` 16 fresh
  random bytes per run, stored in the receipt.

### Step 6: Receipt (`hushmark/receipt.py`)
Only for runs that called the model. Defined in `RECEIPT.md`. Canonical JSON (RFC 8785),
`receipt_id = SHA-256(bytes)`. Holds hashes of the input, request, response, attestation
and findings. Never the diff, excerpts or finding text.

Idempotency key: `(repo_id, pr_number, head_sha, input_sha256, model_id, prompt_hash)`.
The same key twice returns the existing receipt and updates the existing Check Run.

### Step 7: Report (`hushmark/report.py`)
One Check Run named `Hushmark` per head SHA, updated in place (its ID is stored).

| Outcome | Conclusion (`mode: warn`, default) | Conclusion (`mode: block`) |
|---|---|---|
| No candidates | `success` | `success` |
| Candidates, no verified findings | `success`, summary "N hidden regions reviewed in a NEAR TEE, none aimed at agents", receipt ID | same |
| Verified findings | `neutral`, one annotation per finding at its file and line | `failure` |
| Refused (`too_many_candidates`, `budget_exceeded`, verification failure, ...) | `neutral`, reason code, scanner hits as *unconfirmed* annotations | `failure` (GitHub counts a neutral required check as passing; an unreadable config is treated as block) |

- Findings in the PR title or body cannot be line annotations; they go in the summary.
- Summary always ends with `receipt: <id>` when there is a receipt.
- Teams make the check required in branch protection, **restricted to the Hushmark app** as
  the source, so another app cannot post a passing check with the same name.
- On a public repository the Check Run is public. That is accepted: an injection is the
  attacker's own text, already public in their pull request (ADR-0007).

### Step 8: Anchor (`hushmark/anchor.py`, `contract/`)
- For every receipt. Contract method `anchor(key_hash, receipt_hash)` panics if `key_hash`
  already exists.
- Contract on a NEAR sub-account (`anchor.<owner>.testnet`), called with a **function-call
  access key** limited to `anchor`, zero deposit. A stolen server key can only add anchors.
- `key_hash = SHA-256(JCS(idempotency_key))`. No repository names on chain.
- A failed anchor never blocks the report. It is retried and recorded (ADR-0004).

## 3. GitHub App permissions

| Permission | Level | Why |
|---|---|---|
| Metadata | read | required by GitHub |
| Contents | read | compare endpoint for the diff; `.hushmark.yml` at base |
| Pull requests | read | PR title, body, SHAs; `pull_request` and PR `issue_comment` events |
| Checks | write | the `Hushmark` Check Run |

Webhook events: `pull_request`, `issue_comment`, `check_run`.
**Unverified:** that `pull_requests: read` is enough to receive `issue_comment` on pull
requests (Q4).

## 4. Configuration

`.hushmark.yml` on the default branch, read at `base_sha`:

```yaml
mode: warn   # warn (default) | block
```

That is the only setting in v0.1. Path ignores and per-path modes are ROADMAP v0.3.

## 5. Run state machine

Each run is a row in SQLite that moves forward only:

```
received → checked_in → fetched → scanned ─┬─▶ reported (no candidates)
                                           └─▶ inferred → verified → receipted → reported
        any step can go to → refused(reason) → reported
anchored is tracked separately: pending → done | failed(retries)
```

On restart, a run resumes from its last state. The Check Run ID is stored, so reporting is
always an update, never a duplicate.

## 6. Proving "no shell"

1. ruff banned-API rule: the `hushmark` package cannot import `subprocess`, `os.system`,
   `os.exec*`, `os.spawn*`, `pty`, `multiprocessing`.
2. Tests install `sys.addaudithook` and fail on `subprocess.Popen`, `os.system`, `os.exec`,
   `os.posix_spawn` and `os.spawn` events while the whole pipeline runs.
3. A test asserts the recorded request body has no `tools` field.

This proves the review code has no path that runs the diff. It does not prove the host
cannot be compromised. See `THREAT_MODEL.md`.

## 7. Offline and live verification

- **Recorded once** with a real key, against a demo repository we control: raw request and
  response bytes, signature JSON, attestation report, Intel collateral, NRAS response.
- `make verify` (offline): every fixture, including the quote checked against saved collateral
  at a pinned time with `dcap_qvl.verify` (confirmed to work 2026-11-01).
- `make verify-live` (network, no key): fetches a fresh attestation for the same model and
  re-checks Intel and NVIDIA online.

## 8. Repository layout

```
hushmark/
  scan.py  excerpt.py  infer.py  nonce.py  receipt.py  config.py
  pipeline.py    one review: scan → excerpt → infer → checks a–g → receipt
  report.py      outcome → Check Run conclusion, summary, annotations
  github.py      GitHub App auth, webhook HMAC, diff, config at base, Check Run calls
  service.py     one pull request from Check Run start to finish
  near.py        live NEAR AI Cloud, Intel PCS and NVIDIA NRAS adapters
  anchor.py      NEAR testnet anchor: Borsh transaction, Ed25519 signing, RPC
  action.py      the GitHub Action entry point
  app.py         the GitHub App: which delivery starts which review, re-runs, budget
  server.py      the App's webhook server (standard library, one background worker)
  verify/  attestation.py  nras.py  signature.py  grounding.py
prompts/v1.txt
fixtures/   inputs/ recordings/ attestation/ nvidia/
tests/      replay.py replays recorded evidence byte for byte
scripts/    day1_check.py record_completion.py record_attestation.py build_site_data.py
site/       landing page and docs
contract/   near-sdk Rust contract, deployed to anchor.hushmark.testnet
```

Refusal codes added while building: `tee_unavailable` (NEAR AI Cloud, Intel or NVIDIA
unreachable), `webhook_invalid` (bad `X-Hub-Signature-256`), `budget_exceeded` (daily review
cap spent) and `internal_error` (Hushmark failed before reviewing; the Check Run is closed as
not verified instead of being left in progress).

## References

- NEAR AI Cloud response signatures: https://docs.near.ai/cloud/verification/cloud-api/response-signatures.md
- Quote, nonce and signer bindings: https://docs.near.ai/cloud/verification/reference/quote-nonce-signer.md
- NEAR AI Cloud verifier (reference, MIT): https://github.com/nearai/nearai-cloud-verifier
- GitHub Checks API: https://docs.github.com/en/rest/checks/runs
