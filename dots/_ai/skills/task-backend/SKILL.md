---
name: task-backend
description: Read or mutate durable Beads task state: find ready work, claim, note, relate, create, complete, and release registered project tasks.
---

# Task backend

Task state lives OUTSIDE every checkout: canonical Beads/Dolt databases under
`/realm/state/tasks/<project>`, reached via the repo's `.beads` redirect
(`bd where` confirms). `bd` is the only write path. **`bd` routes by cwd** — run it
from the owning repo or IDs resolve against the wrong backend (filing
included: a create from the wrong cwd lands in the wrong project). Pass
`--actor` or set `BEADS_ACTOR`; the default records the operator as author.
Feature branches never touch task state; claims, notes, and closures generate
no git commits. Historical beads-in-git snapshots are immutable evidence, never
live state.

## Reading work

- `bd ready` / `bd list --status ...` / `bd show <id>` / `bd graph --open
<epic>` — the graph is the authority; epic child-counts are not closure
  evidence (membership is dependency-based).
- "Ready" means dependency-ready, not necessarily executable now: live-proof
  and operator-window items are ready-for-a-window, not ready-for-a-worker.
  Check the bead's design for window/consent requirements before claiming.

## Claiming and working

- Claim before working. `agentctl batch start` claims every member of a
  batch with `bd update --claim` and `batch land` closes the satisfied ones;
  workers never touch Beads. Claim by hand only for work you do yourself,
  and release what you will not finish.
- Record as you go with `bd` notes. Notes carry dated facts and disproved
  hypotheses — the next session must inherit them, not re-derive them.
- Relate discovered structure with `bd dep` — convert prose dependencies into
  real edges the moment you notice them.

## Completing

- Complete only with verification evidence: the exact commands run, the PR
  and merge SHA where applicable. Code merge never embeds tracker
  transactions.
- **Close discipline**: a bead closes when its acceptance criteria are met,
  not when a harness exists or a mechanism is "structurally tested". Address
  each AC as satisfied / deferred-to-named-successor / misframed. Partial
  scope splits to a successor bead; it does not stretch the closure.
- Batch tracker housekeeping (multiple closes/notes from one wave) rather
  than emitting one operation at a time. Multi-id closes map `--reason`
  flags positionally; a close refused by an open blocker means close the
  blocker first (or `--force` deliberately, stating why).
- `dispatch_group=<leader-id>` metadata puts beads that share files,
  evidence, or a verification boundary into one worker: `batch start
<leader>` executes the leader and its open members together, and each
  bead keeps its own verifiable close. A closed leader is skipped. Never
  merge beads to co-execute them; remove the metadata when a leader closes
  (`bd update <id> --unset-metadata dispatch_group`).

## Filing new work

Use `bd create` from the owning project's checkout — filing from the wrong
cwd lands the bead in the wrong project. Follow [[bead-authoring]] for content: a
follow-up filed in ten seconds with a ritual title is negative-value; a
two-minute mission-first bead with real edges is how the queue stays
workable. Discovered follow-ups get filed at discovery time, linked to the
originating bead, never held in session memory.

## Drift

When bead claims disagree with code or receipts,
re-verify and fix the document that states it (see [[investigate]] §verifying claims) —
never propagate a stale measured claim into new work.

## Memory

Durable project memory that is task-shaped (decisions, lessons, blockers)
lives in beads via notes on the owning record — not in scratch files, not
in per-checkout markdown. Local plans are the current turn's checklist
only; markdown TODOs are never the shared source of truth.

## Typed close reasons

Prefer machine-parsable close metadata over prose-only reasons: on close, set
`--set-metadata closed_kind=<fixed-by-pr|superseded-by|refuted|delivered|
misfiled|inconclusive>` plus `closed_ref=<PR#/bead-id/receipt>` alongside the
prose `--reason`. Corpus mining and evidence joins then query exactly instead
of keyword-clustering prose reasons. (`bd close` itself lacks
`--set-metadata`: set metadata via `bd update` first, then close.)
