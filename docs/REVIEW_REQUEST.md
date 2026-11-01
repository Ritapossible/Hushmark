# Design review request

This repository has no code yet. Please review the design before the build starts.

## What to read

1. `README.md`, the claim
2. `docs/ARCHITECTURE.md`, the pipeline and checks a–g
3. `THREAT_MODEL.md`, what is and is not proved
4. `docs/FIXTURES.md` and `docs/PLAN.md`, the judged path and schedule

## What we want challenged

- **The claim.** Does anything in the architecture fail to support it, or overstate it?
- **Verification.** Is any check in step 5 missing, in the wrong order, or not fail-closed?
  Can a finding be published without passing all of a–g?
- **Fixtures.** Does any fixture pass for the wrong reason? (Fixture 08 is already a known
  case and is a unit test for that reason.)
- **Privacy.** Can the diff or a finding leak through a receipt, a log, the chain, the
  public repository view, or timing?
- **Scope.** Is anything in `PLAN.md` not needed for the claim? Is anything needed missing?
- **Schedule.** Which day is most likely to slip, and what should be cut first?
- **Open questions.** Do you know the answer to any item in `OPEN_QUESTIONS.md`? Please
  give a source.

## How to respond

For each point: the file and section, what is wrong, and what you would change. Mark each
as **blocking** (must change before building) or **optional**.
