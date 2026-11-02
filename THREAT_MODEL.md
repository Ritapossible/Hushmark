# Threat model

Scope: v0.1, the hackathon build (ADR-0007).

## Assets

| Asset | Why it matters |
|---|---|
| Private repository code | Leaking it is the failure customers care about most |
| The team's AI agents | A merged hidden instruction steers every future agent session |
| Trust in a finding | A forged or hallucinated finding wastes time and erodes trust |
| NEAR AI Cloud credit | Fork pull requests can now trigger model calls |
| GitHub App private key, webhook secret, NEAR function-call key | Control of the app |

## Attackers

| Attacker | Wants | Defence |
|---|---|---|
| **Fork author** writing a malicious PR | Get hidden instructions merged; make the reviewer run code or report the PR clean | Nothing is executed. No tools sent to the model. Detectors find hidden regions deterministically, so the model cannot hide one by saying nothing. A refused or unverifiable run still shows the scanner's hits as *unconfirmed*. |
| **Same, aiming at cost** | Burn the owner's credit | No model call without candidates; cap of 20 candidates and 200 excerpt lines; per-installation daily budget |
| **Same, aiming at config** | Change `.hushmark.yml` in the PR to `warn` | Config is read from the base commit only |
| **Non-maintainer commenter** | Force re-runs | `/hushmark` requires `admin` or `maintain` |
| **Another GitHub App** | Post a passing check named `Hushmark` | Branch protection requires the check from the Hushmark app as source (README setup step) |
| **Replay attacker** | Reuse an old attestation or signature | Fresh nonce per run, bound into the quote; signature covers exact request and response bytes |
| **Tampering in transit or storage** | Change a finding after signing | Signature check on exact bytes; receipt hash anchored on NEAR |
| **The model itself** (hallucinated or injected) | Invent findings or point at other lines | Model returns only `candidate_id`; file and line come from our own scan |
| **Webhook forger** | Fake events | HMAC check; delivery ID reuse rejected |
| **Compromised Hushmark server** | Read code, show fake results | **Not defended in v0.1.** See below. |

## What is proved

1. The review code has no path that runs the diff (banned-API lint, runtime audit hook, no
   `tools` in requests). One known process start happens at import time, before any input
   exists: a dependency (pycryptodome, via `eth_account`) runs `file -b <python>` to learn
   the platform's word size. Its arguments are fixed, and a test pins it as the only one.
2. A shown finding came from a NEAR AI Cloud model in an attested TEE, on the exact request
   we sent, for that input (checks a–f in `docs/ARCHITECTURE.md`).
3. Every shown finding refers to a hidden region Hushmark found itself (check g).
4. Only excerpts around hidden regions leave Hushmark, and only to an attested TEE.
5. One input is reviewed once; the NEAR anchor shows the receipt existed at that time.

## What is not proved

- **The Hushmark server is not in a TEE.** It receives the full diff. Someone who compromises
  it can read code and could skip verification. The claim covers the review code, not its
  host. Moving the service into a confidential VM is ROADMAP v0.2.
- **TEE trust is hardware trust.** It holds only if Intel TDX and NVIDIA confidential
  computing are sound and NEAR AI Cloud's measurements match what it publishes.
- **Detection is not complete.** Hidden instructions in forms the detectors do not know are
  missed, and plain visible instructions outside rules files are not flagged. The design
  trades recall for few false positives.
- **The model sees excerpts, not the whole change.** It judges whether a hidden region is
  aimed at an agent, not what the whole pull request does.
- **Results on public repositories are public.** Accepted: the injection is the attacker's
  own text, already public in their pull request.
- **`request_sha256` covers the excerpts.** Someone who already has a candidate excerpt can
  confirm it was reviewed. Accepted.
- **Offline verification checks evidence as of the recorded time.** `make verify-live`
  re-checks online.

## Out of scope for v0.1

Denial of service against the app, GitHub itself being compromised, malicious repository
admins (they already control the repository and its config).
