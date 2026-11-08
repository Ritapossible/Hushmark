# What Hushmark finds in public agent rules files

**Date:** 8 November 2026. **Model calls:** none; this is Hushmark's deterministic scanner only.

AI coding agents load rules files (`.cursorrules`, Cursor `.mdc` rules, Copilot agents,
instructions and skills) as instructions, and developers copy them from public collections.
We ran Hushmark's scanner over the two largest public collections to see how often those files
hold text a human reviewer would not see, and what it is.

## What was scanned

| Collection | Commit | Files scanned |
|---|---|---|
| [PatrickJS/awesome-cursorrules](https://github.com/PatrickJS/awesome-cursorrules), `rules/` | `b044f956` (2026-05-30) | 257 Cursor rules files |
| [github/awesome-copilot](https://github.com/github/awesome-copilot): `AGENTS.md`, `agents/`, `instructions/`, `skills/`, `plugins/`, `hooks/`, `workflows/` | `797337f3` (2026-11-07) | 1,819 agent, instruction and skill files |

Every `.md`, `.mdc` and `.cursorrules` file was read as text and scanned the way Hushmark scans
a pull request description. Raw results (file, line range, detectors; no file text):
[`public-rules-scan.json`](public-rules-scan.json).

## Results

| | Cursor rules | Copilot collection | Total |
|---|---:|---:|---:|
| Files scanned | 257 | 1,819 | 2,076 |
| Files with at least one hidden region | 5 | 140 | **145 (7%)** |
| HTML comment regions | 27 | 586 | 613 |
| Hidden HTML regions | 0 | 96 | 96 |
| Zero-width character regions | 0 | 16 | 16 |
| **Hidden instructions trying to harm the user** | 0 | 0 | **0 found** |

We then read what the hidden regions are:

- **HTML comments (613).** 353 (58%) sit inside fenced code blocks: they are HTML or XAML
  examples, visible when the file is rendered. Of the 260 outside code, most are template
  placeholders (`<!-- name -->`), lint directives (`markdownlint-disable`) and section
  markers. We read every one that reads like an instruction (51, in 19 files): all are
  template guidance or the authors' own process steps for the agent, for example a
  threat-modelling skill that keeps "⛔ POST-DFD GATE: count element nodes…" checks in
  comments. None asks an agent to approve, hide, skip checks, run commands or send data.
- **Zero-width characters (16).** 14 are zero-width joiners inside emoji (the "technologist"
  emoji is a person and a laptop joined by one), 2 are a zero-width space used to escape a nested code fence.
- **Hidden HTML (96).** 53 are long, descriptive image alt text (good accessibility),
  22 are collapsible `<details>` sections, and the rest are in code examples or CSS advice.

## What this means

1. **Hiding instructions for agents in comments is normal practice.** Authors of public
   skills and templates put agent-facing steps in HTML comments, which a human reading the
   rendered file never sees. So "a hidden instruction exists" cannot be the test on its own:
   whether it is *aimed at changing what the agent does against the user* is. That is why
   Hushmark sends each hidden region to a model to judge intent, instead of failing every
   comment.
2. **These collections are clean today.** No region we reviewed is an attack. The risk is a
   pull request that adds one, to a collection or to your own rules files, which is the moment
   Hushmark checks.
3. **Two false-positive classes to remove** (now on the [roadmap](../../ROADMAP.md)):
   comments and hidden HTML inside fenced code blocks (visible when rendered; 58% of comment
   hits here), and zero-width joiners inside emoji. Both cost a model call today, and in
   block mode a pull request full of HTML examples can reach the 20-region cap and fail.

## Limits

This is two collections, not a random sample of all repositories, and it checks the files as
they are, not their history. The review of instruction-like comments used a keyword filter
and then a person reading each match; a comment phrased without those words was counted but
not read individually.

## Reproduce

```sh
git clone https://github.com/PatrickJS/awesome-cursorrules && git -C awesome-cursorrules checkout b044f956f021b6e8877f16781bcfc466a6a120e9
git clone https://github.com/github/awesome-copilot && git -C awesome-copilot checkout 797337f33f73e35d08d82f840e21c4b8c4932d88
mkdir -p corpus/copilot && cp -r awesome-cursorrules/rules corpus/cursorrules
cp -r awesome-copilot/{AGENTS.md,agents,instructions,skills,plugins,hooks,workflows} corpus/copilot/
uv run python scripts/scan_rules_corpus.py corpus/cursorrules corpus/copilot > results.json
```
