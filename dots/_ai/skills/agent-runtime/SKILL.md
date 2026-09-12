---
name: agent-runtime
description: Operate or recover agentctl jobs and batches — declared operations as pueue tasks, worker worktrees, the landing task, logs, results, cancellation, cleanup and resumption.
---

# Agent runtime

`agentctl` is an in-process CLI. pueue owns job state, worktrunk owns batch
worktrees, GitHub owns hosted publication, Beads owns tasks, and systemd owns
fixed services and timer wake-ups. Do not create a second ledger or job
controller. `docs/agentctl.md` owns verb, output, and exit-code details; use
`agentctl <verb> --help` for the installed surface.

## Jobs

List declared work with `agentctl project operations <project>`, then use
`agentctl job start` rather than reconstructing its environment, pool, or
timeout. Inspect a job through `get`, `logs`, and `result`; use `cancel`,
`retry`, or `clean` only after reading their current help.

Every task start and finish reaches `agentctl events tail --follow`. Keep one
watch per concern. In `functions.exec`, a returned `session_id` is still
running and must be resumed through `write_stdin`; an outer “Script completed”
only describes the JavaScript call. When supervision ends, terminate the
owned command and verify its exit. On takeover, inspect the full argv before
creating another watch.

Give long work an evidence-based duration estimate. At roughly twice it,
inspect progress and cancel, repair, or extend with a reason.

### Session subagents run outside pueue

Subagents spawned inside a Claude session are not jobs and pueue never sees
them. Give them an explicit bound: one pytest at a time, `-n 2`, or route the
heavy step through `agentctl job start`.

## Batches

A batch is several workers on one base commit landed as one candidate. Its
manifest is `~/.local/state/agentctl/runs/<run>.json`.

`batch start` creates a manifest and one worktree per ownership group. A
queued batch runs its landing task after its workers; an external batch needs
one schema-valid `batch result` for every worker before landing. Read `batch
status` before recovery. Resume one worker in its existing worktree, land a
named failure after correcting it, or abandon a run that will not land.
`batch clean` follows recorded run state and preserves uncommitted or
unmerged work.

## The screen

`agentctl view <project>` shows queue pressure, active jobs, open runs, and
ready work; `events tail` shows the same over time. Pressure stops admissions,
not running jobs. pueue dependencies and operator stashes stay separate.

## Worker toolbelt

Agents have `lane` on PATH:

- `lane task` prints the dispatch packet (`.agentctl/prompt.md`).
- `lane verify` is available only when the descriptor declares a focused
  profile; it runs that operation through `agentctl job start`. A worker does
  not assume a focused profile or launch broad verification from inside its
  own run; the coordinator chooses any broader check explicitly.
- `lane done <result.json>` requires a clean tree, validates the document
  against `.agentctl/worker.schema.json` with `candidate_sha` equal to HEAD, and
  prints it as the final message. It never pushes; the landing task
  publishes.

## Failures

- Wedged job: inspect it, cancel once, confirm it is terminal, then retry.
- Dead worker: preserve its worktree, then resume its owner or abandon the
  run.
- Failed landing: read `batch status` and landing logs, fix the named cause,
  then land again. Reuse evidence only when its base and contract still match.
- Environment mismatch or an unknown pool: use the descriptor and fix its
  declaration, never an ad hoc wrapper.
