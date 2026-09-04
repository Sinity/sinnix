# agentctl

`agentctl` is an in-process CLI. There is no daemon and no socket. Four
external tools own the state it reads and writes:

| Authority | Owns                                                               | Read through                       |
| --------- | ------------------------------------------------------------------ | ---------------------------------- |
| pueue     | the queue, its groups (pools), every process, its terminal result  | `pueue status --json`, `pueue log` |
| worktrunk | worktree creation, provisioning (`.config/wt.toml` hooks), removal | `wt list --format=json` (schema 2) |
| GitHub    | PRs, review, required checks, merge                                | `gh pr list/view/create/merge`     |
| Beads     | tasks                                                              | `bd ready/show/close --json`       |
| systemd   | only the calendar wake-up a declared `schedule` needs              | transient user timers              |

What agentctl owns outright: the project descriptors, the prompt compiled
from a bead, the launch-input and result-artifact contract of a queued
command, and one operator screen.

## Verbs

| Verb                                                          | Does                                                                                                                                                                                    |
| ------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `project list \| get <p> \| operations <p>`                   | the configured descriptors (`/etc/sinnix/agentctl.json` lists the roots)                                                                                                                |
| `job start <p> <op> [--workspace <path>] [--wait] [-- args…]` | `pueue add` in the operation's pool, label `<p>:<op>`, running `sinnixd-queue-run <launch.json>`; extra arguments are appended to the declared `exec`                                   |
| `job fire <p> <op>`                                           | what a schedule timer runs: `job start` on the main checkout, skipped while the same label is queued or running                                                                         |
| `job list [--project p] [--active]`                           | `pueue status --json` reduced to job rows                                                                                                                                               |
| `job get \| logs \| result \| cancel \| retry \| wait <id>`   | one task by pueue id; `logs` reads the bounded log, `result` the typed artifact, `cancel` kills the task and its process group, `retry` is `pueue restart --in-place`                   |
| `lane start <p> <bead> [--backend --model --effort]`          | compile the prompt, `wt switch --create feature/packet/<bead>`, queue the agent in group `agent` (label `<p>:lane:<bead>`)                                                              |
| `lane publish [<worktree>] [--bead --title --body-file]`      | push, `gh pr create` under the bead's type-prefixed subject, `gh pr merge --auto --squash`; refuses a dirty worktree; the worktree defaults to cwd                                      |
| `lane rebase <p> <bead>`                                      | queue an agent with the rebase prompt into the bead's existing worktree (label `<p>:rebase:<bead>`)                                                                                     |
| `lane sync <p>`                                               | worktrees whose PR merged (or `wt` reports integrated): `bd close`, `wt remove`; the rest are reported                                                                                  |
| `refill <p> --limit N [--dry-run]`                            | `bd ready` minus beads that already have a worktree or an open PR, minus epics → `lane start`                                                                                           |
| `view [<p>]`                                                  | queue groups (running/queued/paused), what needs attention, active jobs with start and elapsed, every lane with bead, stage, since/elapsed, agent job, PR and what follows, ready beads |
| `events tail [--lines N] [--follow] [--project p]`            | the event spool (`/realm/state/agentctl/events.jsonl`)                                                                                                                                  |
| `schedule apply`                                              | make the transient timer set equal the declared schedules                                                                                                                               |

Reads print tables in local time; `agentctl --json <verb>` prints the
document. A project argument defaults to the checkout enclosing the working
directory where the table says so. Exit status: 0 done, 1 refused or failed,
2 usage, 3 the waited job (`job wait`, `job start --wait`) did not succeed.
The CLI decides nothing: it dispatches what it is told and reports; a lane's
"next" on the view describes its state.

## Jobs

A job is a pueue task. Its id is pueue's task id, its pool is pueue's group,
its state is pueue's state. `job start` writes a private launch input
(`$XDG_STATE_HOME/sinnixd/inputs/<ref>.json`, mode 0600) carrying the argv
inside the declared environment, the resolved environment, the working
directory, the timeout, the result kind and the artifact paths, then runs
`pueue add --escape -g <pool> -l <label> -- sinnixd-queue-run <input>`.

`sinnixd-queue-run` is the command every task runs. It appends a `started`
event to the spool, starts new launches in the pool's transient systemd scope,
runs the argv with the launch environment in its own session, enforces the
declared timeout (exit 124), refuses a vanished working directory (exit 125),
writes the combined log to `jobs/<ref>.log` and — for
`json`/`pytest` results — stdout alone to `jobs/<ref>.result`, both bounded at
64,000 bytes with an overflow marker. pueue's completion callback (declared by
the CLI feature) appends the finish event. `job logs` and `job result` find
the artifacts by the launch reference in the task's own command line; there
is no job ledger. The launch input stays so `pueue restart` re-runs the same
command.

`pueue add` publishes the adding client's environment into world-readable
state, so every add goes through the adapter's scrubbed environment (`HOME`,
`PATH`, `XDG_RUNTIME_DIR`, `XDG_DATA_HOME`); the launch input carries the
real one. Add tasks by hand with `sinnix-pueue-add`, which scrubs the same
way.

Groups admit work, and every new task's wrapper enters a transient
`sinnixd-pueue-<pool>-<job>.scope` in the corresponding declarative
`sinnixd-pueue-<pool>.slice`: `agent:6 pytest:1 bulk:1 normal:5
interactive:4`. The pytest and bulk slices have fixed memory, swap, CPU, and
IO budgets; they do not choose capacity from instantaneous free RAM.
`sinnixd-backpressure.timer` pauses one group per minute while the host's
`full` IO or memory stall stays above threshold and resumes in reverse order
once clear; a paused task keeps its work.

## Lanes

A lane is a worktree with an agent in it and a PR that merges itself.

`lane start` compiles the prompt (`packets.py`): the bead and its open
dispatch-group members from `bd`, backend/model/effort from the bead's
`model_policy` metadata or the descriptor's `[packets.defaults]` (an explicit
flag wins), the atlas sheets matching the affected paths, and the worker
contract appended verbatim. It creates
`<workspace.root>/<repo>-feature-packet-<bead>` through `wt switch --create`
(the project's own hooks provision it), writes the prompt to
`.lane/prompt.md` (0600), and queues in group `agent`:

```text
<environment.command> sinnixd-queue-run <agent-launch.json>
systemd-run --user --scope --slice=sinnixd-pueue-agent.slice \
  --unit=sinnixd-pueue-agent-<job>.scope -- run_agent_prompt.sh --agent B --workdir W \
  --prompt-file W/.lane/prompt.md --last-file W/.lane/prompt.result.md \
  --model M --reasoning-effort E
```

The queue runner selects the pool slice for every new task, while the agent
scope keeps the descriptor's `workspace.agent_memory_max` (default 10G) as
the hard ceiling for one lane. The adapter (`agentRunner`) turns the prompt
into one backend invocation. Provisioning the worktree (dependencies, the
testmon seed copied from the primary checkout) is the project's `wt.toml`
hooks' job. The environment carries `BEADS_ACTOR=agent-<bead>` so an agent's
task writes are its own. Agent jobs cap at four hours.

The worker ends its lane with `lane publish` (the toolbelt) or
`agentctl lane publish <worktree>`: push, PR titled by the bead (`fix:` for
bugs, `feat:` for features, `chore:` otherwise, at most 72 characters), body
from `.lane/body.md`, auto-merge armed. Branch protection, the required verify
check and review decide when it lands. `lane sync` then closes the bead and
removes the worktree. Nothing dispatches on its own: `refill` and `lane start`
are explicit, and a declared `schedule` is the one autonomous driver a project
can choose.

## Descriptors

`.agentctl/project.toml`, schema 1:

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
root = "/realm/worktrees"
default_base = "origin/master"
agent_memory_max = "10G"

[packets]
branch_prefix = "feature/packet"

[packets.defaults]
backend = "codex"
model = "gpt-5.6-luna"
effort = "medium"

[operations.verify_all]
description = "Run the complete corpus"
exec = ["devtools", "verify", "--all"]
pool = "pytest"
result = "pytest"
timeout_seconds = 14400
checkout = "default"
schedule = "*-*-* 03:17:00"
```

An operation declares `description`, `exec` (argv, no shell), `pool` (a
pueue group), `result` (`exit`, `json`, `pytest`), `timeout_seconds` (1 to
28,800; default 3,600), `checkout` (`any`, or `default` for operations that
run only on the main checkout) and `schedule` (an `OnCalendar` expression).
`cache` is accepted and ignored. Any other operation field takes the project
out of service with the field named. The retired tables `[conflicts]`,
`[owner_adapters]` and the extra `[workspace]` fields are ignored.
`[environment]` declares `kind`, `command`, `inherit`, `unset`, `values` and
`require`; a required variable missing at launch fails the launch with its
name. `[workspace]` declares `root`, `default_base` and `agent_memory_max`
(a systemd size). `[packets]` declares `template`, `atlas_dir`,
`branch_prefix` and `[packets.defaults]` (`backend`, `model`, `effort`).

Descriptor changes take effect on the next call; timers follow on the next
`schedule apply` (every fifteen minutes and at login).

## Schedules

Each declared `schedule` is one transient user timer,
`sinnixd-schedule-<sha256(project:operation:expression)[:24]>.timer`, running
`agentctl job fire <project> <operation>`. `schedule apply` lists the live
timers, stops the ones no descriptor declares, and starts the missing ones;
a changed expression is a new unit. Daily or rarer timers are `Persistent`
(a missed firing catches up); sub-hourly ones are not.

The opt-in refill timer (`sinnix.services.sinnixd.refill = { enable = true;
project; limit; onCalendar; }`) runs `agentctl refill <project> --limit N`;
it is the only timer that starts lanes.

## Limits

| constant                                                     | origin                                                                   | stands for                                                       |
| ------------------------------------------------------------ | ------------------------------------------------------------------------ | ---------------------------------------------------------------- |
| `limits.DEFAULT_TIMEOUT_SECONDS` (3,600)                     | arbitrary bound                                                          | the job timeout when an operation declares none                  |
| `limits.MAX_AGENT_TIMEOUT_SECONDS` (14,400)                  | measurement (a 1h ceiling forced serial re-launch rounds on real lanes)  | the agent job timeout                                            |
| `limits.MAX_DECLARED_OPERATION_TIMEOUT_SECONDS` (28,800)     | arbitrary bound                                                          | the ceiling on a declared `timeout_seconds`                      |
| `limits.AGENT_MEMORY_MAX` (10G)                              | half of the job plane's MemoryHigh                                       | the hard ceiling of one agent's scope                            |
| `pueue.CALL_TIMEOUT_SECONDS` (60)                            | arbitrary bound (a minute distinguishes a wedged daemon from a slow one) | max time for one `pueue` round trip                              |
| `worktrunk.LIST_SCHEMA_VERSION` (2)                          | external tool's contract                                                 | the `wt list` JSON schema this module parses                     |
| `worktrunk.CALL_TIMEOUT_SECONDS` (60)                        | arbitrary bound (covers one cold forge round trip)                       | max time for one `wt` round trip                                 |
| `queue_run.MAX_LOG_BYTES` / `MAX_RESULT_BYTES` (64,000)      | arbitrary bound                                                          | caps on the captured log and typed result                        |
| `queue_run.TIMEOUT_EXIT_CODE` (124)                          | external tool's contract (`timeout(1)`)                                  | the wrapper enforced the declared timeout                        |
| `queue_run.REFUSED_EXIT_CODE` (125)                          | arbitrary bound                                                          | a pre-run refusal (vanished working directory, unreadable input) |
| `lanes.PUSH_TIMEOUT_SECONDS` (2,400)                         | arbitrary bound (the push runs the repository's pre-push gate)           | timeout for `git push` during publication                        |
| `lanes.GH_TIMEOUT_SECONDS` (60)                              | arbitrary bound                                                          | timeout for one `gh`/`git` call                                  |
| `packets.MAX_PROMPT_BYTES` (200,000)                         | arbitrary bound                                                          | cap on a compiled prompt                                         |
| `packets.MAX_SUBJECT_LENGTH` (72)                            | repository commit convention                                             | cap on a PR subject                                              |
| `backpressure.IO_FULL_FREEZE` (25%)                          | measurement (io full avg10 reached 76% under eight normal-pool jobs)     | the IO stall that freezes a group                                |
| `backpressure.MEMORY_FULL_FREEZE` (25%)                      | half of systemd-oomd's kill threshold                                    | the memory stall that freezes a group                            |
| `backpressure.RESUME_BELOW` (10%)                            | arbitrary bound                                                          | both stalls must fall below this before a group thaws            |
| `schedule.SYSTEMCTL_TIMEOUT_SECONDS` (10)                    | arbitrary bound                                                          | timeout for one `systemctl`/`systemd-run` call                   |
| `operator_view.MAX_READY_SHOWN` (8) / `MAX_FAILED_SHOWN` (6) | arbitrary bound                                                          | rows the screen shows                                            |

## Host wiring

`modules/services/sinnixd.nix` renders `/etc/sinnix/agentctl.json`
(`project_roots`, `agent_runner`, `event_spool`, `agentctl`), installs
`agentctl`, `wt`, `pueue` and `gh` as system packages, persists
`~/.local/state/sinnixd`, and declares the timers: `sinnixd-backpressure`
(every minute), `sinnixd-schedule` (every fifteen minutes, and two minutes
after login), and `sinnixd-refill` when the opt-in refill is enabled. pueued itself, its groups, its completion callback and the
`sinnixd-work.slice` coordinator placement, the pueue pool groups, and their
pool slices are declared by the CLI feature and runtime registry
(`modules/features/cli/core.nix`, `flake/data/runtime-defaults.nix`).

`nix build .#sinnixd` runs the package suite, which drives a private pueued
end to end for the adapter and fakes it for the launch and lane routes.
