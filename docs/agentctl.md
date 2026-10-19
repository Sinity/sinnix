# agentctl

`agentctl` runs declared project operations as queued jobs and runs batches of
coding agents on isolated worktrees. It is an in-process CLI with no daemon.
External tools own the state it reads and writes:

| Owner     | Owns                                                       | Read through                       |
| --------- | ---------------------------------------------------------- | ---------------------------------- |
| pueue     | the queue, its groups (pools), processes, terminal results | `pueue status --json`, `pueue log` |
| worktrunk | worktree creation, provisioning hooks, removal             | `git worktree list --porcelain`    |
| GitHub    | PRs, review, required checks, merge                        | `gh`                               |
| Beads     | tasks and claims                                           | `bd ... --json`                    |
| systemd   | each job's unit, and the timers that start operations      | `systemctl --user`                 |

agentctl itself owns the project descriptors (`.agentctl/project.toml`), the
prompt compiled from a task, each job's launch input and result artifacts, each
batch's run manifest, and the `view` screen.

## Verbs

| Verb                                                                        | Does                                                                                                              |
| --------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------- |
| `project list \| get [p] \| operations [p]`                                 | the configured descriptors                                                                                        |
| `job start [p] <op> [--workspace P] [--wait] [--if-idle] [-- args…]`        | queue an operation in its pool, label `<p>:<op>`; `--if-idle` skips it while the same label is queued or running  |
| `job list [--project p] [--active] [--all]`                                 | job rows, newest first (40 unless `--all`)                                                                        |
| `job snapshot [--limit N]`                                                  | group state and counts plus bounded job rows, unfinished first                                                    |
| `job get \| logs \| result \| cancel \| retry \| wait <id>`                 | one job by pueue id or `--reference`; `--attempt` selects a retry; `logs`/`result` page with `--offset`/`--limit` |
| `job clean <id> \| --all-terminal`                                          | remove terminal queue entries; inputs, attempts, results and evidence are kept                                    |
| `batch start [p] <bead>… [--worker a,b]…`                                   | validate members, write the manifest, claim, create worktrees, queue workers and the landing behind them          |
| `batch land <run>`                                                          | the landing body: integrate, verify, review, publish, accept, clean up; re-runnable                               |
| `batch queue <run>`                                                         | queue the landing as a job instead of running it here                                                             |
| `batch status <run>` / `batch list [p]`                                     | the manifest joined with pueue state and the landing PR                                                           |
| `batch result <run> <worker> <result.json> [--attempt n]`                   | file a worker result produced by another harness                                                                  |
| `batch resume <run> --worker <w>`                                           | queue a fresh agent into the worker's worktree with a resume prompt                                               |
| `batch task [--run r --worker w --attempt n]`                               | a worker's current tasks beside its dispatch-time bindings; read-only                                             |
| `batch scope-correct <run> <worker> <candidate> --authorize <bead>=<glob>…` | replace a malformed stored worker scope, keeping the correction history                                           |
| `batch abandon <run> [--reason R]`                                          | release a run that will not land                                                                                  |
| `batch clean [p]`                                                           | remove worktrees of landed or abandoned runs, keeping any with uncommitted or unmerged work                       |
| `result validate-worker <result.json>`                                      | validate a worker result without filing it (same checks as `batch result`)                                        |
| `evidence file \| list \| get`                                              | retain or read evidence for work done outside a batch                                                             |
| `view [p]`                                                                  | queue groups, failures, active jobs, open runs and ready tasks                                                    |
| `events tail [--lines N] [--follow] [--project p]`                          | the event log (`/realm/state/agentctl/events.jsonl`)                                                              |
| `pools apply`                                                               | write the declared pool widths into the running pueued                                                            |
| `pressure tick`                                                             | one pass pausing or reopening groups against memory pressure                                                      |

`job start` and `job wait` take `--timeout-seconds` for the wait.
The project is `--project`, a leading positional naming a project or checkout
path, or the checkout around the working directory. A run is named by its full
id or its 8-character suffix.

Reads print tables (local time, with an age column); `--json` prints the
document. Writes print JSON on stdout and a summary line on stderr. Exit status:
0 done; 1 refused or failed; 2 usage; 3 a driven tool failed; 4 the waited job
did not succeed.

## Jobs

A job is a pueue task: its id is pueue's task id, its pool is pueue's group. A
task id is only a queue position (`pueue switch` swaps ids), so every job also
has a durable launch reference, returned by every job verb and accepted as
`--reference`.

`job start` writes a private launch input
(`$XDG_STATE_HOME/agentctl/inputs/<ref>.json`, mode 0600) with the argv, the
resolved environment, working directory, timeout, result kind and artifact
paths. It then runs `pueue add` with the command `agentctl-run <input>`.
`pueue add` runs with a scrubbed environment because pueue stores the adding
client's environment world-readably. The real environment rides in the launch
input. `job start --idempotency-key` binds a caller's request to one launch:
a replay reuses the accepted launch, and an unprovable submission raises
instead of resubmitting.

`agentctl-run` runs the argv as a transient unit
`agentctl-<group>-<stem>-<digest>.service` in `agentctl-<group>.slice`
(`ExitType=cgroup`, `KillMode=control-group`, `RuntimeMaxSec=<timeout>`). The
job ends when the unit's cgroup is empty, so a surviving descendant still holds
the pool slot. The unit environment carries `AGENTCTL_JOB_ID`, the project,
operation, `AGENTCTL_CHECKOUT_ID` and `AGENTCTL_CHECKOUT_HEAD`.

Each invocation gets `jobs/<ref>.attempts/<n>/`:

- `output.log`: diagnostics, plus all output for `exit` jobs.
- `output.result`: stdout alone, for `json` and `pytest` jobs.
- `output.outcome`: how the invocation ended.

`jobs/<ref>.log`, `.result` and `.outcome` are links to the latest attempt.
Jobs from before attempt directories existed keep their plain files as attempt

1. A retry never overwrites an earlier attempt.

| Outcome         | Exit | Meaning                                                          |
| --------------- | ---- | ---------------------------------------------------------------- |
| `success`       | 0    | the command exited 0                                             |
| `failed`        | n    | the command's exit status                                        |
| `timeout`       | 124  | `RuntimeMaxSec` expired                                          |
| `cancelled`     | 130  | the job was cancelled                                            |
| `vanished`      | 126  | the unit's terminal status could not be observed                 |
| `slot_occupied` | 75   | a single-slot pool was held by another unit                      |
| (refused)       | 125  | refused before starting (vanished workdir, unresolvable command) |

`job cancel` removes a queued task. For a running one it writes the cancel
marker, stops the unit and kills the task. `--actor` and `--reason` are
recorded with the request. `--expected-attempt <n>` refuses if a newer retry
has started. `job wait` follows a job across queue moves and resolves retained
results after the queue entry is cleaned. An expired wait exits 4 without
cancelling.

Launch inputs may set `unit_properties`, limited to resource limits
(`MemoryMax`, `MemoryHigh`, `MemorySwapMax`, `MemoryZSwapMax`, `TasksMax`,
`CPUWeight`, `IOWeight`, `IOReadBandwidthMax`, `IOWriteBandwidthMax`) and path
access (`ReadOnlyPaths`, `ReadWritePaths`, `InaccessiblePaths`).

### Scratch

An operation with `scratch = "tmpfs"` or `"nvme"` gets one job-owned directory,
`/dev/shm/agentctl/<ref>` or `/realm/tmp/work/agentctl/<ref>` (mode 0700),
exported as `AGENTCTL_SCRATCH` and `TMPDIR`. After the unit exits, agentctl
records its size in the outcome and deletes it. If deletion fails, the outcome
records `scratch.cleanup_error` and the command's exit status is unchanged.
An existing path is never reused or removed.

## Pools and admission

Pools are pueue groups declared by `sinnix.services.agentctl.pools` and
rendered into `/etc/sinnix/agentctl.json` (`agentctl pools apply --json` shows
the live widths). `pools apply` creates missing groups and resizes drifted ones
in the running daemon, keeping every task and pause; restarting pueued instead
would mark running tasks killed. Each pool has a slice `agentctl-<pool>.slice`
whose resource budget comes from `flake/data/runtime-defaults.nix`.

A pool declaration may also set:

- `exclusive_with`: cross-pool exclusion. `pytest-heavy` excludes `agent`, so a
  full corpus run and an implementation wave wait for each other. agentctl
  stashes the later task and releases it when the partner pool drains.
- `adaptive` (`floor`, `job_memory_bytes`, `slice`): each pressure tick
  moves the width by at most one between the floor and `parallel`. It rises
  only when memory pressure is low and the slice has room for another job's
  budget, and falls otherwise.

A single-slot pool checks its slice before starting: a unit left by a dead
wrapper whose task is terminal is stopped; a live one ends the run as
`slot_occupied`.

**Pressure pauses.** `agentctl-pressure.timer` runs `pressure tick` every
minute.

- **Closing:** when host memory `full avg60` is at least 25%, the tick pauses
  one running group (`pueue pause --wait`, so running jobs finish), in the
  order `pytest-heavy`, `pytest`, `normal`, `bulk`, `pytest-quick`. It records
  a `pressure` event `closed` with `"owner": "agentctl"` in the event log.
- **Reopening:** a group whose last recorded pause is agentctl's reopens
  (`pueue start --group`) once memory `full avg10` is below 10%, one group per
  tick.
- **Operator pauses:** a group paused by the operator, with no agentctl `closed`
  event, is never resumed. Re-pausing a group agentctl already paused does not
  transfer ownership; resume such a group by hand.
- **I/O pressure** is reported, but it neither closes nor delays admission.

## Worktrees

Creation and removal go through worktrunk and hold one lock per repository
(keyed by the common `.git`). Each returns only after Git releases the
repository's `index.lock`. Listing takes no lock and runs with
`GIT_OPTIONAL_LOCKS=0`, as do agentctl's other Git reads and every queued
command.

agentctl's own index-writing Git calls are refused in a main checkout except
the post-publish fast-forward under `publish = "master"`. A timed-out Git call
gets SIGTERM, then SIGKILL after ten seconds. An `index.lock` stranded by a
failed call is removed only from a worktree agentctl owns. Elsewhere it is
reported, and the job wrapper records any it finds in the outcome's
`stranded_index_locks`.

## Batches

A batch is several workers on one base commit, landed as one candidate. Its
record is the run manifest `$XDG_STATE_HOME/agentctl/runs/<run-id>.json`, with
the run's workers and their attempts, worktrees, results, landing state and
acceptance record. Pueue holds live task state, Beads the claims, worktrunk the
worktrees and GitHub the PR.

### Start

`batch start` resolves each seed task's dispatch group into one worker
(`--worker a,b` names one explicitly). It validates every member: open or in
progress, no open external blocker, no assignee, not in a live run.

For each worker it then:

1. Claims the tasks as `agentctl-batch-<run>`.
2. Creates a worktree on `batch/<run>/<worker>` from the base.
3. Writes the worker prompt to `.agentctl/prompt.md`.
4. Queues the worker in pool `agent`, with `MemoryMax` from
   `[workspace].agent_memory_max`.

The landing task goes in `<p>-land`, behind every worker.

A worker runs `agentctl-agent` with that prompt and the worker result schema,
then `agentctl batch result`, which validates its last message and binds it to
the worktree head. Backend, model and effort come from the flags, the task's
`model_policy` metadata, or `[packets.defaults]`. Agents start with no MCP
servers unless `--mcp-server NAME` selects some from the generated profile.

Worker, resume and review units cannot publish or change tasks:

- **Git:** pushes go to a dead URL, the credential helper is empty, and
  `SSH_AUTH_SOCK` and `GH_TOKEN` are cleared.
- **Beads:** `bd` is shimmed to `bd --readonly`.
- **Files:** the unit sees the project root read-only (with `.git` writable),
  and other workers' worktrees are hidden.

`--workers external` makes the same manifest, claims, worktrees and prompts but
queues only the landing (stashed). Another harness runs the workers and files
results with `batch result`. The last filed result releases the landing.
Re-running `batch start` on an existing manifest completes missing steps.

List-valued task metadata (`verification_commands`, `affected_paths`,
`write_scope`, `acceptance_criteria`) may be a JSON array or a `;`-separated
string. A value starting with `[` that is not an array of non-empty strings is
refused.

### Landing

`batch land <run>` records each step before starting the next, so a repeat
resumes. It holds `runs/<run>.land.lock`.

1. **Results.** Refuse unless every worker filed a valid result. A result whose
   `candidate_sha` is the base carries no commit. It is `verified` when every
   criterion is satisfied and `no_op` otherwise, and that worker is left out
   of the merge.
2. **Integrate.** Fetch the base and merge the worker commits into the
   integration worktree. On a conflict, queue one integration agent in pool
   `land-agent`. Refuse if conflict markers remain.
3. **Verify.** Run one `[workspace].verify.candidate` job on the candidate, or
   wait for the hosted check named `hosted:<check>`. The receipt records the
   tested SHA only if the checkout was clean before and after.
4. **Review.** One reviewer job (pool `land-agent`) on `git diff
base..candidate`, using the `review` agent and the judge schema. The verdict
   must be `pass`. `[workspace].review = "none"` skips this step and records
   that it was skipped.
5. **Publish.** Under `publish = "master"`, push with
   `--force-with-lease=<branch>:<base>` and fast-forward a clean main checkout.
   Under `publish = "pr"`, create or reuse the PR, wait for the declared check
   on the exact candidate, then `gh pr merge --squash --match-head-commit`.
   One base movement triggers a refresh from step 2; a second is
   `target_moved_twice`.
6. **Accept.** Write the acceptance record, close each task whose criteria are
   all satisfied or superseded, comment the residual on the rest, and remove
   worktrees that hold no unique work.

A retry reuses earlier verification and review only when the run's
`inputs_digest` (base, worker commits and results, task content, descriptor,
templates, schemas) is unchanged.

`batch abandon` cancels queued tasks, unclaims members, removes clean
worktrees (keeping branches) and records the reason. It is refused while
landing runs or after acceptance. `batch clean` removes worktrees of landed or
abandoned runs. Before deleting a branch it saves the exact commit under
`refs/agentctl/recovery/`, and it keeps any worktree that a process is using
or that holds unmerged work.

When the queue loses a task (for example after a pueued reset), `batch status`
and `view` show it as `vanished` and name the exact next command: `batch
queue`, `batch result` or `batch resume`.

### Worker result

The worker's final message is the JSON document
`dots/claude/agents/schemas/worker.schema.json` describes:

- `candidate_sha`.
- `beads`, with each acceptance criterion marked `satisfied`, `unsatisfied`
  or `superseded`, plus evidence.
- `unresolved` findings.
- `verification` receipts.
- `self_review` (required for new dispatches).

Filing checks the attempt and the dispatch-time acceptance bindings.

Changed paths are compared with the workers' `write_scope` globs. Paths outside
the scope are recorded for the reviewer, not refused. A worker may explain them
with `scope_expansion`.

### Refusals

A batch verb that cannot proceed exits 1 with `<code>: <detail>`. A landing
also records the code in `landing.failure`.

| code                           | meaning                                                                  |
| ------------------------------ | ------------------------------------------------------------------------ |
| `abandoned`                    | the run was abandoned                                                    |
| `already_accepted`             | the run already has an acceptance record                                 |
| `ambiguous_run`                | the suffix names more than one run                                       |
| `backend`                      | the backend cannot satisfy this queued execution                         |
| `candidate_mismatch`           | the worktree HEAD does not descend from the filed candidate, or is dirty |
| `candidate_off_base`           | the candidate does not descend from the run base                         |
| `check_missing`                | the declared check was not reported within ten minutes                   |
| `checks_failed`                | a required PR check failed or timed out                                  |
| `empty_candidate`              | integrating the workers produced no change                               |
| `exists`                       | a manifest with this run id exists                                       |
| `foreign_beads`                | the result covers tasks outside the worker                               |
| `harness`                      | the harness is neither `queued` nor `external`                           |
| `head_moved`                   | the PR head is no longer the verified candidate                          |
| `integration_conflict_markers` | a changed file carries a conflict marker                                 |
| `integration_dirty`            | the integration agent left an unclean tree                               |
| `integration_failed`           | the integration task did not succeed                                     |
| `integration_incomplete`       | a worker branch is not merged into the candidate                         |
| `integration_worktree_missing` | the integration branch has no directory                                  |
| `invalid_result`               | the worker result does not validate                                      |
| `landing_in_progress`          | another landing of this run is running                                   |
| `manifest`                     | the run manifest is unreadable                                           |
| `mcp_servers`                  | the MCP server selection is invalid or differs from the run              |
| `members`                      | a task cannot join the batch (`refusals` names each reason)              |
| `no_candidate_profile`         | the descriptor declares no `verify.candidate`                            |
| `project`                      | the run belongs to another project                                       |
| `publish_rejected`             | the push was rejected for a reason a refresh cannot fix                  |
| `result_already_filed`         | the worker already has a result for this attempt                         |
| `result_attempt`               | the result is not for the worker's current attempt                       |
| `result_evidence_binding`      | the result differs from its dispatch-time acceptance binding             |
| `result_self_review`           | `self_review` is required and missing                                    |
| `review_failed`                | the review task did not succeed                                          |
| `review_invalid`               | the verdict does not validate                                            |
| `review_rejected`              | the verdict is not `pass`                                                |
| `runner`                       | the agent runner is missing or not executable                            |
| `scope_violation`              | a `scope_expansion` declaration is malformed                             |
| `target_moved_twice`           | the default branch moved again after one refresh                         |
| `task_attempt`                 | the task read names a superseded or unknown attempt                      |
| `unknown_run`                  | no run has this id or suffix                                             |
| `verify_failed`                | candidate verification failed or timed out                               |
| `verify_running`               | candidate verification is still running                                  |
| `worker_active`                | the worker's task is still queued or running                             |
| `worker_missing`               | no such worker, or it has no worktree                                    |
| `worker_not_done`              | a worker's task has not finished                                         |
| `worker_result_missing`        | a worker filed no valid result                                           |
| `workspace`                    | the descriptor declares no `[workspace]`                                 |

## Evidence outside batches

Work done by an agent outside a batch can still close tasks:

```text
agentctl evidence file result.json --project <project>
agentctl evidence list <project> [--cursor C] --json
agentctl evidence get <evidence_id> --project <project> --json
```

The result names a candidate SHA, its tasks, their acceptance bindings and a
`self_review`. Each verification claim must be a job receipt,
`agentctl://jobs/<id>/<launch-reference>`. Filing checks that the job
succeeded on a clean checkout of the candidate, and records whether the
candidate is published on the base branch. Records are immutable files under
`$XDG_STATE_HOME/agentctl/native-evidence/`.

## Descriptors

`.agentctl/project.toml`:

```toml
schema = 1

[project]
id = "polylogue"
display_name = "Polylogue"
root_markers = ["pyproject.toml", "polylogue"]

[environment]
kind = "nix-develop"
command = ["nix", "develop", "--accept-flake-config", "--command"]
inherit = ["HOME", "USER", "PATH", "SSH_AUTH_SOCK", "XDG_RUNTIME_DIR"]
unset = ["PYTHONPATH"]
require = ["POLYLOGUE_ARCHIVE_ROOT"]

[environment.values]
POLYLOGUE_ARCHIVE_ROOT = "/realm/state/polylogue"

[workspace]
root = "/realm/worktree"
default_base = "origin/master"
agent_memory_max = "10G"
verify = { focused = "verify_quick", candidate = "hosted:verify", corpus = "verify_all" }
publish = "pr"

[packets.defaults]
backend = "codex"
model = "gpt-6-luna"
effort = "medium"

[operations.verify_all]
description = "Run the complete corpus"
exec = ["devtools", "verify", "--all"]
pool = "pytest"
result = "pytest"
timeout_seconds = 14400
checkout = "default"
admission = { memory_mib = 12288 }
```

### Operation fields

| Field                 | Meaning                                                                                                  |
| --------------------- | -------------------------------------------------------------------------------------------------------- |
| `description`, `exec` | what it does; argv with no shell                                                                         |
| `pool`                | the pueue group                                                                                          |
| `result`              | `exit`, `json` or `pytest`                                                                               |
| `timeout_seconds`     | 1 to 28,800, or 0 for no limit; default 3,600                                                            |
| `arguments`           | `none`, or `required` when the caller must pass a selector after `--`                                    |
| `checkout`            | `any` (the caller's `--workspace` or the project root) or `default` (the project root only)              |
| `cache`               | `none`, or `tree+environment` to reuse a matching active or completed job                                |
| `scratch`             | `none`, `tmpfs` or `nvme`                                                                                |
| `admission`           | `{ memory_mib }`: the expected footprint, exported as `AGENTCTL_ADMISSION_MEMORY_MIB`. It is not a limit |
| `unit_properties`     | resource limits for the unit, e.g. `["MemoryMax=3G", "IOReadBandwidthMax=/realm 20M"]`                   |

Unknown operation fields are ignored with a warning.

`[environment]` declares `kind`, `command`, `inherit`, `unset`, `values` and
`require`. A missing required variable fails the launch.

`[workspace]` declares:

- `root`, `default_base`, `agent_memory_max`.
- `verify`: the `focused`, `candidate` and `corpus` operations; `candidate`
  may be `hosted:<check>`.
- `publish`: `pr` or `master`.
- `review`: `agent` (default) or `none`.
- `retain_artifacts`: globs copied into run state before a checkout is
  released.

`[packets]` declares `template`, `atlas_dir`, `branch_prefix`,
`[packets.model_policy.<name>]`, `[packets.defaults]` and `[packets.review]`.
An unknown table takes the project out of service; an unknown field in a
known table is ignored with a warning.

Descriptor changes apply on the next call.

## Timers

A module's `lib.sinnix.mkScheduledJob` timer starts a declared operation with
`agentctl job start --if-idle <project> <operation>`, which skips the launch
while the same operation is queued or running. A timer passes no workspace, so
the operation runs on the project's main checkout.

## Limits

Timeouts, size bounds and exit codes are named constants in
`pkgs/agentctl/agentctl/limits.py`, `run.py`, `landing.py` and `prompts/`. The
agent watchdog is one week, and agents run until they finish or are
cancelled.

## Host wiring

`modules/services/agentctl.nix` renders `/etc/sinnix/agentctl.json`:
`project_roots`, `agent_runner`, `worker_contract`, `event_spool` and `pools`,
with each pool as `{parallel, ...}`. It installs `agentctl`, `wt`, `pueue` and
`gh`, persists `~/.local/state/agentctl`, and declares these units:

- `agentctl-pressure` (every minute).
- `agentctl-clean` (daily: removes finished queue tasks, keeping results).
- `agentctl-pools`, which reapplies pool widths whenever pueued starts or the
  configuration changes.

pueued and the pool slices come from `modules/features/cli/core.nix` and
`flake/data/runtime-defaults.nix`. The package's test suite drives a private
pueued end to end.

The worker tool `batch-worker` (`dots/_ai/skills/agent-runtime/scripts/batch-worker`) is what a
queued worker uses while it works. `batch-worker task` shows the worker its current
tasks beside the dispatch-time snapshot, and `batch-worker done` files its result.
