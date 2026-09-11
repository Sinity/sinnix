---
name: analyze
description: Interactive codebase analysis with user steering (survey → narrate → synthesize)
---

# Interactive Code Analysis

Analyze a target in three useful phases: survey its structure, narrate the
selected areas, then synthesize evidence-backed findings. Pause for steering
when the next phase or scope is genuinely user-owned; a user may say `focus on
X`, `skip X`, `go deeper on X`, `check X vs Y`, `write findings`, or `fix issue
N`.

At each phase, state the files and commands examined, expected versus observed
behavior, and concrete file:line evidence. Keep findings separate from
speculation and note suspicious-looking code that is actually sound. Use the
existing global agent definitions and model choices for any delegated bounded
narration; do not create another launcher or receipt contract.

## Survey

List the target's items, size, purpose, and concern (high/medium/low). Recommend
the smallest useful narration scope. Large or dependency-heavy code is a
reason to inspect it first, not a mandate to scan unrelated directories.

## Narrate

Read the selected files systematically and cross-check related call paths.
Classify concrete findings as critical, structural, style, algorithmic, or
debt. For each, name the input, wrong or surprising outcome, and evidence that
would disprove it. Exact tests or live probes are preferred to broad suites.

## Synthesize

Cross-reference the findings, remove duplicates, and prioritize by impact,
scope, and fixability. Return high/medium/low findings, recurring patterns,
cross-checks performed, open questions, and the next action. Persist findings
only when requested or when the repository's normal evidence record requires
it; use the existing tracker/report rather than a new ledger.

If the analysis spans turns or is interrupted, a project-local scratch note may
hold the target, completed phase, selections, evidence paths, findings, and
open questions. It is a resume aid, not a mandatory per-phase ritual. Never
start implementation, destructive action, or publication without the user's
direction when it would materially change scope or risk.

**Target**: $ARGUMENTS
