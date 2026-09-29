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

Run this checklist loudly (global rules, Reporting) and write the result as
the handoff:

1. Every job you started, by ID, with its state (`agentctl job result <id>`
   for a terminal one) and the event you were waiting on.
2. Every worktree you own, by path, with its branch, `HEAD`, and
   `git -C <path> status --short` (clean, or the uncommitted paths).
   Uncommitted work is committed first unless it is unsafe to.
3. Every open PR, with its head SHA, required-check state, hosted-review
   state on that head, and unresolved-thread count, queried from the forge.
4. Every Bead you claimed or changed, with its claim and the note you left.
5. The verification already run: command, job ID, and result line, and the
   SHA it ran on.
6. Watches, timers, or background shells of yours that are still running, or
   none.
7. The single next action, as a command or a named decision.

## Resuming from one

Before acting on a handoff or a compaction summary, check each record against
its owner: jobs through `agentctl job result`, worktrees through
`git -C <path> status` and `git -C <path> log -1`, PRs through `gh pr view`,
Beads through `bd show`. Where a record and its owner disagree, the owner is
right; note the difference and work from the live state.
