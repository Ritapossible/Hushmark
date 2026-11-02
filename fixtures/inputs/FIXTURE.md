# Fixture pull requests

Hand-written inputs for recordings R1–R3 (docs/FIXTURES.md). They are not real pull requests: `repo_id` is 0 and the SHAs in `meta.json` are placeholders. Injection payloads are inert and point at an unreachable `.invalid` domain.

- `r1`: hidden HTML comment in `docs/setup.md` and in the PR body (two findings expected)
- `r2`: harmless `<!-- TODO -->` (zero findings expected)
- `r3`: new instructions added to `AGENTS.md` (one finding expected)
- `r4`: ordinary style rules added to `AGENTS.md` (zero findings expected): the control for `r3`
