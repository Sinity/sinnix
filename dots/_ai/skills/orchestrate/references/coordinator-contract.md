# Coordinator contract

A fresh session takes over running batches from this document plus the live
state below. It holds no campaign state itself; `agentctl` holds none either.

## Where state lives

- **Runs and jobs**: `agentctl view <p>` is the screen (`--json` is the same
  payload); `agentctl batch status <run>` is one run; `agentctl job
get|logs|result <id>` is one job. Job ids are pueue task ids; a run id is
  `<project>-<stamp>-<8 hex>` and its suffix is accepted everywhere.
- **Manifests**: `~/.local/state/agentctl/runs/<run>.json` — inputs, worker
  results, landing state, acceptance record.
- **Worktrees**: `wt list` in the project, or the manifest's worker rows.
- **Task authority**: external Beads per project. `bd` resolves its database
  from the working directory, so mind your cwd.
- **Events**: one persistent watch on `agentctl events tail --follow
--project <p>` (spool: `/realm/state/agentctl/events.jsonl`): every task's
  start and finish, and backpressure freezes, in local time.
- **Project rules and history**: read the repository's `CLAUDE.md` and its
  per-project memory index (`~/.claude/projects/<p>/memory/MEMORY.md`) before
  dispatch or integration; the project's atlas directory, when the
  descriptor declares one, is product orientation.

## Who drives

The operator or the coordinating agent starts every batch; `agentctl` does
what it is told and reports. A started batch lands itself: the landing task
is queued behind its workers and runs when they all succeed. A run's "next"
on the view describes its state.

## Capability map

Look for the verb before writing any procedure: `agentctl <verb> --help`.

| Need                                          | Verb                                                                                  |
| --------------------------------------------- | ------------------------------------------------------------------------------------- |
| see the runs, queue and ready work            | `agentctl view <p>`                                                                   |
| watch what happens                            | `agentctl events tail --follow --project <p>`                                         |
| start a batch of workers                      | `agentctl batch start <p> <bead>… [--worker a,b]… [--backend B --model M --effort E]` |
| start a batch that Claude subagents will work | `agentctl batch start <p> <bead>… --workers external`                                 |
| file an external worker's result              | `agentctl batch result <run> <worker> <result.json>`                                  |
| land a run by hand, or again after a failure  | `agentctl batch land <run>`                                                           |
| land a hand fix made on the integration tree  | `agentctl batch land <run> --keep-integration`                                        |
| release a run that will not land              | `agentctl batch abandon <run> [--reason R]`                                           |
| one run, every run                            | `agentctl batch status <run>`, `agentctl batch list <p>`                              |
| re-queue an agent into a worker's worktree    | `agentctl batch resume <run> --worker <w> [--backend B --model M --effort E]`         |
| run a declared operation                      | `agentctl job start <p> <operation> [--workspace <path>] [--wait]`                    |
| read a job                                    | `agentctl job get\|logs\|result <id>`                                                 |
| stop a job                                    | `agentctl job cancel <id>`                                                            |
| run it again                                  | `agentctl job retry <id>`                                                             |
| remove a finished job's artifacts             | `agentctl job clean <id>`                                                             |
| the descriptors                               | `agentctl project list\|get\|operations`                                              |
| timers, pool pressure                         | `agentctl schedule apply`, `agentctl backpressure tick`                               |

Task mutations go through `bd` directly; see [[task-backend]]. `batch start`
claims the members and `batch land` closes them from the acceptance record.

A missing capability is a bead against the substrate. Declared operations are
the extension point: `.agentctl/project.toml` in the repo, live on the next
call.

Publication policy is the descriptor's `[workspace].publish`: `pr` pushes the
candidate as one PR (titled with the leader bead's subject) and
squash-merges it on exactly that head after the required checks and the
reviewer verdict, then deletes the remote integration branch; the beads
close on the merge commit. `master` fast-forwards the default branch to the
candidate. Hosted review comments are handled as `docs/agentctl.md` states.

## The operating loop

1. Inventory: `agentctl view <p>`, open manifests, `wt list`, `bd ready`,
   the project's rules.
2. Start one coherent set as a batch, two to four workers: `agentctl batch
start <p> <bead>…`. Each seed bead's open dispatch group is one worker;
   `--worker a,b` names one explicitly.
3. Wait for the `<p>:land:<run>` finished event on the watch; do not poll.
4. `agentctl batch status <run>`: `landed` with an acceptance record, or a
   named failure.
5. Next set.

For Claude-subagent workers: `batch start … --workers external`, run one
`lane` subagent per worker in the worktree the manifest names, file each
result with `batch result` (the last one enqueues the landing task), then
step 3.

**Stages on the view** and what follows mechanically:

| Stage                       | Next                                                                        |
| --------------------------- | --------------------------------------------------------------------------- |
| `working`, `landing`        | wait                                                                        |
| `stashed`                   | `batch result` per external worker; the landing task then runs              |
| `awaiting workers`          | a failed worker: `batch resume --worker`; missing: `batch result`           |
| `ready to land`             | `batch land`                                                                |
| `landing dependency-failed` | `batch resume --worker <w>` for the failed worker; it re-queues the landing |
| `failed: <code>`            | `job logs <landing task>`, then `batch land` again                          |
| `landing <phase>`           | same                                                                        |
| `unprepared`                | `batch start` again with the same members                                   |
| `landed`, `abandoned`       | nothing                                                                     |

**Verification**: workers run the descriptor's focused operation; the landing
task runs the `candidate` profile once on the integrated tree (a hosted check
where the descriptor names one); the `corpus` operation runs once at the
master boundary, as a declared operation or its schedule. A selected green
proves the selected scope only. Read `.cache/verify/runs/<id>/run.json`
receipts where the project writes them.

**Fix loops preserve batch ownership.** A finding isolated to one worker's
change goes back to that worker (`batch resume`). Integration conflicts and
cross-worker findings are fixed on the integration branch by the integration
agent the landing task queues, or by hand in the integration worktree
followed by `batch land --keep-integration`. A failed review's verdict is in
the manifest's `landing.review_verdict`. A run that will not land is
released with `batch abandon`; it keeps any worktree holding unpreserved
work and names it in the residual.

**Substrate defects** are next work items: file instances in the owning
project's Beads with reproduction evidence. Deploy sinnix through the devshell
`switch` wrapper; running pueue tasks survive it.

## Cost discipline

Every wake is a full-context turn. Batch what machinery can batch, write future
receipts at decision time, and spend your own tokens on adversarial review and
frontier strategy. File product defects freely, process beads sparingly.

## Packet and bead authoring

- **One current-state note per bead.** Consolidate on contact; a superseded
  amendment reads as current to a fresh-context worker.
- **Readiness lives only in typed dependency edges**, where the validator owns
  it.
- **Spec weight tracks work size.** Heavy acceptance criteria mark big work;
  small fixes stay light.
- **Acceptance criteria must survive their neighbors.** Name the invariant and
  its owning surface; a criterion bound to a file another bead deletes
  manufactures false reds.
- **Name a deletion target in the source tree**, never at its installed path.
- **Co-execution via dispatch groups.** Beads sharing a file, area, fix
  pattern, or required context get `dispatch_group=<leader-id>`; one worker
  executes the group and each bead keeps its own verifiable close.
- **Bead type names the PR subject prefix**: `bug` → `fix:`, `feature` →
  `feat:`, anything else → `chore:`.
