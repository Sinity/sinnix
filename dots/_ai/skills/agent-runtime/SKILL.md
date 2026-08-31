---
name: agent-runtime
description: Operate or recover AgentCTL workspaces and jobs, including checkpoints, exact-head execution, logs, results, cancellation, cleanup, and checkpoint-based redispatch.
---

# Agent runtime

AgentCTL is the lifecycle authority for registered work. Systemd owns process
state and cgroups, Git owns workspace state, hosted Git owns review state,
Beads owns tasks, and Sinnixd schedules work and records bounded results. Do
not add a parallel ledger for any of them.

## Workspaces

- Inspect with `agentctl workspace list` and `workspace get` before mutation.
- Create or adopt linked worktrees only beneath the project's declared
  workspace root. Git remains authoritative for HEAD, branch, membership, and
  dirty state on every read.
- `workspace checkpoint <id>` stores digest-verified staged and unstaged
  patches plus a bounded untracked archive when project policy permits it. It
  does not create a stash or commit.
- `workspace restore <id> <checkpoint>` requires the same branch and HEAD and
  a clean existing workspace. `workspace recover` recreates a missing
  AgentCTL-created workspace whose branch still matches the checkpoint, then
  restores it. Adopted workspaces cannot be recovered this way.
- Publish only after an exact-head declared verifier succeeds. Use
  `workspace publish`, `review-status`, `land`, and `finish` for hosted review;
  use `finish-integrated` for an already-integrated branch.
- `dispose` is only for clean, base-contained, no-review work with empty
  checkpoints. `reap` removes an eligible managed worktree but retains its
  branch. Never clean an adopted, dirty, divergent, or identity-changed tree.

## Jobs

- Discover declared operations with `agentctl project get <project>`.
- Start with `agentctl job start <project> <operation> [--workspace <id>]`.
  Parameters, when declared, enter through `--parameters-json` and are retained
  publicly only as a digest.
- Observe with `job get`, `job logs`, `job list --kind <kind>`, and `job wait
<id...> --any`; consume the typed artifact with `job result`. Cancel by job
  ID, then verify terminal state. `agentctl agent list|status|wait|result`
  are sugar over jobs of kind `attested-agent`.
- **Never poll.** Terminal transitions append to
  `/realm/state/agentctl/events.jsonl` — tail that one stream (or one
  persistent Monitor on it) instead of per-job status loops. Non-job scripts
  append their completions to the same spool by convention.
- Feature gate: the event plane, agent verbs, `--kind`, wait `--any`,
  `environment.require` (missing required vars fail dispatch loudly),
  `BEADS_ACTOR=agent-<job-id>` injection, timeout WIP-preservation, and
  14-day record retention deploy together — the daemon's `status` capability
  list is the runtime check; a daemon predating the current rebuild lacks
  them.
- The operation descriptor owns environment, resources, dependencies, result
  contract, and timeout. Declared operations may run for up to eight hours;
  typed agent jobs remain capped at one hour.
- Every long launch carries an evidence-based duration expectation and a
  deadline around twice that expectation. At the deadline, inspect progress
  evidence and choose to cancel, repair, or extend for a stated reason.

## Agent continuation

- `agentctl lane resume <workspace>` re-dispatches an interrupted lane from
  its preserved prompt into the same checkout with the original
  backend/model/effort. Uncommitted work in the worktree belongs to the
  resumed agent; the standing preamble tells it so.
- Reserve manual `agent launch --checkout <id>` for prompts that must
  differ from the original mandate (a review verdict to apply, a changed
  scope); checkout ids come from `workspace get`.

## Failures

- `agentctl agent --checkout` takes the CHECKOUT id (`worktree-…` from
  `workspace list`), not the workspace UUID — the UUID fails with "unknown
  registered checkout".
- `dispose` refuses squash-merged branches as "unpublished committed content"
  (ancestry check, not content-equality): verify branch-own files match the
  default branch, then remove worktree and branch with git directly.
- Missing workspace: inspect Git membership and checkpoint authority before
  `recover`; preserve evidence before any repair.
- Wedged job: inspect `job get` and logs, cancel once, and confirm the unit and
  record are terminal before restarting.
- Dead worker: checkpoint its workspace, record the result and residuals on
  the task, then release or reassign the claim.
- Environment mismatch: use the registered operation. Do not duplicate its
  devshell, secret, port, or service contract in ad hoc shell wrappers.
