---
name: agent-runtime
description: Operate or recover AgentCTL workspaces and jobs, including checkpoints, exact-head execution, logs, results, cancellation, cleanup, and agent redispatch.
---

# Agent runtime

AgentCTL is the lifecycle authority for registered work. Systemd owns process
state and cgroups, Git owns workspace state, hosted Git owns review state,
Beads owns tasks, and sinnixd schedules work and records bounded results. Do
not add a parallel ledger for any of them.

Verbs: `status`, `shell`, `agent`, `project`, `workspace`, `events`, `lane`,
`packet`, `campaign`, `job`, `plan`. `agentctl <verb> --help` is the surface;
`--plain` prints the payload as text.

## Workspaces

`list`, `get`, `create`, `drop`, `checkpoint`, `restore`, `publish`,
`review-status`, `land`, `finish`.

- Inspect with `agentctl workspace list` and `workspace get` before mutation.
  Git is authoritative for HEAD, branch, membership, and dirty state.
- `workspace create <project> <name> --branch <b> [--base <ref>]` creates a
  linked worktree beneath the project's declared workspace root through
  worktrunk, which runs the project's own `.config/wt.toml` hooks to provision
  it. A name or branch that is already registered is refused.
- `workspace checkpoint <id>` stores digest-verified staged and unstaged
  patches plus a bounded untracked archive when project policy permits it. It
  does not create a stash or commit. `workspace restore <id> <checkpoint>`
  requires the same branch and HEAD and a clean workspace; `--recreate`
  rebuilds a missing worktree from its branch first.
- Publish only after an exact-head declared verifier succeeds:
  `workspace publish --job <verify-job> --title T [--body F] [--wait]`, then
  `review-status`, `land --job <verify-job>`, `finish`.
- `workspace drop <id>` deletes the worktree, its branch, and every job record
  and artifact bound to that checkout. It proves the content is published
  first: contained in the declared base, or carrying worktrunk's `integrated`
  verdict. `--force` says the content is expendable.

## Jobs

`start`, `fire`, `get`, `retry`, `list`, `wait`, `logs`, `result`, `cancel`,
`admission`.

- List declared operations with `agentctl project operations <project>`.
- `agentctl job start <project> <operation> [--workspace <id>]
[--parameters-json …] [--wait]`. The descriptor owns environment, resources,
  dependencies, result contract, and timeout.
- Observe with `job get`, `job logs`, `job list --kind <kind>`, `job wait`;
  read the typed artifact with `job result`. Agent jobs are
  `--kind attested-agent`.
- **Never poll.** Terminal transitions append to
  `/realm/state/agentctl/events.jsonl`; watch `agentctl events tail --follow`.
- Declared operations may run for up to eight hours; agent jobs cap at four.
- Every long launch carries an evidence-based duration expectation and a
  deadline around twice it. At the deadline, inspect progress evidence and
  cancel, repair, or extend for a stated reason.

### Record lifetime

A job record and its artifacts live exactly as long as the thing they served.
Ownership deletes them, never a clock:

- `workspace drop` / `workspace finish` deletes every record bound to that
  checkout.
- A plan owns its nodes' records; they die with the plan.
- The next terminal run of the same operation on the same checkout supersedes
  the previous record. Read a result before re-running the operation that
  produced it.

### Admission

`agentctl job admission [--project <p>]` shows holders, queue order, and the
blocking arithmetic; a queued job's own record names `blocked_by`.

- Concurrency is the only per-pool bound: `interactive` 4, `normal` 5, `bulk`
  1, `pytest` 1, `agent` 16. There is no memory metering. Memory is bounded by
  the slice hierarchy — `sinnixd.slice` carries `MemoryHigh` and
  `MemorySwapMax` for the whole job plane.
- Sustained host IO stall (`io_full_avg60` ≥ 25%) blocks new non-interactive
  admissions. It never cancels running work.
- Declared `exclusive_keys` serialize operations that share a resource.

### Session subagents run outside admission

Subagents spawned inside a Claude session are not jobs and are not admitted.
Give them an explicit bound: one pytest at a time, `-n 2`, or route the heavy
step through `agentctl job start`.

## Agents

`agentctl agent launch --project <p> --checkout <worktree-id> --prompt-file F
--backend B --model M --effort E`. Every dispatch names backend, model, and
effort. Checkout ids (`worktree-…`) come from `workspace list`; the workspace
UUID fails with "unknown registered checkout". `--coordinator-label` is copied
to the job's terminal events so a campaign monitor can filter its own lanes.

Re-dispatch an interrupted lane with a fresh `agent launch` into the same
checkout. Uncommitted work in the worktree belongs to the new agent; say so in
the prompt.

## Worker toolbelt

Attested workers have `lane` on PATH:

- `lane task` prints the dispatch snapshot while the private prompt input is
  alive.
- `lane verify` runs the project's quick verification operation through
  AgentCTL.
- `lane done report.md` requires a clean tree, pushes the branch, and emits the
  report as the final result. `lane done --incomplete report.md` pushes
  committed WIP and marks the report partial.

## Failures

- Wedged job: read `job get` and `job logs`, cancel once, confirm the unit and
  record are terminal before restarting.
- Dead worker: checkpoint its workspace, record the result and residuals on the
  bead, then release or reassign the claim.
- "sinnixd is unavailable" is a client timeout string with no diagnostic
  content: read the daemon journal.
- Environment mismatch: use the registered operation. Do not duplicate its
  devshell, secret, port, or service contract in an ad hoc wrapper.
