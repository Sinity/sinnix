---
name: bead-loop
description: Work a Beads queue continuously — pick the highest-value ready bead, execute it to a merged PR, close with verification, repeat. Use when the user says "work the bead queue", "keep going through bd ready", or invokes it under /loop for cross-session continuation. Requires a repo with a .beads/ workspace.
metadata:
  short-description: Greedy execution loop over bd ready
---

# Bead Loop

Beads is the devloop: this skill is the loop driver. One bead at a time,
carried to a verified, merged done-state, then the next — no pauses to ask
"continue?" between beads.

**Arguments**: `$ARGUMENTS` — optional filter/focus: a label (`wave:0`,
`area:durability`), an epic id ("work under sinex-r6d"), or a priority
ceiling ("P1 only"). Empty = whole ready queue, priority then wave order.

## Iteration protocol

1. **Orient** (first iteration only): `bd prime`; read the repo's
   `.agent/CONVENTIONS.md` if not already loaded.
2. **Pick**: `bd ready --json` (apply `$ARGUMENTS` filter). Choose by
   priority, then wave, then unblock-count (prefer beads that free others).
   Skip beads labeled for operator decision unless asked to draft options.
3. **Claim + reconcile**: `bd update <id> --claim`, then re-verify the
   bead's cited file:line facts against current master; update the
   description if the world moved. If the bead is already done, close it
   with evidence and pick again.
4. **Execute** to the bead's acceptance criteria. Greedy-batch cadence:
   one complete bead per branch/PR; widen to a coherent AC phase before
   splitting; a green substep is a checkpoint, not a publishing trigger.
5. **Verify** per the bead's named VERIFY commands, narrow-first; broad
   gate once per publishable phase (repo rules: xtask in sinex, devtools
   test in polylogue).
6. **Ship**: branch → PR (Summary/Problem/Solution/Verification) → merge
   per the standing merge authorization. Run `.agent/scripts/bd-graph-lint`
   before shipping any bead-state delta.
7. **Close**: `bd close <id> --reason` with the exact verification
   commands; create linked beads for discovered follow-ups
   (`--deps discovered-from:<id>`); record satisfied/deferred AC matrix if
   the PR did not close everything.
8. **Loop**: go to 2. Do not stop between iterations to ask permission.

## Stop conditions

- Operator interrupts or the filter is exhausted (report the final state:
  beads closed, PRs merged, follow-ups created).
- Only operator-decision beads remain in scope → present the decision
  frames instead of guessing.
- A red substantive gate you cannot fix locally → park the bead with a
  note (unclaim), report, continue with the next bead.
- Context nearly exhausted → finish the current step, push WIP to the
  branch, write bead notes sufficient for cold resume, then summarize.

## Cross-session continuation

For a loop that survives context windows, invoke via the harness loop:
`/loop /bead-loop <filter>` — each firing re-enters this protocol; Beads
claims/notes make every iteration cold-resumable, so nothing depends on
chat history. For scheduled runs (e.g. nightly), use a cron loop with the
same prompt. Concurrency rule: one bead-loop per checkout (claims are the
mutex; a second loop must use its own worktree and disjoint bead scope).
