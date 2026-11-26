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

Within the Python package, `job_queries` owns job reads, selected attempts,
masked byte pages and waiting. `launch` owns job creation and controls;
`artifacts` owns attempt directories. Both the CLI and gateway use these shared
functions. Waiting never cancels a job; queue cleanup keeps its input and output.

## Verbs

| Verb                                                                                          | Does                                                                                                                                                                                                                                                                                                 |
| --------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `project list \| get [p] \| operations [p]`                                                   | the configured descriptors                                                                                                                                                                                                                                                                           |
| `job start [p] <op> [--workspace P] [--wait] [--if-idle] [--fresh] [--priority N] [--discretionary] [-- args…]` | queue an operation in its pool, label `<p>:<op>`; `--if-idle` skips it while the same label is queued or running; `--fresh` runs a cached operation even when a matching job exists; `--priority` (-100 to 100, default 0) sets this job's pueue priority: within its pool a higher one starts first; `--discretionary` holds the job while the subscription is above the quota threshold |
| `owners [--unowned] [--sizes]`                                                                   | each entry under `/realm/tmp/work`, the worktree roots and the compiler cache with the owner that will remove it (job, session, worktree, process, the devshell sweeper), marking those with none; it deletes nothing                                                                                 |
| `job list [--project p] [--active] [--all]`                                                   | job rows, newest first (40 unless `--all`)                                                                                                                                                                                                                                                           |
| `job snapshot [--limit N]`                                                                    | group state and counts plus bounded job rows, unfinished first                                                                                                                                                                                                                                       |
| `job get \| logs \| result \| cancel \| retry \| wait <id>`                                   | one job by pueue task ID, with optional `--job-id` checked against that row; `--attempt` selects a retry; `logs`/`result` page with `--offset`/`--limit`                                                                                                                                             |
| `job admit`                                                                                   | release held jobs the job plane's free memory now covers ([memory admission](#memory-admission)); the `agentctl-admit` timer runs it every minute                                                                                                    |
| `job clean <id> \| --all-terminal`                                                            | remove terminal entries; `--all-terminal` removes only jobs finished more than 24 hours ago; inputs and output stay                                                                                                                                                                                  |
| `worktree clean [p] [--path P]`                                                               | retire completed checkouts whose work is published, keeping any with unpublished or uncommitted work                                                                                                                                                                                                 |
| `worktree build-output [--root D] [--expire-idle-days N [--apply]]` | what each checkout's build output occupies and when it was last used; with `--expire-idle-days`, remove that output for idle checkouts (a dry run without `--apply`) |
| `view [p]`                                                                                    | queue groups, recent failures, active jobs and ready tasks                                                                                                                                                                                                                                           |
| `events tail [--lines N] [--follow] [--project p]`                                            | the event log (`/realm/state/agentctl/events.jsonl`)                                                                                                                                                                                                                                                 |
| `pools apply`                                                                                 | write the declared pool widths into the running pueued                                                                                                                                                                                                                                               |

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
Both values are positive integers. Omitted values keep Nix defaults;
`--no-build` evaluates the same complete default target set without building.
Discovery retains its recycled evaluator workers; the explicit bounds apply to
the subsequent Nix build.

## Jobs

`project operations` and `project get` show the effective pool from the same
default-branch descriptor that `job start` uses. `checkout_pool` also retains the
selected checkout's declaration. Commands and arguments still
come from that checkout.

`job get` reports the selected job and its group's running and waiting jobs.
Queued order follows pueue priority (highest first), then task ID, among jobs
whose dependencies are satisfied. Paused groups, paused tasks and operator
stashes have distinct reasons.

### Announced operations

An operation declared `announce = true` changes the live machine (Sinnix
declares it on `switch` and `boot`). The queue already runs such jobs one at a
time; the declaration adds visibility at the moment of asking. `job start`
records the commit the checkout stands on, and when other announced jobs are
queued or running it prints one line per job on stderr (label, task, phase,
since when, the calling session and its commit) and returns them as
`announced_ahead`. The new job is queued as usual. `sinnix state` lists them
under Activations.

### Discretionary jobs

`job start --discretionary` is the starter saying this job can wait. agentctl
then runs the configured `quota_check` command. When it answers that the
subscription is above its threshold and names the reset time, the job is added
held (pueue's delayed enqueue) and pueue releases it by itself a minute after
that reset. The launch input records `deferred` (`reason`, `until`); the start
prints it, and `job snapshot` and `sinnix state` show it as the reason the job
waits. A job with a memory reservation is instead held by admission, which
releases it no earlier than `until`; pueue's delay would put it in its pool
unadmitted. A check that is absent, fails, or names no reset time defers nothing.
agentctl never marks a job discretionary by itself: an ordinary `job start`
does not run the check.

A job has two IDs: pueue's numeric `task_id` and agentctl's string `job_id`.
Every job verb selects the numeric ID. An optional `--job-id` must match the
same row; a mismatch is refused. Agentctl does not search for another row.
Hourly queue cleanup keeps tasks that finished within the last 24 hours,
including the newest IDs. After a task has been removed, its saved input and
output remain readable with its original numeric ID and `--job-id`.

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

The launch input also records when the job was enqueued and, when the
launching process can say, who started it: `caller.harness` and
`caller.session` from the agent session variable (`CLAUDE_CODE_SESSION_ID`,
`CODEX_THREAD_ID`), `caller.bead` from `AGENTCTL_LANE_BEAD`, and
`caller.principal`. Both ride on the job's `queue-task` events. `job snapshot`
shows them on unfinished rows with the command and checkout, and gives each
queued row a `wait` reason: `group-paused`, `dependencies`, `pool-full` (with
the jobs holding the pool), `priority-order` or `ready`. A job held by
[memory admission](#memory-admission) has phase `waiting-memory` and reason
`memory` (its `memory_mib`, the plane's `free_mib` and `ceiling_mib`, and
`behind` when an older held job may not be passed), or phase `queued` with
reason `pool-full`, `group-paused` or `deferred`. `job get` reports the same
reason, `job list` the same phase, and `job start` and `job wait` print the
line on stderr, e.g. `waiting for memory: needs 6144 MiB, 3284 of 7680 MiB free`.
`job start --idempotency-key` binds a caller's request to one launch:
a replay reuses the accepted launch, and an unprovable submission raises
instead of resubmitting.

`agentctl-run` runs the argv as a transient unit
`agentctl-<group>-<stem>-<digest>.service` in `agent-ctl-<group>.slice`
(`ExitType=cgroup`, `KillMode=control-group`, `RuntimeMaxSec=<timeout>`). The
job ends when the unit's cgroup is empty, so a surviving descendant still holds
the pool slot. Systemd owns the queued execution deadline; the wrapper waits
for an actual terminal or missing-unit observation rather than caching a second
runtime timer. It follows systemd pending and stop-grace states. Temporary
property-query failures retain ownership and do not end the
command; cancellation remains available outside the allocation lock. Bare
foreground commands still enforce their own declared execution timeout.
The unit environment carries `AGENTCTL_JOB_ID`, the project,
operation, `AGENTCTL_CHECKOUT_ID` and `AGENTCTL_CHECKOUT_HEAD`.
The same authoritative job identity is exported through the runner-neutral
`DEVKIT_JOB_RUNNER=agentctl` and `DEVKIT_JOB_ID` interfaces for product tooling.

Each invocation gets `jobs/<ref>.attempts/<n>/`:

- `output.log`: diagnostics, plus all output for `exit` jobs.
- `output.result`: stdout alone, for `json` and `pytest` jobs.
- `output.outcome`: how the invocation ended, with the unit's
  `memory_peak_mib` when systemd reported it.

`jobs/<ref>.log`, `.result` and `.outcome` are links to the latest attempt.
Jobs from before attempt directories existed keep their plain files as
attempt 1. A retry never overwrites an earlier attempt.

| Outcome     | Exit | Meaning                                                          |
| ----------- | ---- | ---------------------------------------------------------------- |
| `success`   | 0    | the command exited 0                                             |
| `failed`    | n    | the command's exit status                                        |
| `timeout`   | 124  | `RuntimeMaxSec` expired                                          |
| `cancelled` | 130  | the job was cancelled                                            |
| `vanished`  | 126  | the unit's terminal status could not be observed                 |
| (refused)   | 125  | refused before starting (vanished workdir, unresolvable command) |
| `out-of-memory` | 121 | the kernel or systemd-oomd killed the unit (`Result=oom-kill`) |

An `out-of-memory` job was the victim the host chose when agent work reached
its memory ceiling ([resource control](resource-control.md)); the log ends
with `killed: out of memory in the agent budget`. Job units carry
`OOMPolicy=kill`, so the whole unit ends with the killed process. Admission
counts what jobs use as well as what they reserve, so a recurring kill means
some job outgrew its reservation: compare the outcomes' `memory_peak_mib`
(the unit's peak, page cache included) with the operations' `admission`.

Terminal outcomes publish retained records and finish events for the event feed. They do not send phone notifications. Producers that require
operator action use explicit alarm paths.

`job cancel` writes the cancellation request and stops the job's exact
systemd unit before changing the queue task. Startup and cancellation use the
same attempt lock, so a cancellation cannot pass an in-progress unit start.
A queued task is removed. For a running task, the wrapper gets time to save its
outcome and output before pueue kills it if necessary. A failed unit stop is
reported and leaves the queue task in place. No process or cgroup scan runs.
`--actor` and `--reason` are saved with the request. `--expected-attempt <n>`
refuses if a different attempt has started. A retry uses `pueue restart` on the
same task; its previous output stays in the previous attempt directory.

The runner stops a previous unit with the same job name before creating
scratch or starting the new command. Other job units are left to pueue's group
widths. `job wait` observes completion; an expired wait exits 4 without
cancelling the job.

Cached operations keep Git observations from the start and end of execution.
A successful cached result is reused only when both show the requested clean
tree and the saved environment matches. Operations with `cache = "none"`
omit those endpoint records. Checkout root and HEAD still reach the command's
environment.

Launch inputs may set `unit_properties`, limited to resource limits
(`MemoryMax`, `MemoryHigh`, `MemorySwapMax`, `MemoryZSwapMax`, `TasksMax`,
`CPUWeight`, `IOWeight`, `IOReadBandwidthMax`, `IOWriteBandwidthMax`) and path
access (`ReadOnlyPaths`, `ReadWritePaths`, `InaccessiblePaths`).

### Scratch

Every job gets one directory of its own, `/realm/tmp/work/agentctl/<ref>`, or
`/dev/shm/agentctl/<ref>` for an operation declaring `scratch = "tmpfs"`
(mode 0700), exported as `AGENTCTL_SCRATCH`, `DEVKIT_SCRATCH` and `TMPDIR`.
After the unit exits, whatever the outcome, agentctl deletes it. If deletion fails, the outcome
records `scratch.cleanup_error` and the command's exit status is unchanged.
An existing path is never reused or removed. Cleanup also runs if result
bookkeeping fails after the command ends. If a unit's observation fails,
agentctl stops that unit before removing its scratch. When termination cannot
be confirmed, the outcome names the unit and records `scratch.cleanup_error`;
the scratch remains available to that unit. Retained results belong outside
the disposable scratch directory.

## Pools

Pools are pueue groups declared by `sinnix.services.agentctl.pools` and
rendered into `/etc/sinnix/agentctl.json` (`agentctl pools apply --json` shows
the live widths). `pools apply` creates missing groups and resizes drifted ones
in the running daemon, keeping every task and pause; restarting pueued instead
would mark running tasks killed. Each pool has a slice `agent-ctl-<pool>.slice`
whose resource budget comes from `flake/data/runtime-defaults.nix`. Every pool
slice sits under `agent-ctl.slice`, inside the host's agent budget
(`agent.slice`), which it shares with interactive agents and their tools.

A pool declares one fixed `parallel` width. Pueue enforces it. Applying pool
settings changes widths without restarting the daemon or its running jobs.

**Concurrent builds.** The widths of the pools that run Cargo builds
(`normal` 1, `bulk` 1, `compile` 1) bound how many run at once within each
pool, so a job takes its queue slot only when it can run; no job waits inside
its slot. Across pools, memory admission decides. The ceiling, not the widths,
protects the host.

### Memory admission

Each pueue group admits on its own, so groups alone would start a build in
every pool at once and overfill the plane's `MemoryMax`, where the kernel or
systemd-oomd kills one of them. A job therefore reserves memory: its
operation's `admission.memory_mib`, else its pool's `memory_mib`. A job with a
reservation is added to pueue stashed (the launch input records
`admission.held`) and released into its group when

- the group is running and has a free slot, so the job starts at once, and
- the plane's free memory covers the reservation.

The plane's committed memory is what it holds now that reclaim cannot free
(`memory.current` less clean page cache, read from `agent-ctl.slice`), plus
the part of each running reservation its job has not used yet, plus the whole
reservation of each released job that has not started. A job using more than
it reserved is charged what it uses. When no reserved job is running, the
first held job starts whatever its size, so neither a reservation larger than
the plane nor memory held by unreserved work blocks the queue for good.
Pools whose jobs are agents (`agent`, `codex`, the shell pools) reserve
nothing: an agent waits on builds of its own, and a reservation it held would
keep them out. Their usage still counts.

Held jobs are released in pueue's order (priority, then task ID) across all
pools. A smaller job may pass a held one that does not fit until that one has
waited ten minutes; from then on nothing passes it. A job added stashed by
its caller, or stashed by hand, is never released by admission.

There is no daemon. A pass runs under one lock (`<state_dir>/admission.lock`)
when a job is added or retried, when a job's wrapper finishes (after its unit
has ended, counting its own slot as free), when a job is cancelled, and every
minute from `agentctl-admit.timer`, which covers deferrals running out, pools
resumed by hand and wrappers killed before their own pass. Each pass reads
pueue's state, the launch inputs and the plane's cgroup afresh, and records
each release as an `admission` event. `agentctl job admit` runs one pass and
prints what it released and why the rest wait.

**Pausing work.** `pueue pause --group <pool> --wait` stops new jobs in a
group while its running jobs finish. `pueue start --group <pool>` resumes it.

- **Freezing running work:** a paused group admits nothing new, but jobs
  already running keep running in their own units. To take the disk or memory
  back now (for example while PostgreSQL finishes a checkpoint), freeze them:
  `systemctl --user freeze agent-ctl.slice`, and `thaw` it afterwards. Each
  unit shows `FreezerState=frozen-by-parent` while frozen.
- **Long copies and offloads** belong in the `background` pool, whose slice has
  the plane's lowest I/O weight. Benchmarks and measurements run in the
  one-slot `measure` pool, and full system builds, including `switch` and
  `boot`, in the one-slot `system-build` pool, so neither occupies a `bulk` slot
  a check is waiting for and an activation never waits behind a product check.
- **Rust type and lint checks** (the Rust projects' `compile` operations and
  their Clippy operations) run in the one-slot `compile` pool. They write only
  metadata, so they neither wait behind test builds nor stop when `normal`
  and `bulk` are paused, and an agent learns within minutes whether its head
  compiles. Focused test builds run in `normal`.

## Worktrees

`agentctl worktree clean` is an explicit request to retire completed,
registered worktrees. It lists them through Git and removes them through
worktrunk; it does not create checkouts or copy artifacts.

```sh
agentctl worktree clean polylogue --path /realm/worktree/finished-change --json
```

`agentctl worktree build-output` reports and expires build output without
retiring anything; see [worktree cleanup](worktree-cleanup.md#build-output-of-idle-checkouts).

Omit `--path` for a project-wide pass. The main checkout and locked checkouts
stay. Before removal, agentctl fetches the default branch from `origin` (the
descriptor's `workspace.default_base`, otherwise origin's HEAD). Publication
requires one of these exact checks:

- HEAD is in the default branch's history.
- HEAD's tree equals the current default branch's tree.
- A merged pull request has exactly this HEAD and its merge commit is in the
  fetched default branch's history.

Tracked changes and untracked nonignored files prevent removal. An unfinished
queue job whose working directory is this checkout or inside it also prevents
removal; the reason names the task and job. Agentctl does not scan processes.
A shell or editor outside its queue may lose its working directory when the
checkout is removed. Ignored files go with the checkout.

Before removal, a Git ref under `refs/agentctl/recovery/checkouts/` saves HEAD.
Agentctl calls `wt remove` in the foreground without process termination,
deletes the checkout's Cargo cache directory, then deletes its local branch.
The remote branch is deleted only while it still names the published HEAD;
the push checks that exact commit. Errors and retained branches are reported.
The recovery ref preserves committed source; output needed after retirement
belongs outside the checkout. Job input, attempts and output in agentctl's
state directory remain available.

See [compiler targets](worktree-cleanup.md#compiler-targets) for per-checkout
Cargo caches, dependency seeding and their release with the checkout. Reserve a checkout
between jobs with `git worktree lock --reason "owner and purpose" <path>`;
release it with `git worktree unlock <path>` before requesting retirement.

Hourly `job clean --all-terminal` removes queue tasks finished more than 24
hours ago, keeping recent IDs and saved output. Worktree retirement runs only
when explicitly requested through `worktree clean`.

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

| Field                 | Meaning                                                                                                                                                                                                                                                                                                                                           |
| --------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `description`, `exec` | what it does; argv with no shell                                                                                                                                                                                                                                                                                                                  |
| `environment`         | string values applied after project inheritance/unsets/values and before entering its environment command; e.g. `{ CARGO_TARGET_DIR = "target" }`                                                                                                                                                                                                 |
| `pool`                | the pueue group                                                                                                                                                                                                                                                                                                                                   |
| `result`              | `exit` (default), `json` or `pytest`                                                                                                                                                                                                                                                                                                              |
| `timeout_seconds`     | 1 to 28,800, or 0 for no limit; default 3,600                                                                                                                                                                                                                                                                                                     |
| `arguments`           | `none`, or `required` when the caller must pass a selector after `--`                                                                                                                                                                                                                                                                             |
| `cache`               | `none` (default), or `tree+environment` to answer a request from an active or successful job with the same clean content tree, environment and arguments, in any checkout of the project and at any commit; after the queue entry is cleaned, its retained outcome still answers (`<state_dir>/results/` maps each request key to its newest job) |
| `scratch`             | `nvme` (default) or `tmpfs`                                                                                                                                                                                                                                                                                                                       |
| `admission`           | `{ memory_mib }`: the memory the job reserves in the job plane ([memory admission](#memory-admission)), overriding its pool's default; exported as `AGENTCTL_ADMISSION_MEMORY_MIB`. It is not a unit limit                                                                                                                                        |
| `unit_properties`     | resource limits for the unit, e.g. `["MemoryMax=3G", "IOReadBandwidthMax=/realm 20M"]`                                                                                                                                                                                                                                                            |

| `announce`            | `true` for an operation that changes the live machine: its caller is told which other announced jobs are queued or running |

Unknown operation fields are ignored with a warning.

`[environment]` declares `kind`, `command`, `inherit`, `unset`, `values` and
`require`. A missing required variable fails the launch.

`[workspace]` optionally declares `root` and `default_base`. Operations choose their
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
`job_queries.py`. Operations declare their deadline; waiting observes the job until terminal state, and cancellation stops its named unit.

## Host wiring

`modules/services/agentctl.nix` renders `/etc/sinnix/agentctl.json`:
`project_roots`, `event_spool`, `state_dir` and `pools`,
with each pool as `{parallel, memory_mib}`; `build_output_exempt`
(`sinnix.services.agentctl.buildOutputExempt`), the worktree names whose build
output is never examined; and `quota_check`, the command asked before a
discretionary job is queued. It installs `agentctl`, `wt`, `pueue` and
`gh`, keeps job state (`~/.local/state/agentctl`, a link to
`/realm/state/agentctl` beside the event spool) off the root disk, and
declares these units:

- `agentctl-clean-queue` (hourly: removes tasks finished over 24 hours ago).
- `agentctl-pools`, which reapplies pool widths whenever pueued starts or the
  configuration changes.
- `agentctl-admit` (every minute: one [memory admission](#memory-admission)
  pass).

pueued and the pool slices come from `modules/features/cli/core.nix` and
`flake/data/runtime-defaults.nix`. The package's test suite drives a private
pueued end to end.
