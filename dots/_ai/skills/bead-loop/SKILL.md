---
name: bead-loop
description: Work a canonical AgentCTL task queue continuously: pick the highest-value ready task, execute it to a merged PR, complete it with verification, repeat. Use when the user asks to work a Beads queue or continue a task loop. Requires a registered AgentCTL project.
metadata:
  short-description: Greedy execution loop over AgentCTL tasks
---

# Bead Loop

AgentCTL tasks are the devloop: this skill is the loop driver. One task at a time,
carried to a verified, merged done-state, then the next — no pauses to ask
"continue?" between beads.

**Arguments**: `$ARGUMENTS` — optional filter/focus: a label (`wave:0`,
`area:durability`), an epic id ("work under sinex-r6d"), or a priority
ceiling ("P1 only"). Empty = whole ready queue, priority then wave order.

## Iteration protocol

1. **Orient** (first iteration only): read the registered project's AgentCTL task state and `.agent/CONVENTIONS.md` if present.
2. **Pick**: list open tasks through AgentCTL and apply `$ARGUMENTS`. Choose by priority, then wave, then unblock-count. Skip tasks labeled for an operator decision unless asked to draft options.
3. **Claim + reconcile**: the coordinator claims through `agentctl task` with a stable request ID, then re-verifies the task's cited file:line facts against current master. If the task is already done, complete it
   with evidence and pick again.
4. **Execute** to the task's acceptance criteria. Greedy-batch cadence:
   one complete task per branch/PR; widen to a coherent AC phase before
   splitting; a green substep is a checkpoint, not a publishing trigger.
5. **Verify** per the task's named verification commands, narrow-first; broad
   gate once per publishable phase (repo rules: xtask in sinex, devtools
   test in polylogue).
6. **Ship**: branch → PR (Summary/Problem/Solution/Verification) → merge
   per the standing merge authorization.
7. **Complete**: the coordinator completes the AgentCTL task with the exact
   verification commands and merge evidence; create discovered follow-ups with
   `agentctl task create <project> 'Title' --description 'Description' --type task --priority 2 --request-id <uuid>` and add `--parent` or repeated `--dependency relation:task-id` when needed; record satisfied/deferred AC matrix if
   the PR did not close everything.
8. **Loop**: go to 2. Do not stop between iterations to ask permission.

## Stop conditions

- Operator interrupts or the filter is exhausted (report completed tasks, PRs merged, and follow-ups created).
- Only operator-decision tasks remain in scope → present the decision
  frames instead of guessing.
- A red substantive gate you cannot fix locally → park the task with a coordinator note, report, and continue with the next task.
- Context nearly exhausted → finish the current step, push WIP to the
  branch, write bead notes sufficient for cold resume, then summarize.

## Cross-session continuation

For a loop that survives context windows, invoke via the harness loop:
`/loop /bead-loop <filter>` — each firing re-enters this protocol; AgentCTL
task state makes every iteration cold-resumable, so nothing depends on chat
history. For scheduled runs (e.g. nightly), use a cron loop with the same
prompt. Concurrency rule: one task loop per checkout; a second loop needs its
own AgentCTL workspace and disjoint task scope.
