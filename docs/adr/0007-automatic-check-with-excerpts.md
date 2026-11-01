# ADR-0007: Automatic required check, excerpts only, one Check Run output

- Status: accepted
- Date: 2026-11-01
- Supersedes: the `/advisory` trigger, the draft-advisory and PR-review outputs, and the
  whole-diff 200-line cap in ADR-0005

## Context

The first design needed a maintainer to type `/advisory` on each pull request, refused any
diff over 200 lines, and published a draft security advisory on public repositories. A team
would not adopt that:

- Nobody types a command on every pull request, and the malicious one is the one nobody
  suspects. Security tools are adopted as automatic, required checks.
- Many real pull requests are over 200 lines.
- An injection is the attacker's own text, already public in their pull request. There is
  nothing to keep confidential, and advisories are for disclosing vulnerabilities.
- Agents also read the PR title and body (the 2025 GitHub MCP attack came through an issue),
  and agent rules files are instructions to agents by design (the 2025 Rules File Backdoor).

## Decision

1. Run automatically on every pull request event. `/hushmark` is only a maintainer re-run.
2. Detectors scan the whole diff, title and body, with no size cap. The model is called only
   when there are candidates; most pull requests cost nothing.
3. Send the model **excerpts only**: each candidate with up to 10 lines of context. The cap
   (20 candidates, 200 excerpt lines) applies to excerpts; over it, `too_many_candidates`.
4. Report through one GitHub Check Run per head SHA, with line annotations. `mode: warn`
   (default) or `mode: block` in `.hushmark.yml`, read from the base branch only.
5. Treat any added line in a known agent rules file as a candidate.
6. Permissions shrink to contents read, pull requests read, checks write.

## Consequences

- Teams can make it a required check, restricted to the Hushmark app as the source.
- Less code leaves GitHub than before: excerpts instead of the full diff.
- The model judges with less context. Accepted: it only decides whether a known hidden region
  is aimed at an agent.
- Check Runs on public repositories are public. Accepted, for the reason above.
- Open questions Q4 and Q5 (advisories on private repositories) no longer apply.
- Fork pull requests can now cause model calls. Bounded by: no call without candidates, the
  candidate cap, and a per-installation daily budget.
