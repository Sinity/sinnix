# Coordinator contract

A fresh session takes over running lanes from this document plus the live
state below. It holds no campaign state itself; `agentctl` holds none either.

## Where state lives

- **Lanes and jobs**: `agentctl view <project>` is the screen (`--json view`
  is the same payload); `agentctl job get|logs|result <id>` is one job. Job
  ids are pueue task ids.
- **Worktrees**: `wt list` in the project, or the lanes section of the view.
- **Task authority**: external Beads per project. `bd` resolves its database
  from the working directory, so mind your cwd.
- **Events**: one persistent watch on `agentctl events tail --follow
--project <p>` (spool: `/realm/state/agentctl/events.jsonl`): every task's
  start and finish, and backpressure freezes, in local time.
- **History**: per-project memory (`~/.claude/projects/<p>/memory/MEMORY.md`)
  and the repo's `docs/atlas/`.

## Who drives

The operator or the coordinating agent takes every step by hand; `agentctl`
dispatches what it is told and reports. A lane's "next" column on the view
is a description of its state, not something the CLI will do.

## Capability map

Look for the verb before writing any procedure: `agentctl <verb> --help`.

| Need                                       | Verb                                                                |
| ------------------------------------------ | ------------------------------------------------------------------- |
| see the lanes, queue and ready work        | `agentctl view <p>`                                                 |
| watch what happens                         | `agentctl events tail --follow --project <p>`                       |
| start lanes for ready beads                | `agentctl refill <p> --limit N [--dry-run]`                         |
| start one lane                             | `agentctl lane start <p> <bead> [--backend B --model M --effort E]` |
| re-queue an agent into an existing lane    | `agentctl lane rebase <p> <bead> [--model M --effort E]`            |
| publish a finished lane                    | `agentctl lane publish <worktree>` (or the worker's `lane publish`) |
| close merged beads, remove their worktrees | `agentctl lane sync <p>`                                            |
| run a declared operation                   | `agentctl job start <p> <operation> [--workspace <path>] [--wait]`  |
| read a job                                 | `agentctl job get\|logs\|result <id>`                               |
| stop a job                                 | `agentctl job cancel <id>`                                          |
| run it again                               | `agentctl job retry <id>`                                           |

Task mutations go through `bd` directly; see [[task-backend]].

A missing capability is a bead against the substrate. Declared operations are
the extension point: `.agentctl/project.toml` in the repo, live on the next
call.

Every repository lands the same way: `lane publish` verifies at the exact
head, pushes, opens the PR and arms auto-merge; GitHub merges. What it waits
for is per-repository: polylogue's `master` requires a status check, sinnix's
carries no protection and merges at once. Nothing lands by hand.

## The operating loop

1. `agentctl lane sync <p>`: merged lanes close their beads and lose their
   worktrees. Excisions land as whole merges.
2. Run the corpus once at the master boundary:
   `agentctl job start polylogue verify_all`. Never a corpus run per lane.
3. `agentctl view <p>`; decide; `refill` or `lane start` the next wave.

**Stages on the view** and what follows mechanically: `lane queued/running`
→ wait; `unpublished` (agent done, no PR) → `lane publish`; `pr open` with
auto-merge unarmed → publication refused, so read its reason, fix in the lane
and `lane publish` again; `auto-merge armed` / `checks running` → wait;
`checks failing` or `changes requested` → fix in the lane, push;
`conflicting` → `lane rebase`;
`lane failed/timed-out` → `job logs`, then `lane rebase`; `merged` →
`lane sync`.

**Refill** skips epics, beads with a worktree, and beads with an open PR; it
dedupes nothing else. `--dry-run` lists the candidates.

**Verification**: lanes run `verify_affected`; the corpus runs once at the
master boundary as `verify_all`. `devtools verify` selects from the
checkout's one testmon datafile and writes back; `--all` runs everything; a
corrupt or foreign datafile stops with `graph_unusable` (delete it and
rerun). Wrongly skipped tests are acceptable, a refusal is not. A package or
interpreter change is a reported full run. Read
`.cache/verify/runs/<id>/run.json` receipts.

**Fix loops belong in lanes.** Lanes exit rebased on current master with the
quick gate green. A PR failing checks goes back to its lane (`lane rebase`
with the finding in the bead note), never fixed at the coordinator's desk.

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
  pattern, or required context get `dispatch_group=<leader-id>`; one lane
  executes the group and each bead keeps its own verifiable close.
- **Bead type names the PR subject prefix**: `bug` → `fix:`, `feature` →
  `feat:`, anything else → `chore:`.
