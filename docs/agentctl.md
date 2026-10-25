# agentctl

`agentctl` runs declared project operations as queued jobs and reads preserved
work history. It is an in-process CLI with no daemon.
External tools own the state it reads and writes:

| Owner     | Owns                                                       | Read through                       |
| --------- | ---------------------------------------------------------- | ---------------------------------- |
| pueue     | the queue, its groups (pools), processes, terminal results | `pueue status --json`, `pueue log` |
| worktrunk | worktree creation, provisioning hooks, removal             | `git worktree list --porcelain`    |
| GitHub    | PRs, review, required checks, merge                        | `gh`                               |
| Beads     | tasks and claims                                           | `bd ... --json`                    |
| systemd   | each job's unit, and the timers that start operations      | `systemctl --user`                 |

agentctl itself owns the project descriptors (`.agentctl/project.toml`), each job's launch input and result artifacts, retained historical manifests,
and the `view` screen.

Within the Python package, `job_queries` owns stable-identity reads, selected
attempts, bounded and redacted artifact pages, and observational waiting.
`launch` owns admission and mutations; `artifacts` owns invocation storage.
The CLI, gateway and evidence readers call the query owner directly. Waiting
never cancels a job, and a queue cleanup retains its historical artifacts.

## Verbs

| Verb                                                                 | Does                                                                                                                                                 |
| -------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------- |
| `project list \| get [p] \| operations [p]`                          | the configured descriptors                                                                                                                           |
| `job start [p] <op> [--workspace P] [--wait] [--if-idle] [-- args…]` | queue an operation in its pool, label `<p>:<op>`; `--if-idle` skips it while the same label is queued or running                                     |
| `job list [--project p] [--active] [--all]`                          | job rows, newest first (40 unless `--all`)                                                                                                           |
| `job snapshot [--limit N]`                                           | group state and counts plus bounded job rows, unfinished first                                                                                       |
| `job get \| logs \| result \| cancel \| retry \| wait <id>`          | one job by pueue task id, plus `--job-id` to follow it across a reorder; `--attempt` selects a retry; `logs`/`result` page with `--offset`/`--limit` |
| `job clean <id> \| --all-terminal`                                   | remove terminal queue entries; inputs, attempts, results and evidence are kept                                                                       |
| `batch status <run>` / `batch list [p]`                              | the manifest joined with pueue state and the landing PR                                                                                              |
| `worktree clean [p]`                                                 | remove worktrees of landed or abandoned runs, keeping any with uncommitted or unmerged work                                                          |
| `evidence list \| get`                                               | read original retained native evidence                                                                                                               |
| `view [p]`                                                           | queue groups, failures, active jobs, open runs and ready tasks                                                                                       |
| `events tail [--lines N] [--follow] [--project p]`                   | the event log (`/realm/state/agentctl/events.jsonl`)                                                                                                 |
| `pools apply`                                                        | write the declared pool widths into the running pueued                                                                                               |
| `pressure tick`                                                      | one pass pausing or reopening groups against memory pressure                                                                                         |

`job start` and `job wait` take `--timeout-seconds` for the wait. When the
waited job ends without success, both print its failure lines (nextest
verdicts, compiler errors, panics with their message, refusals and the
`recorded as run N` history pointer) and the log's last lines to stderr.
The project is `--project`, a leading positional naming a project or checkout
path, or the checkout around the working directory. A run is named by its full
id or its 8-character suffix.

Reads print tables (local time, with an age column); `--json` prints the
document. Writes print JSON on stdout and a summary line on stderr. Exit status:
0 done; 1 refused or failed; 2 usage; 3 a driven tool failed; 4 the waited job
did not succeed.

## Jobs

A job is a pueue task, and its pool is pueue's group. Each job has two ids:
`task_id`, pueue's task number, which is only a queue position (`pueue switch`
swaps them), and `job_id`, agentctl's stable string id. Every job verb returns
both and takes the task id as its argument; pass `--job-id` too so the call
follows the job if the queue is reordered.

`job start` writes a private launch input
(`$XDG_STATE_HOME/agentctl/inputs/<job-id>.json`, mode 0600) with the argv, the
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
Jobs from before attempt directories existed keep their plain files as
attempt 1. A retry never overwrites an earlier attempt.

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
An existing path is never reused or removed. Cleanup also runs if result
bookkeeping fails after the command ends. If a unit's observation fails,
agentctl stops that unit before removing its scratch. When termination cannot
be confirmed, the outcome names the unit and records `scratch.cleanup_error`;
the scratch remains available to that unit. Retained results belong outside
the disposable scratch directory.

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

**Caps.** `sinnix.services.agentctl.caps` declares cross-pool caps, rendered
as `caps` in the configuration; `cargo = 3` bounds Cargo builds across
`normal` and `bulk`. An operation naming a cap waits, after it leaves the
queue and before its unit starts, for one of the cap's places (a lock under
`<state_dir>/caps/<name>/`); the wait holds the job's pool slot, does not count
against its timeout, is logged once, and is recorded in the outcome as `cap`.
`job start` refuses a cap the host does not declare. The width is read when
the job starts, so a changed declaration applies to queued jobs.

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
  An operation declaring `max_io_pressure` refuses to start above it, and
  long copies and offloads belong in the `background` pool, whose slice has
  the plane's lowest I/O weight.

## Worktrees

Creation and removal go through worktrunk and hold one lock per repository
(keyed by the common `.git`). Each returns only after Git releases the
repository's `index.lock`. Listing takes no lock and runs with
`GIT_OPTIONAL_LOCKS=0`, as do agentctl's other Git reads and every queued
command.

Retire a completed checkout after publication, using its exact path:

```sh
agentctl worktree clean polylogue --path /realm/worktree/finished-change --json
```

Omit `--path` for a project-wide pass. Recorded job ownership and terminal
outcomes select candidates. An explicit path also identifies the author's
completed registered checkout when only foreground checks were needed; it
never overrides a known active job or unavailable terminal evidence. Git ancestry, matching published trees or an exact
merged PR head establish publication; the PR's merge must be reachable from
the fetched default branch. Optional local merge checks have a shared time and
size budget. Unproved changes stay with a reason.

Cleanup preserves declared artifacts, nextest reports and Git recovery refs
before removing source and qualified compiler outputs. It checks working bytes,
Git locks, queued target aliases and process cwd/exe/fd/mappings, refreshing the
shared holder census after preservation. Tagged Cargo targets and the compiler
selector's exact per-checkout external cache retire together with the checkout.
The cache tag is removed last, so interrupted removal can be retried. Unknown
nonempty directories stay; empty directory leftovers do not block retirement.

Keep a functional checkout reserved between jobs with Git's existing lock:
`git worktree lock --reason "owner and purpose" /realm/worktree/retained-checkout`.
Release it with `git worktree unlock` when ownership ends. Cleanup also preserves
pre-rewrite branches and active target aliases.

The existing daily maintenance runs `job clean --all-terminal --worktrees`.
Queue results and worktree outcomes are reported separately, including kept
paths and failures. Without `--worktrees`, job-clean JSON remains unchanged.

agentctl's own index-writing Git calls are refused in a main checkout. A timed-out Git call
gets SIGTERM, then SIGKILL after ten seconds. An `index.lock` stranded by a
failed call is removed only from a worktree agentctl owns. Elsewhere it is
reported, and the job wrapper records any it finds in the outcome's
`stranded_index_locks`.

## Retained history

`batch list` and `batch status` read the original documents without loading a
workflow engine. Status may join native queue observations and the recorded PR.
Unknown original fields, incomplete attempts and artifact mappings remain in
the document. Inaccessible history is unavailable, not an empty inventory.

New work uses native agents, Git worktrees and selected declared operations.
Batch start, landing, result filing, resumption, task compilation and abandonment
commands are retired. An unfinished historical record is inspection-only.

The [worktree cleanup](#worktrees) command also reads retained invocation
ownership after finished jobs leave the queue. Historical manifests and their
original evidence remain readable.

### Refusals

Historical manifests may contain these original refusal codes. The batch
mutation commands are retired; reading a record never resumes its executor.

| code                           | meaning                                                                  |
| ------------------------------ | ------------------------------------------------------------------------ |
| `admission_closed`             | the project accepts native changes instead of new batches                |
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

## Original native evidence

`evidence list` pages summaries and reports unreadable entries. `evidence get`
returns the complete original record after checking its project, artifact size
and SHA-256 identity. Filing new worker-schema claims is retired. Record native
verification and decisions directly with the owning task and repository tools.

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
| `cap`                 | a host-declared cross-pool cap (`caps`) the job holds a place under while its unit runs                  |
| `max_io_pressure`     | refuse to start (exit 125) while host I/O `full avg60` exceeds this percentage; for measurements         |
| `admission`           | `{ memory_mib }`: the expected footprint, exported as `AGENTCTL_ADMISSION_MEMORY_MIB`. It is not a limit |
| `unit_properties`     | resource limits for the unit, e.g. `["MemoryMax=3G", "IOReadBandwidthMax=/realm 20M"]`                   |

Unknown operation fields are ignored with a warning.

`[environment]` declares `kind`, `command`, `inherit`, `unset`, `values` and
`require`. A missing required variable fails the launch.

`[workspace]` optionally declares `root`, `default_base` and relative
`retain_artifacts` globs for preservation-aware cleanup. Operations choose their
own checkouts, resources and argument requirements. The old packet, reviewer,
verification-profile and publication policy configuration is retired.

`[packets]` is no longer a descriptor table. Remove it when updating a producer.
Unknown tables are rejected; unknown fields within known tables warn.

For a supported rollback, use revision `4845906d` or later, whose absent packet
table keeps old admissions closed. Keep current manifests, dispositions, inputs
and outputs in place. Rollback changes code, never historical state, and does
not replay old executors. Earlier revisions are for historical source inspection
and are excluded from automatic activation. Arbitrary same-user native commands
remain outside this cooperative routing guarantee.

Descriptor changes apply on the next call.

## Timers

A module's `lib.sinnix.mkScheduledJob` timer starts a declared operation with
`agentctl job start --if-idle <project> <operation>`, which skips the launch
while the same operation is queued or running. A timer passes no workspace, so
the operation runs on the project's main checkout.

## Limits

Timeouts, size bounds and exit codes are owned by `limits.py`, `run.py` and
`job_queries.py`. Operations declare their deadline; waiting observes the native
unit until terminal state, and cancellation targets its recorded identity.

## Host wiring

`modules/services/agentctl.nix` renders `/etc/sinnix/agentctl.json`:
`project_roots`, `event_spool`, `state_dir` and `pools`,
with each pool as `{parallel, ...}`. It installs `agentctl`, `wt`, `pueue` and
`gh`, persists `~/.local/state/agentctl`, and declares these units:

- `agentctl-pressure` (every minute).
- `agentctl-clean` (daily: removes finished queue tasks, keeping results).
- `agentctl-pools`, which reapplies pool widths whenever pueued starts or the
  configuration changes.
- `agentctl-baseline-<project>` (every ten minutes, for each of
  `masterBaselines`): `sinnix-master-baseline` fetches the default branch and,
  when its head is new and no baseline job is active, moves the reserved
  detached checkout `<workspace root>/<project>-master` there and queues the
  project's `baseline` operation in it. Lanes read the newest
  `<project>:baseline` job to learn whether a failure is already on master;
  its warm target seeds new checkouts' targets (`docs/worktree-cleanup.md`).

pueued and the pool slices come from `modules/features/cli/core.nix` and
`flake/data/runtime-defaults.nix`. The package's test suite drives a private
pueued end to end.
