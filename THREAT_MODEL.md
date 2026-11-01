# Threat model

Scope: v0.1, the hackathon build.

## Assets

| Asset | Why it matters |
|---|---|
| Private diff content | Leaking it is the failure customers care about most |
| Findings | Publishing a real finding publicly warns attackers before maintainers |
| Maintainers' trust in a finding | A forged or hallucinated finding wastes time and erodes trust |
| NEAR AI Cloud credit | Spam triggers cost money |
| GitHub App private key, webhook secret, NEAR function-call key | Control of the app |

## Attackers

| Attacker | Wants | Defence |
|---|---|---|
| **Fork author** writing a malicious PR | Make the reviewer run code, follow hidden instructions, or report the PR clean | Nothing is ever executed. No tools sent to the model. Scanner finds candidates deterministically, so the model cannot hide them by saying nothing. |
| **Non-maintainer commenter** | Trigger runs, spend credit, fish for findings | `admin`/`maintain` check on every trigger; refusals post nothing |
| **Replay attacker** | Reuse an old attestation or signature | Fresh nonce per run, bound into the quote; signature covers exact request and response bytes |
| **Tampering in transit or storage** | Change a finding after signing | Signature check on exact bytes; receipt hash anchored on NEAR |
| **The model itself** (hallucination or injected) | Invent findings or point at lines that do not exist | Grounding check: findings must match a scanner candidate and a real diff line |
| **Webhook forger** | Fake a `/advisory` trigger | HMAC check; delivery ID reuse rejected |
| **Compromised Hushmark server** | Read diffs, publish fake findings | **Not defended in v0.1.** See below. |

## What is proved

1. The review code has no path that runs the diff (banned-API lint, runtime audit hook,
   no `tools` in requests).
2. A published finding came from a NEAR AI Cloud model running in an attested TEE, on the
   exact request we sent, for that commit (checks a–f in `docs/ARCHITECTURE.md`).
3. Every published finding points at a real line of the reviewed diff (check g).
4. A given commit is reviewed once; the NEAR anchor shows the receipt existed at that time.

## What is not proved

- **The Hushmark server is not in a TEE.** It receives the diff before sending it to NEAR
  AI Cloud. Someone who compromises the server can read diffs and could skip verification.
  The claim covers what the review code does, not the host it runs on. Moving the service
  into a confidential VM is ROADMAP v0.2.
- **TEE trust is hardware trust.** The guarantee holds only if Intel TDX and NVIDIA
  confidential computing are sound and NEAR AI Cloud's measurements match what it
  publishes.
- **Detection is not complete.** Hidden instructions in forms the scanner does not know
  are missed. The design deliberately trades recall for no false positives.
- **`request_sha256` is a hash of content that includes the diff.** Someone who already has
  a candidate diff can confirm it was the one reviewed. Diffs are high entropy, so this is
  accepted.
- **Offline verification checks evidence as of the recorded time.** It does not prove the
  TEE's TCB status is still acceptable today. `make verify-live` re-checks online.

## Out of scope for v0.1

Denial of service against the app, GitHub itself being compromised, malicious repository
admins (they already control the repository).
