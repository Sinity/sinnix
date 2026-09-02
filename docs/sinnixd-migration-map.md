# Sinnixd migration map

Sinnixd stops being a scheduler. pueue owns the queue, worktrunk owns
worktrees, GitHub's merge queue owns landing. What is left is the part no
external tool has: project descriptors, the bead-to-prompt compiler, the
result-artifact contract, and one readable operator view.

Baseline: 23 modules, 21,324 lines at `92f1141b`.

## Module fates

| Module                 |      Lines | Fate                                                    | Reason                                                                                                                                                                                                                                                                                               |
| ---------------------- | ---------: | ------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `jobs.py`              |      5,254 | replaced by `pueue add/status/log/wait/kill`; ~450 kept | Job store, systemd-run unit construction, admission, pool ledgers, leases, retry and reconciliation. pueue's `state.json` is the record; its groups are the pools; `pueue restart` is retry. What stays: build the argv from the descriptor, choose the group, mint the label, read `--json`.        |
| `workspaces.py`        |      1,814 | replaced by `wt switch/list/remove`; ~180 kept          | Worktree creation, its own relationship registry, checkpoints, stacking, restack, reap. worktrunk creates, provisions (`.config/wt.toml` hooks), lists with PR and CI joined, and removes. What stays: bead → branch name, and a reader for `wt list --format=json`.                                 |
| `cli.py`               |      1,664 | kept, ~450                                              | Shrinks with the verb surface below.                                                                                                                                                                                                                                                                 |
| `harvest.py`           |      1,559 | moved to Polylogue                                      | Receipt minting, scanner red flags, `HARVEST_OK`/`REBASE_CONFLICT`/`GATE_RED` are Polylogue's publication semantics. agentctl is project-agnostic; harvest is a declared operation like any other.                                                                                                   |
| `projects.py`          |      1,541 | kept, ~800                                              | The descriptor catalog is the thing agentctl uniquely owns. Drops the fields the scheduler needed and pueue does not read: `estimate_memory_bytes`, `exclusive_keys`, `scratch`, `supersede`, and the development-service lease contract (a dev server is a `pueue add` in the `interactive` group). |
| `service.py`           |      1,294 | kept, ~350                                              | The socket operation table follows the verb surface; every admission, checkpoint, publish, land, and sweep route goes with its module.                                                                                                                                                               |
| `reactor.py`           |      1,273 | kept, ~200                                              | Becomes the `campaign run` planner: read `campaign view` facts once, emit `pueue add` tasks, exit. No tick loop, no cooldowns, no backoff markers, no judgment dispatch, no `campaign-board.json`.                                                                                                   |
| `project_plans.py`     |        808 | kept, ~250                                              | The DAG stays a real product (an agent writes a plan in advance); the executor is `pueue add --after <ids>`. Node scheduling, recovery, and per-node state are pueue's.                                                                                                                              |
| `packets.py`           |        776 | kept, ~650                                              | Bead group → prompt compilation. No external tool does this.                                                                                                                                                                                                                                         |
| `lane_facts.py`        |        765 | kept, ~300                                              | `advance` stays as the pure fact → next-action function. The landed classifier (a test-rebase) is deleted for `wt list --format=json` `display.state == "integrated"`; job facts come from `pueue status --json`.                                                                                    |
| `contracts.py`         |        662 | kept, ~350                                              | Checkout revalidation and the `env -i` construction move into the command wrapper the pueue task runs. The transient-unit half goes.                                                                                                                                                                 |
| `campaign.py`          |        614 | kept, ~180                                              | Wave scheduling helpers; the launch half becomes `pueue add`.                                                                                                                                                                                                                                        |
| `publication_sweep.py` |        569 | deleted                                                 | GitHub merge queue plus `gh pr merge --auto --squash` converges open PRs. A required check gates; Codex findings are change requests. Nothing to converge locally.                                                                                                                                   |
| `operator_view.py`     |        531 | kept, ~450                                              | Re-pointed at `pueue status --json`, `wt list --format=json`, and `bd` JSON. The one surface the operator reads.                                                                                                                                                                                     |
| `delivery.py`          |        493 | deleted                                                 | Publish/land preconditions. `wt` proves the worktree state, the required check proves verification, branch protection proves review. Three authorities already own every precondition it recomputed.                                                                                                 |
| `runner.py`            |        374 | kept, ~200                                              | Becomes the pueue command wrapper: append the started event, run the declared argv, capture the result artifact.                                                                                                                                                                                     |
| `retrospective.py`     |        372 | deleted                                                 | A daily model-judgment proposer. The executor is dumb and mechanical; judgment agents are not part of it.                                                                                                                                                                                            |
| `integration.py`       |        300 | deleted                                                 | Batching lane branches into conflict-free units is what a merge queue does, with the repository's own checks behind it.                                                                                                                                                                              |
| `delivery_runner.py`   |        100 | deleted                                                 | CLI shim over `delivery.py`.                                                                                                                                                                                                                                                                         |
| `environment.py`       |         30 | kept, 30                                                | Environment construction for the wrapper.                                                                                                                                                                                                                                                            |
| `limits.py`            |         24 | kept, ~15                                               | Timeout ceilings. Every constant names its measured fact.                                                                                                                                                                                                                                            |
| `__init__.py`          |          6 | kept, 6                                                 |                                                                                                                                                                                                                                                                                                      |
| `api.py`               |        501 | kept, ~350                                              | Unix-socket transport; shrinks with the operation table.                                                                                                                                                                                                                                             |
| **Total**              | **21,324** |                                                         | **~4,700 kept, ~16,600 deleted or moved**                                                                                                                                                                                                                                                            |

The 2026-09-02 plan estimated ~3,200 surviving. The gap is `projects.py`
(descriptor parsing and its parameter grammar) and `packets.py` (prompt
compilation), which are the two things this codebase owns outright and which
no primitive replaces. Reaching 3,200 means simplifying the descriptor
parameter grammar, not deleting another subsystem.

## Target verb surface

Sixteen leaf verbs across ten groups. Everything pueue or worktrunk does
natively is absent, not wrapped.

| Verb                                                   | Maps to                                                                                        |
| ------------------------------------------------------ | ---------------------------------------------------------------------------------------------- |
| `agentctl status`                                      | `pueue status --json` group summary + `wt list --format=json` + `bd` counts                    |
| `agentctl project list \| get \| operations \| reload` | the descriptor catalog; no external equivalent                                                 |
| `agentctl workspace create <project> <bead>`           | `wt switch --create <branch> --no-cd -y --format json` in the primary checkout                 |
| `agentctl workspace list`                              | `wt list --format=json` (schema 2)                                                             |
| `agentctl workspace drop <id>`                         | `wt remove --reap -y` + `pueue remove` of that workspace's tasks                               |
| `agentctl job start <project> <operation>`             | `pueue add -g <pool> -l <project>:<operation>:<ref> --print-task-id -- <wrapper>`              |
| `agentctl job get \| list`                             | `pueue status --json`                                                                          |
| `agentctl job wait <id>`                               | `pueue wait <id>`                                                                              |
| `agentctl job logs <id>`                               | `pueue log --json <id>`                                                                        |
| `agentctl job result <id>`                             | the result artifact (`exit` / `json` / `pytest`); the one contract pueue has no notion of      |
| `agentctl job cancel <id>`                             | `pueue kill <id>`                                                                              |
| `agentctl plan submit \| get`                          | `pueue add --after <ids>` chained from the DAG                                                 |
| `agentctl packet launch <bead>`                        | compile the prompt, then `job start`                                                           |
| `agentctl campaign run`                                | plan a wave from `campaign view` facts into `pueue add`                                        |
| `agentctl campaign view \| log`                        | the operator screen and one lane's timeline from the event spool                               |
| `agentctl events tail`                                 | the spool (`kind: queue-task` finish events from pueue's callback, `started` from the wrapper) |
| `agentctl agent \| shell`                              | typed one-off dispatch through the same wrapper                                                |

Deleted verbs and their native replacements:

| Deleted                                                | Use                                                            |
| ------------------------------------------------------ | -------------------------------------------------------------- |
| `job admission`                                        | `pueue status`; group parallelism is the whole policy          |
| `job retry`                                            | `pueue restart <id>`                                           |
| `job fire`                                             | a `systemd --user` timer running `pueue add`                   |
| `workspace checkpoint \| restore`                      | Git                                                            |
| `workspace publish \| land \| finish \| review-status` | `gh pr create`, `gh pr merge --auto --squash`, the merge queue |
| `campaign integrate`                                   | the merge queue                                                |
| `lane publish \| authorize`                            | Polylogue's declared `harvest` operation                       |
| freeze / thaw                                          | `pueue pause -g <group>` and `pueue start -g <group>`          |

## Ordering

1. This map.
2. Worktrees through worktrunk (`workspaces.py`, `lane_facts.py`'s classifier).
3. Jobs through pueue (`jobs.py`, admission, `contracts.py`, `runner.py`).
4. The remainder: reactor to a planner, delete the publication half, docs and
   skills describe only the surviving surface.

Each step is reversible on its own commit.
