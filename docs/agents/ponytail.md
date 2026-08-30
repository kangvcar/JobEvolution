# Ponytail

Always on for any code change this turn. Lazy means efficient, not careless. The best code is the code never written.

Off only if the user says `stop ponytail` or `normal mode`. Default intensity: **full**. Switch: `lite` / `full` / `ultra`.

Commit messages still follow `docs/agents/git.md` (detailed Chinese, then push). Ponytail shortens the code, not the commit.

## Ladder

Stop at the first rung that holds. Read the task and the code it touches first. Trace the real flow. Then climb.

1. Does this need to exist at all? Speculative need: skip it, say so in one line.
2. Already in this codebase? Reuse it.
3. Stdlib does it? Use it.
4. Native platform feature covers it? Use it.
5. Already-installed dependency solves it? Use it. Do not add a new one for what a few lines can do.
6. Can it be one line? One line.
7. Only then: the minimum code that works.

Two rungs work: take the higher one. The first lazy solution that works is the right one, once you know what the change has to touch.

Bug fix is root cause, not symptom. Grep every caller of the function you are about to touch. One guard in the shared function beats a guard in every caller.

## Rules

- No unrequested abstractions: no interface with one implementation, no factory for one product, no config for a value that never changes.
- No boilerplate, no scaffolding for later.
- Deletion over addition. Boring over clever.
- Fewest files possible. Shortest working diff, after you understand the problem.
- Complex request: ship the lazy version and question the rest in the same response.
- Two stdlib options, same size: take the one that is correct on edge cases.
- Deliberate shortcuts with a known ceiling get a `ponytail:` comment naming the ceiling and the upgrade path.

Never simplify away: input validation at trust boundaries, error handling that prevents data loss, security, accessibility basics, anything the user explicitly asked for.

Non-trivial logic leaves one runnable check: a small `test_*.py` or an `assert` self-check. Trivial one-liners need no extra test.

## Intensity

| Level | What changes |
| --- | --- |
| lite | Build what was asked. Name the lazier alternative in one line. |
| full | Ladder enforced. Shortest diff. Default. |
| ultra | Deletion before addition. Ship the one-liner and challenge the rest of the requirement. |

## Output

Code first. Then at most three short lines: what was skipped, when to add it. Pattern: `[code] → skipped: [X], add when [Y].`

User-asked explanation (a report, a walkthrough, commit text) is not debt. Give it in full.
