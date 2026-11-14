# agentctl

`agentctl` runs declared project operations as queued jobs, reads their
retained results, and retires completed checkouts. It is an in-process CLI with
no daemon and keeps no copy of another owner's state.
External tools own the state it reads and writes:

| Owner     | Owns                                                       | Read through                       |
| --------- | ---------------------------------------------------------- | ---------------------------------- |
| pueue     | the queue, its groups (pools), processes, terminal results | `pueue status --json`, `pueue log` |
| worktrunk | worktree creation, provisioning hooks, removal             | `git worktree list --porcelain`    |
| GitHub    | PRs, review, required checks, merge                        | `gh`                               |
| Beads     | tasks and claims                                           | `bd ... --json`                    |
| systemd   | each job's unit, and the timers that start operations      | `systemctl --user`                 |

agentctl itself owns the project descriptors (`.agentctl/project.toml`), each
job's launch input and result artifacts, and the `view` screen.

Within the Python package, `job_queries` owns stable-identity reads, selected
attempts, bounded and redacted artifact pages, and observational waiting.
`launch` owns admission and mutations; `artifacts` owns invocation storage.
The CLI and the gateway call the query owner directly. Waiting
never cancels a job, and a queue cleanup retains its historical artifacts.

## Verbs

| Verb                                                                                          | Does                                                                                                                                                                                                                                                                                                 |
| --------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `project list \| get [p] \| operations [p]`                                                   | the configured descriptors                                                                                                                                                                                                                                                                           |
| `job start [p] <op> [--workspace P] [--wait] [--if-idle] [--fresh] [--priority N] [-- args…]` | queue an operation in its pool, label `<p>:<op>`; `--if-idle` skips it while the same label is queued or running; `--fresh` runs a cached operation even when a matching job exists; `--priority` (-100 to 100, default 0) sets this job's pueue priority: within its pool a higher one starts first |
| `job list [--project p] [--active] [--all]`                                                   | job rows, newest first (40 unless `--all`)                                                                                                                                                                                                                                                           |
| `job snapshot [--limit N]`                                                                    | group state and counts plus bounded job rows, unfinished first                                                                                                                                                                                                                                       |
| `job get \| logs \| result \| cancel \| retry \| wait <id>`                                   | one job by pueue task id, plus `--job-id` to follow it across a reorder; `--attempt` selects a retry; `logs`/`result` page with `--offset`/`--limit`                                                                                                                                                 |
| `job clean <id> \| --all-terminal`                                                            | remove terminal queue entries; inputs, attempts, results and evidence are kept                                                                                                                                                                                                                       |
| `worktree clean [p] [--path P]`                                                               | retire completed checkouts whose work is published, keeping any with unpublished or uncommitted work                                                                                                                                                                                                 |
| `view [p]`                                                                                    | queue groups, recent failures, active jobs and ready tasks                                                                                                                                                                                                                                           |
| `events tail [--lines N] [--follow] [--project p]`                                            | the event log (`/realm/state/agentctl/events.jsonl`)                                                                                                                                                                                                                                                 |
| `pools apply`                                                                                 | write the declared pool widths into the running pueued                                                                                                                                                                                                                                               |
| `pressure tick`                                                                               | one pass pausing or reopening groups against memory pressure                                                                                                                                                                                                                                         |

`job start --wait --wait-seconds N` and `job wait --timeout-seconds N` bound
only the caller's wait; a job's runtime limit is always its operation's
declared `timeout_seconds`. When the
waited job ends without success, both print its failure lines (nextest
verdicts, compiler errors, panics with their message, refusals and the
`recorded as run N` history pointer) and the log's last lines to stderr.
The project is `--project`, a leading positional naming a project or checkout
path, or the checkout around the working directory.

A named project selects the descriptor in its registered project root.
`--workspace CHECKOUT` changes only the execution working directory; it does
not select the checkout's descriptor or its operation limits. To use the
checkout's descriptor explicitly, pass its path as the project:
`agentctl job start --project CHECKOUT check --workspace CHECKOUT`.
The same registry resolution, descriptor trust and checkout policies apply.

Reads print tables (local time, with an age column); `--json` prints the
document. Writes print JSON on stdout and a summary line on stderr. Exit status:
0 done; 1 refused or failed; 2 usage; 3 a driven tool failed; 4 the waited job
did not succeed.

For Sinnix's default check, explicit build bounds follow the operation separator:
`agentctl job start sinnix check --workspace <checkout> -- --max-jobs 1 --cores 2`.
Both values are positive integers. Omitted values keep native Nix defaults;
`--no-build` evaluates the same complete default target set without building.
Discovery retains its recycled evaluator workers; the explicit bounds apply to
the subsequent Nix build.

## Jobs

`project operations` and `project get` show the effective pool from the same
default-branch descriptor that `job start` uses. `checkout_pool` also retains the
selected checkout's declaration. Commands and arguments still
come from that checkout.

`job get` reports current native queue occupancy, with stable job identity,
project and workspace for slot holders. Queued order follows Pueue's priority
(highest first), then task ID, among jobs whose dependencies are satisfied.
Paused groups, paused tasks, operator stashes and cross-pool admission holds
have distinct reasons. Admission inspection recomputes unfinished blockers;
a retained launch record does not make an ended job a current blocker.

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
input. Launch summaries and `job get` show the retained `descriptor_path`,
`project_root` (the descriptor root), `working_directory` (the workspace), and
`timeout_seconds`. Human output labels all four; JSON includes the same fields.
Historical inputs lacking a field do not reconstruct it from today's descriptor.
Environment values and credentials are not part of this public selection view.
`job start --idempotency-key` binds a caller's request to one launch:
a replay reuses the accepted launch, and an unprovable submission raises
instead of resubmitting.

`agentctl-run` runs the argv as a transient unit
`agentctl-<group>-<stem>-<digest>.service` in `agent-ctl-<group>.slice`
(`ExitType=cgroup`, `KillMode=control-group`, `RuntimeMaxSec=<timeout>`). The
job ends when the unit's cgroup is empty, so a surviving descendant still holds
the pool slot. The unit environment carries `AGENTCTL_JOB_ID`, the project,
operation, `AGENTCTL_CHECKOUT_ID` and `AGENTCTL_CHECKOUT_HEAD`.
The same authoritative job identity is exported through the runner-neutral
`DEVKIT_JOB_RUNNER=agentctl` and `DEVKIT_JOB_ID` interfaces for product tooling.

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

Terminal outcomes publish retained records and finish events for the native
event feed. They do not send phone notifications. Producers that require
operator action use explicit alarm paths.

`job cancel` removes a queued task. For a running one it writes the cancel
marker, stops the unit and kills the task. `--actor` and `--reason` are
recorded with the request. `--expected-attempt <n>` refuses if a newer retry
has started. `job wait` requires `--job-id` (the id `job start` prints): the queue
reuses a cancelled task's number, so a bare number can name another caller's job.
It follows the job across queue moves and resolves retained
results after the queue entry is cleaned. An expired wait exits 4 without
cancelling.

Before dispatch, the runner retains its exact unit and expected cgroup path
under the attempt allocation lock. A killed launcher therefore leaves native
custody evidence even without a cancellation request or outcome. A terminal
queue entry with surviving or unreadable membership remains nonterminal in
job reads and waits, and blocks retry and cleanup. Running jobs keep their
ordinary running view. Scratch removal also requires observed cgroup drain,
including after a timeout or a successful user-manager stop. Unavailable
initial cgroup identity remains unresolved.

Cancellation captures the unit's `ControlGroup` before stopping it and reads
`cgroup.procs` afterwards, including child cgroups. Surviving members or an
unreadable cgroup produce an incomplete cancellation disposition and a
nonterminal job view and a refused `job cancel` exit status, even when systemd
reports inactive or pueue is done.
Retry, queue cleanup and worktree cleanup refuse while that cgroup remains
populated or cannot be checked. They recheck the retained cgroup identity,
so an observed empty or removed cgroup releases the guard. The original
attempt outcome and cancellation request remain available.

Launch inputs may set `unit_properties`, limited to resource limits
(`MemoryMax`, `MemoryHigh`, `MemorySwapMax`, `MemoryZSwapMax`, `TasksMax`,
`CPUWeight`, `IOWeight`, `IOReadBandwidthMax`, `IOWriteBandwidthMax`) and path
access (`ReadOnlyPaths`, `ReadWritePaths`, `InaccessiblePaths`).

### Scratch

An operation with `scratch = "tmpfs"` or `"nvme"` gets one job-owned directory,
`/dev/shm/agentctl/<ref>` or `/realm/tmp/work/agentctl/<ref>` (mode 0700),
exported as `AGENTCTL_SCRATCH`, `DEVKIT_SCRATCH` and `TMPDIR`. An invocation
without declared scratch does not inherit `DEVKIT_SCRATCH`. After the unit exits, agentctl
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
would mark running tasks killed. Each pool has a slice `agent-ctl-<pool>.slice`
whose resource budget comes from `flake/data/runtime-defaults.nix`. Every pool
slice sits under `agent-ctl.slice`, inside the host's agent budget
(`agent.slice`), which it shares with interactive agents and their tools.

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

**Concurrent builds.** The widths of the pools that run Cargo builds
(`normal` 1, `bulk` 1, `compile` 1) bound how many run at once, so a job takes its queue slot only
when it can run; no job waits inside its slot.

The complete pressure tick, including adaptive widths and admission hold
release, has a 20-second wall-clock deadline inside the unit's 30-second
timeout. Pueue calls also have an 8-second cap. Hold release skips a busy
admission lock instead of waiting up to 60 seconds. An exhausted tick reports
`action: unavailable` and leaves remaining reconciliation to the next timer.

**Pressure pauses.** `agentctl-pressure.timer` runs `pressure tick` every
minute. Each tick reads every group's state from pueue; it keeps no record of
its own pauses.

- **Closing:** when host memory `full avg60` is at least 25%, the tick pauses
  one running group (`pueue pause --wait`, so running jobs finish), in the
  order `pytest-heavy`, `pytest`, `normal`, `bulk`, `pytest-quick`, and
  reports a `pressure` event `closed` to the event log.
- **Reopening:** once memory `full avg10` is below 10%, the tick reopens
  (`pueue start --group`) the first paused group of that order, one group per
  tick, whoever paused it. Groups outside the order are never paused or
  resumed.
- **Holding work by hand:** a manual `pueue pause` of a group in the close
  order lasts only until memory pressure is low. To hold a pool's work
  regardless of pressure, freeze its slice as below.
- **Holding running work:** a paused group admits nothing new, but jobs
  already running keep running in their own units. To take the disk or memory
  back now (for example while PostgreSQL finishes a checkpoint), freeze them:
  `systemctl --user freeze agent-ctl.slice`, and `thaw` it afterwards. Each
  unit shows `FreezerState=frozen-by-parent` while held.
- **I/O pressure** is reported, but it neither closes nor delays admission.
  Long copies and offloads belong in the `background` pool, whose slice has
  the plane's lowest I/O weight. Benchmarks and measurements run in the
  one-slot `measure` pool, and full system builds, including `switch` and
  `boot`, in the one-slot `system-build` pool, so neither holds a `bulk` slot
  a check is waiting for and an activation never waits behind a product check.
- **Rust type and lint checks** (the Rust projects' `compile` operations and
  their Clippy operations) run in the one-slot `compile` pool. They write only
  metadata, so they neither wait behind test builds nor stop when `normal`
  and `bulk` are paused, and a lane learns within minutes whether its head
  compiles.

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

Omit `--path` for a project-wide pass. Candidates are the checkouts that
retained launch inputs name as a job's working directory, once every such job
is terminal. An explicit path also identifies the author's
completed registered checkout when only foreground checks were needed; it
never overrides a known active job or unavailable terminal evidence. Git ancestry, matching published trees or an exact
merged PR head establish publication; the PR's merge must be reachable from
the fetched default branch. Optional local merge checks have a shared time and
size budget. Unproved changes stay with a reason.

Cleanup preserves declared artifacts and nextest reports (under
`<state_dir>/artifacts/checkouts/`) and the checkout's head as a Git recovery
ref (`refs/agentctl/recovery/checkouts/…`) before removing source and
qualified compiler outputs. It checks working bytes,
Git locks, queued target aliases and process cwd/exe/fd/mappings, refreshing the
shared holder census after preservation. Tagged Cargo targets and the compiler
selector's exact per-checkout external cache retire together with the checkout.
The cache tag is removed last, so interrupted removal can be retried. Unknown
nonempty directories stay; empty directory leftovers do not block retirement.

Each real checkout keeps its own writable Cargo target. Sequential whole-target
sharing is unsafe too: relative Cargo dep-info paths and source mtimes can accept
another checkout's stale path-package artifacts. Use the compiler selector's
dependency-only seed and independent target, or an explicit `CARGO_TARGET_DIR`
for a deliberate distinct target. The hourly cache cleanup preserves targets
while their marked checkout path exists; only removed checkouts become eligible
after the use grace and Cargo-holder checks. See [compiler targets](worktree-cleanup.md#compiler-targets).

Keep a functional checkout reserved between jobs with Git's existing lock:
`git worktree lock --reason "owner and purpose" /realm/worktree/retained-checkout`.
Release it with `git worktree unlock` when ownership ends. Cleanup also preserves
pre-rewrite branches and active target aliases.

Hourly maintenance runs `job clean --all-terminal` to release finished queue
entries while retaining their artifacts. Worktree retirement runs only when
its owner explicitly requests `agentctl worktree clean` or `job clean --worktrees`
after releasing the checkout.

agentctl's own index-writing Git calls are refused in a main checkout. A timed-out Git call
gets SIGTERM, then SIGKILL after ten seconds. An `index.lock` stranded by a
failed call is removed only from a worktree agentctl owns. Elsewhere it is
reported, and the job wrapper records any it finds in the outcome's
`stranded_index_locks`.

## Descriptors

`.agentctl/project.toml`:

```toml
schema = 1

[project]
id = "polylogue"
display_name = "Polylogue"
root_markers = ["Cargo.toml", "crates"]

[environment]
kind = "direct"
command = ["env"]
inherit = ["HOME", "USER", "PATH", "XDG_RUNTIME_DIR", "CARGO_TARGET_DIR"]
unset = ["PYTHONPATH", "PYTHONHOME"]

[workspace]
root = "/realm/worktree"
default_base = "origin/master"

[operations.check]
description = "Formatting, crate boundaries and the workspace test suite"
exec = ["nix", "develop", "--command", "cargo", "run", "--locked", "-p", "xtask", "--", "check"]
pool = "bulk"
result = "exit"
timeout_seconds = 1200
scratch = "tmpfs"
unit_properties = ["MemoryHigh=8G"]
```

Sinnix declares `switch` for immediate activation and `boot` for setting the
next boot default. Both invoke the existing devshell wrappers with the same
bulk pool, NVMe scratch and timeout. `agentctl job start sinnix boot` stages a
generation; reboot remains a separate action.

### Operation fields

| Field                 | Meaning                                                                                                                                                                                                                                                                                                                                 |
| --------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `description`, `exec` | what it does; argv with no shell                                                                                                                                                                                                                                                                                                        |
| `environment`         | string values applied after project inheritance/unsets/values and before entering its environment command; e.g. `{ CARGO_TARGET_DIR = "target" }`                                                                                                                                                                                       |
| `pool`                | the pueue group                                                                                                                                                                                                                                                                                                                         |
| `result`              | `exit`, `json` or `pytest`                                                                                                                                                                                                                                                                                                              |
| `timeout_seconds`     | 1 to 28,800, or 0 for no limit; default 3,600                                                                                                                                                                                                                                                                                           |
| `arguments`           | `none`, or `required` when the caller must pass a selector after `--`                                                                                                                                                                                                                                                                   |
| `cache`               | `none`, or `tree+environment` to answer a request from an active or successful job with the same clean content tree, environment and arguments, in any checkout of the project and at any commit; after the queue entry is cleaned, its retained outcome still answers (`<state_dir>/results/` maps each request key to its newest job) |
| `scratch`             | `none`, `tmpfs` or `nvme`                                                                                                                                                                                                                                                                                                               |
| `admission`           | `{ memory_mib }`: the expected footprint, exported as `AGENTCTL_ADMISSION_MEMORY_MIB`. It is not a limit                                                                                                                                                                                                                                |
| `unit_properties`     | resource limits for the unit, e.g. `["MemoryMax=3G", "IOReadBandwidthMax=/realm 20M"]`                                                                                                                                                                                                                                                  |

Unknown operation fields are ignored with a warning.

`[environment]` declares `kind`, `command`, `inherit`, `unset`, `values` and
`require`. A missing required variable fails the launch.

`[workspace]` optionally declares `root`, `default_base` and relative
`retain_artifacts` globs for preservation-aware cleanup. Operations choose their
own resources and argument requirements; a caller picks the checkout with
`--workspace`. Unknown tables are rejected; unknown fields within known tables
warn.

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
`gh`, keeps job state (`~/.local/state/agentctl`, a link to
`/realm/state/agentctl` beside the event spool) off the root disk, and
declares these units:

- `agentctl-pressure` (every minute).
- `agentctl-clean` (daily: removes finished queue tasks, keeping results).
- `agentctl-pools`, which reapplies pool widths whenever pueued starts or the
  configuration changes.

Whether a failure is already on master comes from the master GitHub Actions
run (`gh run list -b master`): every master commit runs the full check there,
and PR runs restore master's build cache, so no local job builds master.

pueued and the pool slices come from `modules/features/cli/core.nix` and
`flake/data/runtime-defaults.nix`. The package's test suite drives a private
pueued end to end.
