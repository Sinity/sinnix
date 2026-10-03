---
name: handoff
description: Leave or resume a handoff when stopping mid-work, before compaction, passing work to another agent, or re-entering after one — job IDs, worktrees, Git and PR state, next action.
---

# Handoff

A handoff lets the next agent, or you after compaction, continue without
guessing. It points at records their owners keep (pueue, Git, the forge,
Beads); it never replaces them. Put it where the next reader looks first: the
Bead's notes for task work, otherwise the final message.

## Leaving a handoff

Keep one compact current-state note: the outcome, active owner and worktree,
uncommitted WIP, active job or PR pointers, useful verification results,
blockers, and the next action. Include only facts needed to continue. Preserve
uncommitted work; a handoff does not require a cleanliness commit. Link detailed
history rather than copying it or requerying completed records for narration.

## Resuming from one

Check active and action-dependent facts against their owner: the checkout
before editing, a job before retrying, or required PR state before merging.
Immutable completion pointers and unchanged historical evidence need no routine
requery. If a live record differs, update the current note and continue from it.
