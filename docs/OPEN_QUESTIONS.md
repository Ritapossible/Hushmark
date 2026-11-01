# Open questions

Unknowns that change the build. Each has an owner day from `PLAN.md`. When answered, write
the answer and the date here and update `AGENTS.md` if it changes a decision.

| # | Question | Why it matters | Settle by | Answer |
|---|---|---|---|---|
| Q1 | Does the NEAR AI Cloud account need a card or minimum top-up? Will organizers give credit? | Without a key there is no evidence, and the project stops | Day 1 | |
| Q2 | Which NEAR AI Cloud models return `signature_kind: provider_tee`? | `gateway` signatures only bind the gateway, not the model TEE | Day 1 | **Partly (2026-11-01).** Model TEE attestations come back for `Qwen/Qwen3.8-27B`, `Qwen/Qwen3.6-35B-A3B-FP8`, `z-ai/glm-5.3-flash`. Proxied models (OpenAI, Anthropic, etc.) and `deepseek/deepseek-v4.1-flash` return 503 "TEE attestation". `provider_tee` on a real completion still needs a key. |
| Q3 | Can `nearai-cloud-verifier` (or `dcap-qvl`) verify a saved quote offline with saved collateral and a pinned time? | Decides what `make verify` covers offline | Day 1 | **Yes (2026-11-01).** `dcap_qvl.verify(raw_quote, collateral, now_secs)` with `QuoteCollateralV3.from_json(saved)` verified a live NEAR quote: `UpToDate`. NEAR's verifier itself is a demo script that prints results and never fails, so we do not call it (ADR-0006). |
| Q4 | Does `POST /repos/{o}/{r}/security-advisories` work on private repositories? | Decides whether private repos get an advisory or a review comment | Day 2 | |
| Q5 | Does a GitHub App installation token with "Repository security advisories: write" create a draft advisory without a human admin? | The API docs say the *user* must be a security manager or admin | Day 2 | |
| Q6 | Does the GPU evidence (NVIDIA NRAS) carry our nonce, and can its result be checked offline? | Decides whether check e is offline or live-only | Day 7 | **Nonce: yes (2026-11-01).** NRAS itself is online-only. NEAR's reference decodes the NRAS JWT **without verifying its signature**; we must verify it against NVIDIA's published keys, then the saved JWT can be checked offline. |
| Q7 | What does a recorded quote's TCB status look like a week later? | Judging runs 16–18 November, after recording on day 5 | Day 12 | |
| Q8 | Does the attestation report need an API key? | Affects what judges can re-run | Day 1 | **No (2026-11-01).** `GET /v1/attestation/report?model=...&nonce=...&signing_algo=ecdsa` returns a full report unauthenticated. |
