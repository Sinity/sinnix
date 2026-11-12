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
  without cancelling. Its exit status is the answer: 0 when the job succeeded,
  4 when it ended without success (it prints the failure lines). Chain on that
  status (`agentctl job wait <task> --job-id <id> && gh pr merge …`) instead of
  parsing its output.
- From a worktree, name the checkout: `agentctl job start --project <worktree
  path> <operation>`, or omit the project so the enclosing checkout is used. A
  bare project id selects the registered canonical checkout, not your worktree. Read `result` and `logs` after it is terminal; each
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
- Keep a checkout fixed while a native job uses it; its result belongs to
  that commit. After every native holder ends and working bytes are preserved,
  reuse the owner's checkout for a fresh branch from current `origin/master`.
  Hosted CI continues against the immutable pushed head. Rerun a check only
  when its covered tree changed; report failures and untested scope.
- In Codex, an exec session_id remains live after the outer tool call returns.
  Observe it through write_stdin; terminate owned supervision and confirm exit
  when it ends. At about twice an evidence-based expected duration, inspect
  live state and decide to repair, cancel, or extend.

## Cleanup

Record verification and publication references with Beads and Git.

`agentctl worktree clean <project> [--path <checkout>]` retires a completed
checkout only once its work is published and process and queue holders,
working bytes, ignored files and retained job output permit it. It retains recovery refs and reports every checkout it keeps.
`job clean` releases terminal queue entries while retaining their inputs,
attempts and original output. Use these owners rather than deleting state files.

## Finish

Report the actual outcome, exact verification and unresolved criteria. Preserve
recoverable WIP and name the owning worktree or job. Native agents land through
the repository's publication policy; use `orchestrate` when coordinating agents.
