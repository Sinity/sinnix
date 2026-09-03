---
name: agent-runtime
description: Operate or recover agentctl jobs and lanes — declared operations as pueue tasks, worktree lanes with an agent and a PR, logs, results, cancellation, cleanup and redispatch.
---

# Agent runtime

`agentctl` is an in-process CLI; nothing runs on its behalf. pueue owns the
queue, every process and its terminal result; worktrunk owns worktrees;
GitHub owns review, required checks and merge; Beads owns tasks; systemd owns
only calendar wake-ups. Do not add a parallel ledger for any of them.

Verbs: `project`, `job`, `lane`, `refill`, `view`, `events`, `schedule`.
`agentctl <verb> --help` is the surface. Reads print tables in local time;
`--json` (before the verb) prints the document. Exit status: 0 done, 1
refused or failed, 2 usage, 3 the waited job did not succeed.

## Jobs

`start`, `fire`, `list`, `get`, `logs`, `result`, `cancel`, `retry`, `wait`.

- `agentctl project operations <project>` lists the declared operations.
- `agentctl job start <project> <operation> [--workspace <path>] [--wait]
[-- extra args]` queues one pueue task in the operation's pool, labelled
  `<project>:<operation>`. The job id is the pueue task id. The descriptor
  owns environment, pool, result contract and timeout; extra arguments are
  appended to its `exec`.
- `job list [--project p] [--active]`, `job get <id>`, `job logs <id>`,
  `job result <id>` (the typed artifact for `json`/`pytest` results),
  `job wait <id>`, `job cancel <id>` (kills the task and its process group),
  `job retry <id>` (`pueue restart --in-place`).
- **Never poll.** Every task's start and finish reaches
  `/realm/state/agentctl/events.jsonl`; watch `agentctl events tail --follow`.
- Declared operations may run for up to eight hours; agents cap at four.
- Every long launch carries an evidence-based duration expectation and a
  deadline around twice it. At the deadline, inspect progress evidence and
  cancel, repair, or extend for a stated reason.
- Artifacts (launch input, log, result) live under `~/.local/state/sinnixd`
  and are found by the reference in the task's own command line.

### Session subagents run outside pueue

Subagents spawned inside a Claude session are not jobs and pueue never sees
them. Give them an explicit bound: one pytest at a time, `-n 2`, or route the
heavy step through `agentctl job start`.

## Lanes

A lane is a worktree with an agent in it and a PR that merges itself.

- `agentctl lane start <project> <bead> [--backend B --model M --effort E]`
  compiles the prompt from the bead (and its open dispatch group), creates
  `<workspace.root>/<repo>-feature-packet-<bead>` through `wt switch
--create` (the project's `wt.toml` hooks provision it), and queues the
  agent in group `agent` inside a `systemd-run --scope` with the descriptor's
  `agent_memory_max`. Every dispatch names backend, model and effort; the
  descriptor's `[packets.defaults]` fill what the flags leave out.
- `agentctl lane rebase <project> <bead>` queues an agent with the rebase
  prompt into the bead's existing worktree. Uncommitted work there belongs to
  the new agent.
- `agentctl lane publish <worktree>` pushes, opens the PR under the bead's
  type-prefixed subject (body from `.lane/body.md`), and arms
  `gh pr merge --auto --squash`. It refuses a dirty worktree.
- `agentctl lane sync <project>` closes the beads of merged lanes and removes
  their worktrees; the rest are listed with their state and PR.
- `agentctl refill <project> --limit N [--dry-run]` starts lanes for ready
  beads that have neither a worktree nor an open PR.

## The screen

`agentctl view <project>`: queue groups (running/queued/paused), what needs
attention (failed jobs, conflicting or red PRs, failed agents), active jobs
with start time and elapsed, every lane with bead, stage, since/elapsed,
agent job, PR and what follows next, and the ready beads.
`agentctl events tail [--follow] [--project p]` is the same over time.

## Worker toolbelt

Agents have `lane` on PATH:

- `lane task` prints the dispatch prompt (`.lane/prompt.md`).
- `lane verify` runs the project's quick verification as a job and waits.
- `lane publish` is `agentctl lane publish` on the current worktree.
- `lane done report.md` requires a clean tree, pushes the branch, and emits
  the report as the final message. `lane done --incomplete report.md` pushes
  committed WIP and marks the report partial.

## Failures

- Wedged job: `job get`, `job logs`, `job cancel` once, confirm the task is
  terminal in `pueue status` before restarting.
- Dead agent: the worktree keeps its work; commit it, record the result on
  the bead, then `lane rebase` for a fresh agent or `wt remove` to abandon.
- `pueue has no group X`: the descriptor names a pool pueued does not have;
  the groups are declared with pueued in the CLI feature.
- Environment mismatch: use the declared operation. Do not duplicate its
  devshell, secret, port, or service contract in an ad hoc wrapper.
