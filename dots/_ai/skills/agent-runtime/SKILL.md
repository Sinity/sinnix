---
name: agent-runtime
description: Run, watch, recover, or clean AgentCTL work — declared operations as pueue jobs, batches of isolated workers, landing tasks, results, events, and backpressure.
---

# Agent runtime

`agentctl` is a CLI over owners that keep their own state: pueue for jobs,
worktrunk for batch worktrees, GitHub for publication, Beads for tasks, systemd
for fixed services and timers. It holds no campaign state, so neither should
you. `agentctl <verb> --help` gives the installed syntax and
`/realm/project/sinnix/repo/docs/agentctl.md` the output and exit-code contract.
A capability you need but cannot find is a task against the substrate; the
extension point is a declared operation in the project's
`.agentctl/project.toml`.

## Where state is

- `agentctl view <project>`: queue pressure, active jobs, open runs, ready
  work. `--json` gives the same document.
- `agentctl events tail --follow --project <project>`: every task start and
  finish and every backpressure change. Keep one watch per concern; on
  takeover, inspect the existing watches' argv before adding one, and stop a
  watch you own when its purpose ends. Coordinators only: a batch worker
  waits on its own job with `agentctl job wait <id>`.
- `agentctl job get|logs|result <id>`: one job (the ID is the pueue task ID).
- `agentctl batch status <run>`: one run, joining its manifest
  (`~/.local/state/agentctl/runs/<run>.json`) with pueue state and the landing
  PR. A run ID's suffix is accepted everywhere.

## Jobs

List the declared work with `agentctl project operations <project>` and start
it with `agentctl job start <project> <operation>`; never rebuild its
environment, pool, timeout, `systemd-run` scope, or reaper by hand. Keep the
returned job ID. A queued job is running work: wait for its finish event
instead of starting it again. Retry only after reading the terminal result and
fixing its named cause. A wedged job gets one cancel, a check that it is
terminal, then a retry.

A paused pool is an admission hold. Run `agentctl backpressure tick` and wait
for the release before dispatching more; running jobs continue.

Agents spawned inside a Claude or Codex session are not pueue jobs. Heavy
gates, broad type checks, suites, and builds use `agentctl job start` with
`--workspace <worktree>`. Bounded low-memory import/static probes and small
diagnostics may run directly; avoid launching a managed job for every tiny check.

In Codex, a `functions.exec` call that returns a `session_id` is still
running and continues through `write_stdin`; the outer "Script completed"
describes only the JavaScript call. Terminate what you own and confirm the
exit when supervision ends.

## Batches

`agentctl batch start <project> <task>… [--worker a,b]… [--backend B --model M
--effort E]` validates and claims the members, creates one worktree per
ownership group (a seed task plus its open `dispatch_group` members, or an
explicit `--worker` list), and queues the workers with the landing task behind
them. With `--workers external`, you run the workers yourself in the manifest's
worktrees and file each with `batch result <run> <worker> <result.json>`; the
last result queues the landing. Landing integrates, runs the declared
candidate checks and review policy, publishes per the descriptor's
`[workspace].publish` (`pr`: one squash-merged PR titled from the leader task,
`bug` → `fix:`, `feature` → `feat:`, otherwise `chore:`; `master`: a
fast-forward), and closes the tasks its acceptance record satisfies.

| Stage                       | Next                                                         |
| --------------------------- | ------------------------------------------------------------ |
| `working`, `landing`        | wait for the event                                           |
| `stashed`                   | file `batch result` for each external worker                 |
| `awaiting workers`          | read worker tasks and results; file or recover, then resume  |
| `ready to land`             | `batch land <run>`                                           |
| `landing dependency-failed` | fix the failed worker, then `batch resume --worker <w>`      |
| `failed: <code>`            | read landing logs and `landing.review_verdict`; fix, re-land |
| `unprepared`                | read the refusal and correct it before starting again        |
| `landed`, `abandoned`       | nothing                                                      |

- A finding confined to one worker goes back to it with `batch resume`.
  Cross-worker findings are fixed on the integration branch, then
  `batch land <run> --keep-integration`.
- `batch abandon <run>` releases a run that will not land; it keeps any
  worktree holding unpreserved work. `batch clean <project>` removes finished
  runs' worktrees by recorded state, never by age.
- The standing worker rules live in
  [worker-contract.md](../orchestrate/references/worker-contract.md), which
  AgentCTL compiles into every worker prompt.

## Worker toolbelt

Batch workers have `lane` on PATH. `lane task` prints the packet. `lane
verify` runs the descriptor's focused profile without arguments. For an
operation requiring a selector, use `agentctl job start <project> <operation>
--workspace <worktree> -- <selector>` explicitly. `lane done <result.json>` requires a clean tree,
validates the result, checks `candidate_sha` against `HEAD`, and prints it as
the final message; it never pushes.

## Before reporting work finished

Report the actual terminal result of work you claim finished, with useful job
IDs and any remaining blockers. A batch is landed when its merge is on the
default branch. Preserve WIP, name worktrees kept for continuation, and stop
watches you own when their purpose ends. No per-item narration is needed.

## Failures

- Dead worker: preserve its worktree, then resume its owner or abandon the
  run.
- Failed landing: read the status and landing logs, fix the named cause, land
  again. Reuse earlier evidence only when its base and contract still match.
- Unknown pool or environment mismatch: fix the descriptor, not a wrapper.
- Give long work an evidence-based duration; at about twice it, inspect and
  decide to repair, cancel, or extend.
