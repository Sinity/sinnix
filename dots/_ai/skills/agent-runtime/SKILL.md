---
name: agent-runtime
description: "Run, watch, recover, or clean AgentCTL jobs and retained history: native queue state, exact identities, artifacts, pressure pauses, and preservation-aware worktree cleanup."
---

# Agent runtime

AgentCTL runs declared operations over pueue and systemd. Git owns checkouts
and publication; Beads owns tasks and decisions. Use `agentctl <verb> --help`
and [the command contract](../../../../docs/agentctl.md) for syntax.

## Native jobs

- Discover operations with `agentctl project operations <project>`. Short
  foreground probes run directly; queued, heavy, detached or shared checks use
  `agentctl job start <project> <operation> [--workspace <worktree>] -- <args>`.
- Keep both the numeric task_id and stable string job_id. Pass `--job-id` to
  reads and controls so a queue reorder cannot redirect the call.
- Wait for a job by blocking on it once: `agentctl job start … --wait`, or
  `agentctl job wait --job-id <id> <task_id>`, which returns at completion
  without cancelling. Read `result` and `logs` after it is terminal; each
  repeated `job get`, `logs`, `tail` or `sleep` costs a turn and learns nothing
  new. Read original artifacts; a successful transport proves only what its
  payload covers.
- Pools run one heavy job at a time, so queue order decides wall time. Give
  short jobs that unblock others (an activation, a compile or fast check, a
  focused rerun) `--priority 50`; leave full checks and package builds at the
  default.
- Bound log reads: `journalctl` takes an exact unit and `--since` within the
  job's lifetime, plus `-n`; a glob unit over days of journal can read for
  hours.
- Keep one `agentctl events tail --follow --project <project>` watch per
  concern. Reuse its live handle and stop a watch you own when its purpose ends.
- A queued job is already running work. Wait for its completion event before
  retrying. Diagnose a terminal failure first; an uncertain launch is not a
  reason to submit it again. Cancel by recorded identity, then confirm terminal
  state before retrying. `pressure tick` reconciles admission holds.
- Leave a branch alone while its check runs; a result belongs to the commit
  it ran on. Rerun a check only when the tree it covers changed. Report
  failures and untested scope.
- In Codex, an exec session_id remains live after the outer tool call returns.
  Observe it through write_stdin; terminate owned supervision and confirm exit
  when it ends. At about twice an evidence-based expected duration, inspect
  live state and decide to repair, cancel, or extend.

## Retained history and cleanup

`batch list` and `batch status` read original manifests and native job
observations. `evidence list` and `evidence get` read original native evidence
and verify artifact identities. Missing or inaccessible history stays explicit.
Historical executors cannot be resumed or retried through the supported route.
Record new verification and publication references directly with Beads and Git.

`agentctl worktree clean <project>` releases terminal owned checkouts only
when process/queue holders, working bytes, ignored files and retained job output
permit it. It retains recovery refs and reports every checkout it keeps.
`job clean` releases terminal queue entries while retaining their inputs,
attempts and original output. Use these owners rather than deleting state files.

## Finish

Report the actual outcome, exact verification and unresolved criteria. Preserve
recoverable WIP and name the owning worktree or job. Native agents land through
the repository's publication policy; use `orchestrate` when coordinating agents.
