# Open questions

Unknowns that change the build. Each has an owner day from `PLAN.md`. When answered, write
the answer and the date here and update `AGENTS.md` if it changes a decision.

| # | Question | Why it matters | Settle by | Answer |
|---|---|---|---|---|
| Q1 | Does the NEAR AI Cloud account need a card or minimum top-up? Will organizers give credit? | Without a key there is no evidence, and the project stops | Day 1 | |
| Q2 | Which NEAR AI Cloud models return `signature_kind: provider_tee`? | `gateway` signatures only bind the gateway, not the model TEE | Day 1 | |
| Q3 | Can `nearai-cloud-verifier` (or `dcap-qvl`) verify a saved quote offline with saved collateral and a pinned time? | Decides what `make verify` covers offline | Day 1 | |
| Q4 | Does `POST /repos/{o}/{r}/security-advisories` work on private repositories? | Decides whether private repos get an advisory or a review comment | Day 2 | |
| Q5 | Does a GitHub App installation token with "Repository security advisories: write" create a draft advisory without a human admin? | The API docs say the *user* must be a security manager or admin | Day 2 | |
| Q6 | Does the GPU evidence (NVIDIA NRAS) carry our nonce, and can its result be checked offline? | Decides whether check e is offline or live-only | Day 7 | |
| Q7 | What does a recorded quote's TCB status look like a week later? | Judging runs 16–18 November, after recording on day 5 | Day 12 | |
