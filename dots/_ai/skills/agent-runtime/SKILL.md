---
name: agent-runtime
description: Operate or recover agentctl jobs and batches — declared operations as pueue tasks, worker worktrees, the landing task, logs, results, cancellation, cleanup and resumption.
---

# Agent runtime

`agentctl` is an in-process CLI; nothing runs on its behalf. pueue owns the
queue, every process and its terminal result; worktrunk owns worktrees;
GitHub owns review, required checks and merge; Beads owns tasks and claims;
systemd owns only calendar wake-ups. Do not add a parallel ledger for any of
them. `docs/agentctl.md` in sinnix is the reference.

Verbs: `project`, `job`, `batch`, `view`, `events`, `schedule`,
`backpressure`. `agentctl <verb> --help` is the surface. Reads print tables
in local time; `--json` (before or after the verb) prints the document;
writes print JSON on stdout and one summary line on stderr. `--project` is
optional everywhere: a leading positional that names a project or checkout
selects it, else the checkout enclosing the working directory. A run is its
id or its 8-character suffix; `--full` prints whole ids. Exit status: 0
done, 1 refused or failed, 2 usage, 3 a driven tool failed, 4 the waited job
did not succeed.

## Jobs

`start`, `fire`, `list`, `get`, `logs`, `result`, `cancel`, `retry`, `wait`,
`clean`.

- `agentctl project operations <project>` lists the declared operations.
- `agentctl job start [project] <operation> [--workspace <path>] [--wait]
[-- extra args]` queues one pueue task in the operation's pool, labelled
  `<project>:<operation>`. The job id is the pueue task id. The descriptor
  owns environment, pool, result contract and timeout; extra arguments are
  appended to its `exec`.
- `job list [--project p] [--active]`, `job get <id>`, `job logs <id>`,
  `job result <id>` (the typed artifact for `json`/`pytest` results, else the
  outcome), `job wait <id>`, `job retry <id>` (`pueue restart --in-place`).
- `job cancel <id>`: a queued task is removed; a running task's unit is
  stopped and its whole cgroup with it. Exit 1 while the unit is still
  active.
- Outcomes of a run, shown by `job result` and carried on the finished
  event: `success`, `failed` (the command's exit), `timeout` (124),
  `cancelled` (130), `vanished` (126, the unit could not be observed after a
  failing wait), `slot_occupied` (75, a single-slot pool was held).
- `job clean <id>` deletes a terminal task's launch input, log, result,
  outcome and cancel marker, then removes the task from pueue;
  `--all-terminal` does it for every terminal task; `--daemon-era` deletes
  the state subtrees no verb reads. Never by age.
- **Never poll.** Every task's start and finish reaches
  `/realm/state/agentctl/events.jsonl`; watch `agentctl events tail --follow`.
- Declared operations may run for up to eight hours; agents cap at four.
- Every long launch carries an evidence-based duration expectation and a
  deadline around twice it. At the deadline, inspect progress evidence and
  cancel, repair, or extend for a stated reason.
- Artifacts (launch input, log, result) live under `~/.local/state/agentctl`
  or the task's own working directory, and are found by the launch input the
  task's command names.

### Session subagents run outside pueue

Subagents spawned inside a Claude session are not jobs and pueue never sees
them. Give them an explicit bound: one pytest at a time, `-n 2`, or route the
heavy step through `agentctl job start`.

## Batches

A batch is several workers on one base commit landed as one candidate. Its
manifest is `~/.local/state/agentctl/runs/<run>.json`.

- `agentctl batch start [project] <bead>… [--worker a,b]… [--workers
queued|external] [--backend B --model M --effort E]` validates the members,
  writes the manifest, claims the beads, creates one worktree per worker on
  branch `batch/<run>/<worker>` at `<workspace.root>/<repo>-<branch with /
replaced by ->` through `wt switch --create` (the project's `wt.toml` hooks
  provision it), writes the
  packet to `.lane/prompt.md`, queues each worker in group `agent` inside a
  unit capped at the descriptor's `agent_memory_max`, and queues the landing
  task behind them in `<project>-land`. `--workers external` skips the
  worker enqueue and stashes the landing task for another harness's
  workers. Repeating it on an existing run completes what is missing.
- `agentctl batch result <run> <worker> <result.json>` files an external
  worker's result after validating it against the worker schema and binding
  it to the worktree head; the last result enqueues the landing task.
- `agentctl batch land <run>` integrates, verifies, reviews, publishes,
  records acceptance, closes satisfied beads and removes worker worktrees.
  It is the landing task's body and is re-run by hand after a named failure.
- `agentctl batch resume <run> --worker <w>` queues a fresh agent into the
  worker's existing worktree with the original packet. Uncommitted work
  there belongs to the new agent.
- `agentctl batch status <run>`, `agentctl batch list [project]`.

## The screen

`agentctl view <project>`: queue groups (running/queued/paused), what needs
attention (failed jobs, failed workers, failed landings), active jobs with
start time and elapsed, every open run with each worker's stage, since and
job, the landing task and what follows next, and the ready beads.
`agentctl events tail [--follow] [--project p]` is the same over time.

## Worker toolbelt

Agents have `lane` on PATH:

- `lane task` prints the dispatch packet (`.lane/prompt.md`).
- `lane verify` runs the descriptor's focused verification through
  `agentctl job start <project> <focused> --workspace . --wait`.
- `lane done <result.json>` requires a clean tree, validates the document
  against `.lane/worker.schema.json` with `candidate_sha` equal to HEAD, and
  prints it as the final message. It never pushes; the landing task
  publishes.

## Failures

- Wedged job: `job get`, `job logs`, `job cancel` once, confirm the task is
  terminal in `pueue status` before restarting.
- Dead worker: the worktree keeps its work; commit it, then `batch resume
--worker` for a fresh agent or `wt remove` to abandon.
- Failed landing: `batch status` names the code, `job logs <landing task>`
  the cause; fix it, then `batch land <run>` again.
- `pueue has no group X`: the descriptor names a pool pueued does not have;
  the groups are declared with pueued in the CLI feature.
- Environment mismatch: use the declared operation. Do not duplicate its
  devshell, secret, port, or service contract in an ad hoc wrapper.
