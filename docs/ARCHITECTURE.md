# Architecture

Status: design, v0.1 scope. Facts about NEAR AI Cloud come from its verification docs
(links at the end). Anything not confirmed is marked **unverified** and listed in
`OPEN_QUESTIONS.md`.

## 1. Trust boundaries

```
 GitHub (untrusted input)            Hushmark service (our code)               NEAR AI Cloud (TEE)
 ┌──────────────────────┐   webhook  ┌─────────────────────────────────────┐   HTTPS  ┌──────────────────┐
 │ PR diff, comments,   │──(HMAC)──▶│ 1 Gate      maintainer? key unused?   │          │ Gateway (TDX)    │
 │ fork authors         │            │ 2 Fetch     diff pinned to base..head │          │ Model TEE (GPU)  │
 └──────────────────────┘            │ 3 Scan      deterministic detectors   │          │                  │
            ▲                        │ 4 Infer     fixed prompt, diff = data │────────▶│ completion       │
            │ publish only if        │ 5 Verify    quote+nonce+sig+grounding │◀────────│ signature        │
            │ step 5 passes          │ 6 Receipt   canonical JSON, no diff   │          │ attestation      │
            └────────────────────────│ 7 Publish   advisory OR review comment│          └──────────────────┘
                                     └───────────────┬─────────────────────┘
                                                     │ receipt hash (best effort)
                                                     ▼
                                       NEAR testnet contract: anchor(key_hash, receipt_hash)
                                       called with a function-call access key
```

- **Everything from GitHub is untrusted.** That includes the diff, titles, comment bodies
  and usernames.
- **The model's output is untrusted until step 5 passes.** The signature proves where it
  came from, not that it is right. Step 5 checks both.
- **Our service is trusted for the gate logic and it sees the diff.** It is not inside a
  TEE in v0.1. `THREAT_MODEL.md` says so, and `ROADMAP.md` v0.2 fixes it.

## 2. Pipeline

### Step 1: Gate (`hushmark/gate.py`)
- Trigger: an `issue_comment` webhook whose body is exactly `/advisory`, on an issue that is
  a pull request. Never runs on `pull_request` events.
- Verify `X-Hub-Signature-256` with a constant-time compare. Reject a reused
  `X-GitHub-Delivery` ID.
- `GET /repos/{owner}/{repo}/collaborators/{login}/permission`. Accept only
  `role_name ∈ {admin, maintain}`. Reject `user.type == "Bot"`. Refusal: `not_maintainer`.
- Idempotency key: `(repo_id, pr_number, head_sha, model_id, prompt_hash)`.
  `repo_id` because names change; `prompt_hash` because a new prompt is a different review.
- Claim the key with `INSERT ... ON CONFLICT DO NOTHING`. If it exists, return the existing
  receipt and do nothing else.

### Step 2: Fetch (`hushmark/fetch.py`)
- Read `base.sha` and `head.sha` from the pull request.
- `GET /repos/{owner}/{repo}/compare/{base_sha}...{head_sha}` with
  `Accept: application/vnd.github.diff`. Pinning both SHAs means a push mid-run cannot
  swap the diff.
- More than 200 lines: refuse with `diff_too_large`. Never truncate.

### Step 3: Scan (`hushmark/scan.py`)
Deterministic detectors. Each hit becomes a candidate `{id, file, line, span, detector}`.

| Detector | Matches |
|---|---|
| `html_comment` | `<!-- ... -->` in `.md`, `.mdx`, `.rst`, `.html` |
| `zero_width` | U+200B–U+200D, U+2060, U+FEFF |
| `bidi` | U+202A–U+202E, U+2066–U+2069 (Trojan Source) |
| `hidden_html` | `<details>`, `alt=`, link titles, `style="display:none"` |
| `agent_phrase` | weak signal only: `ignore previous`, `you are`, `curl ... \| sh` inside the above |

No candidates: finish with zero findings and **no model call**. The model never searches the
diff for hiding places. It only decides whether a candidate is an instruction aimed at an
agent.

### Step 4: Infer (`hushmark/infer.py`)
- Model: `Qwen/Qwen3.8-27B` (model TEE attestation confirmed 2026-11-01; fallback
  `z-ai/glm-5.3-flash`). It must return `signature_kind: provider_tee`.
  Send the canonical model ID with header `x-no-aliasing: true`.
- Fixed system prompt, versioned in `prompts/v1.txt`; its SHA-256 is `prompt_hash`.
- The diff and candidates go inside a random boundary (`<<<DIFF-{16 random hex}>>>`). The
  prompt says everything inside it is data written by an adversary.
- `temperature: 0`, no `tools`, no streaming, `Accept-Encoding: identity`.
- Keep the **exact** request and response bytes. They are hashed for the signature check.

Required output (validated in step 5g):
```json
{"findings":[{"candidate_id":"c3","kind":"injection","file":"docs/setup.md","line":42,
              "rationale":"Instructs an AI agent to run a remote script.","severity":"high"}]}
```

### Step 5: Verify (`hushmark/verify/`)
Every check passes, or the run is refused with that check's reason code.

| # | Check | Reason code |
|---|---|---|
| a | Fetch `GET /v1/attestation/report?model=...&nonce=...&signing_algo=ecdsa`; a report is present | `no_attestation` |
| b | Intel TDX quote valid (`dcap-qvl`), TCB status in allowlist, debug bit off | `quote_invalid` |
| c | `report_data` = signing address right-padded to 32 bytes ‖ nonce; `request_nonce` echoes the nonce | `nonce_mismatch` |
| d | MRCONFIGID matches `app_compose`; RTMR3 replays from the event log | `measurement_mismatch` |
| e | NVIDIA GPU evidence passes NRAS and carries our nonce | `gpu_evidence_invalid` |
| f | `GET /v1/signature/{chat_id}`: `text == "{model}:{sha256(req)}:{sha256(resp)}"`, EIP-191 signer equals the attested `signing_address`, `signature_kind == "provider_tee"` | `signature_mismatch` |
| g | Output parses against the schema; every finding's `candidate_id` exists and its `file:line` is in the diff | `ungrounded` (whole run) or finding dropped and counted |

Checks b–e use `dcap-qvl` for the quote and NVIDIA NRAS for GPU evidence, with NEAR's
reference checks ported so each one raises (ADR-0006). We do not parse quotes ourselves.
The attestation report is fetched **after** the completion, with `signing_address` set to
the signer, as NEAR's reference does. It needs no API key.

**Nonce** (ADR-0003): `nonce = SHA-256(canonical(idempotency_key) ‖ salt)`, where `salt` is
16 fresh random bytes per run, stored in the receipt.

### Step 6: Receipt (`hushmark/receipt.py`)
Defined in `RECEIPT.md`. Canonical JSON (RFC 8785), `receipt_id = SHA-256(bytes)`.
Holds hashes of the request, response, attestation and findings. Never the diff.
The full attestation report is stored next to it, addressed by its hash.

### Step 7: Publish (`hushmark/publish.py`)
| Repository | Action | Permission |
|---|---|---|
| Public | `POST /repos/{owner}/{repo}/security-advisories`, ecosystem `other`, left as a draft, body ends with `receipt: <id>` | Repository security advisories: write |
| Private | One pull request review with inline comments at the validated lines, ending `receipt: <id>` | Pull requests: write |
| Refusal or zero findings | Log only | none |

- Before publishing, search for the `receipt: <id>` marker so a retry never posts twice.
- Public repositories get the same public output whatever the result (currently: none),
  so the outcome does not leak.
- **Unverified:** whether repository security advisories work on private repositories.
  Test on day 2.

### Step 8: Anchor (`hushmark/anchor.py`, `contract/`), best effort
- Contract method `anchor(key_hash, receipt_hash)` panics if `key_hash` already exists.
- Called with a **function-call access key** limited to `anchor`, zero deposit. A stolen
  server key can only add anchors; it cannot move funds.
- `key_hash = SHA-256(canonical(idempotency_key))`. No repository names on chain.
- A failed anchor never blocks publishing. It is retried and recorded (ADR-0004).

## 3. GitHub App permissions

| Permission | Level | Why |
|---|---|---|
| Metadata | read | required by GitHub |
| Contents | read | compare endpoint for the pinned diff |
| Pull requests | write | read PR, post review (private repositories) |
| Issues | read | receive `issue_comment` events |
| Repository security advisories | write | draft advisory (public repositories) |

Webhook events: `issue_comment` only.

## 4. Run state machine

Each run is a row in SQLite that moves forward only:

```
received → authorized → fetched → scanned → inferred → verified → receipted → published
     └──────────── any step can go to → refused(reason) ─────────────┘
anchored is tracked separately: pending → done | failed(retries)
```

On restart, a run resumes from its last state. Publishing is idempotent through the marker.

## 5. Proving "no shell"

1. ruff banned-API rule: the `hushmark` package cannot import `subprocess`, `os.system`,
   `os.exec*`, `os.spawn*`, `pty`, `multiprocessing`.
2. Tests install `sys.addaudithook` and fail on `subprocess.Popen`, `os.system`, `os.exec`,
   `os.posix_spawn` and `os.spawn` events while the whole pipeline runs.
3. A test asserts the recorded request body has no `tools` field.

This proves the review code has no path that runs the diff. It does not prove the host
cannot be compromised. See `THREAT_MODEL.md`.

## 6. Offline and live verification

- **Recorded once:** with a real key, against a demo repository we control. Saved per
  fixture: raw request bytes, raw response bytes, signature JSON, attestation report,
  Intel collateral, NVIDIA result.
- `make verify` (offline): signature (f), report data and nonce (c), quote against saved
  collateral at a pinned verification time (b), grounding (g), and all refusal fixtures.
- `make verify-live` (network, no key): re-runs NEAR's full verifier against the recorded
  report, including NVIDIA NRAS.
- **Confirmed 2026-11-01:** `dcap_qvl.verify(quote, collateral, now)` verifies a saved
  NEAR quote offline from saved collateral. Check e's NRAS call is online; its signed JWT
  is saved and its signature checked offline against NVIDIA's pinned keys.

## 7. Repository layout (planned)

```
hushmark/
  gate.py  fetch.py  scan.py  infer.py  receipt.py  publish.py  anchor.py  app.py
  verify/  attestation.py  signature.py  grounding.py
prompts/v1.txt
contract/            near-sdk Rust contract
fixtures/01-injection/ ... 09-oversize/
tests/
docs/  ARCHITECTURE.md  PLAN.md  FIXTURES.md  OPEN_QUESTIONS.md  adr/
README.md  AGENTS.md  THREAT_MODEL.md  RECEIPT.md  ROADMAP.md  SECURITY.md  CHANGELOG.md
```

## References

- NEAR AI Cloud response signatures: https://docs.near.ai/cloud/verification/cloud-api/response-signatures.md
- Quote, nonce and signer bindings: https://docs.near.ai/cloud/verification/reference/quote-nonce-signer.md
- NEAR AI Cloud verifier: https://github.com/nearai/nearai-cloud-verifier
- GitHub repository security advisories API: https://docs.github.com/en/rest/security-advisories/repository-advisories
