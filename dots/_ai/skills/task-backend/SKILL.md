---
name: task-backend
description: Read or mutate durable Beads task state: find ready work, claim, note, relate, create, complete, release, reconcile, and snapshot registered project tasks.
---

# Task backend

Task state lives OUTSIDE every checkout: canonical Beads/Dolt databases under
`/realm/state/tasks/<project>`, reached via the repo's `.beads` redirect
(`bd where` confirms) or `agentctl task ...`. Feature branches never touch
task state; claims, notes, and closures generate no git commits. Historical
beads-in-git snapshots are immutable evidence, never live state.

## Reading work

- `bd ready` / `bd list --status ...` / `bd show <id>` / `bd graph --open
<epic>` — the graph is the authority; epic child-counts are not closure
  evidence (membership is dependency-based). All task reads go through `bd`
  directly; AgentCTL deliberately has no `task list`/`task get` (it owns only
  journalled mutations, reconcile, and the authority-bound snapshot).
- "Ready" means dependency-ready, not necessarily executable now: live-proof
  and operator-window items are ready-for-a-window, not ready-for-a-lane.
  Check the bead's design for window/consent requirements before claiming.

## Claiming and working

- Claim before working: `agentctl task claim <id> --workspace W` (binds the
  claim to the workspace) or `bd` claim in-repo. Stale leases with dead
  heartbeats are the recorded smell of abandoned claims — release what you
  will not finish (`agentctl task release`).
- Record as you go: `agentctl task note <id> --commit SHA --text ...` /
  `bd` notes. Notes carry dated facts and disproved hypotheses — the next
  session must inherit them, not re-derive them.
- Relate discovered structure: `agentctl task relate` / `bd dep` — convert
  prose dependencies into real edges the moment you notice them.

## Completing

- Complete only with verification evidence: the exact commands run, the PR
  and merge SHA where applicable (`agentctl task complete <id> --pr N
--merge-sha SHA`). Completion is idempotent after merge and retryable
  after a backend outage — code merge never embeds tracker transactions.
- **Close discipline**: a bead closes when its acceptance criteria are met,
  not when a harness exists or a mechanism is "structurally tested". Address
  each AC as satisfied / deferred-to-named-successor / misframed. Partial
  scope splits to a successor bead; it does not stretch the closure.
- Batch tracker housekeeping (multiple closes/notes from one wave) rather
  than emitting one operation at a time.

## Filing new work

Use `agentctl task create` for typed cross-project creation, with a stable
request ID so retries are idempotent. Use `bd create` in the owning project
when direct-owner access is the appropriate route. Follow [[bead-authoring]] for content: a
follow-up filed in ten seconds with a ritual title is negative-value; a
two-minute mission-first bead with real edges is how the queue stays
workable. Discovered follow-ups get filed at discovery time, linked to the
originating bead, never held in session memory.

## Reconciliation and drift

`agentctl task reconcile` retries failed mutations; `task snapshot` produces
the portable export. When bead claims disagree with code or receipts,
re-verify and fix the carrier (see [[investigate]] §verifying claims) —
never propagate a stale measured claim into new work.

## Memory

Durable project memory that is task-shaped (decisions, lessons, blockers)
lives in beads via notes on the owning record — not in scratch files, not
in per-checkout markdown. Local plans are the current turn's checklist
only; markdown TODOs are never the shared source of truth.
