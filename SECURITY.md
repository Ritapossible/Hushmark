# Security policy

Hushmark is a security tool, so reports about it are welcome.

## Reporting a vulnerability

Please use GitHub's private vulnerability reporting on this repository
(**Security → Report a vulnerability**). Do not open a public issue.

Include what you found, how to reproduce it, and what an attacker could do with it.

## Especially interesting

- Any way to make Hushmark execute code from a pull request
- Publishing a finding without a valid attestation and signature
- Diff content appearing in a receipt, log, or on chain
- Triggering a review without `admin` or `maintain` permission

## Scope

v0.1 is a hackathon build. Known limits are listed in `THREAT_MODEL.md` under
"What is not proved"; reports of those are still welcome but are not new.
