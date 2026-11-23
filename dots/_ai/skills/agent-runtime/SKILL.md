---
name: agent-runtime
description: "Run, watch, recover, or clean AgentCTL jobs and retained history: queue state, exact identities, artifacts, and preservation-aware worktree cleanup."
---

# Agent runtime

AgentCTL runs declared operations over pueue and systemd. Git owns checkouts
and publication; Beads owns tasks and decisions. Use `agentctl <verb> --help`
and [the command contract](../../../../docs/agentctl.md) for syntax.

## Jobs

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
- Expect durations from the record, not a guess. Typical run times here
  (November 2026): a type check (`compile`, `fast`) about 1 minute, p90 up to
  5; a focused test about 3 minutes, p90 about 7; a PR's hosted check about 19
  minutes for Polylogue, 13 for Sinex, 4 for the shared crates; queue waits
  in a busy pool can add as much again. Current figures come from the
  started and finished events per `job_id` in
  `/realm/state/agentctl/events.jsonl`, the devkit history
  (`~/.local/state/devkit/history.db`, build and test stage times per run),
  and `gh run list --json createdAt,updatedAt,conclusion`.
- Pools run one heavy job at a time, so queue order decides wall time. Give
  short jobs that unblock others (an activation, a compile or fast check, a
  focused rerun) `--priority 50`; leave full checks and package builds at the
  default.
- Bound log reads: `journalctl` takes an exact unit and `--since` within the
  job's lifetime, plus `-n`; a glob unit over days of journal can read for
  hours.
- In `pgrep -f` patterns, bracket one character so the search cannot match
  itself.
- Keep one `agentctl events tail --follow --project <project>` watch per
  concern. Reuse its live handle and stop a watch you own when its purpose ends.
- A queued job is already running work. Wait for its completion event before
  retrying. Diagnose a terminal failure first; an uncertain launch is not a
  reason to submit it again. Cancel by recorded identity, then confirm terminal
  state before retrying.
- Keep a checkout on its commit while a job uses it; the job's result belongs
  to that commit. Once every job and process using it has ended and its
  uncommitted work is preserved, the owner reuses the checkout for a fresh
  branch from current `origin/master`. Hosted CI keeps checking the pushed
  commit meanwhile. Rerun a check only
  when its covered tree changed; report failures and untested scope.
- In Codex, an exec session_id remains live after the outer tool call returns.
  Observe it through write_stdin; terminate owned supervision and confirm exit
  when it ends. At about twice an evidence-based expected duration, inspect
  live state and decide to repair, cancel, or extend.

## Cleanup

Record verification and publication references with Beads and Git.

`agentctl worktree clean <project> [--path <checkout>]` retires a completed
checkout only once its work is published and no process or queued job uses
it, and its uncommitted and ignored files and retained job output allow it. It retains recovery refs and reports every checkout it keeps.
`job clean` releases terminal queue entries while retaining their inputs,
attempts and original output. Use these owners rather than deleting state files.

## Finish

Report the actual outcome, exact verification and unresolved criteria. Preserve
recoverable WIP and name the owning worktree or job. Harness agents land through
the repository's publication policy; use `orchestrate` when coordinating agents.
