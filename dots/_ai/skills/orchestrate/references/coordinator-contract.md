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
- **Project rules and history**: read the repository's `CLAUDE.md` and its
  per-project memory index (`~/.claude/projects/<p>/memory/MEMORY.md`) before
  dispatch or integration; use `docs/atlas/` for product orientation.

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
| publish an integrated product batch        | `agentctl lane publish <integration-worktree>`                     |
| close merged beads, remove their worktrees | `agentctl lane sync <p>`                                            |
| run a declared operation                   | `agentctl job start <p> <operation> [--workspace <path>] [--wait]`  |
| read a job                                 | `agentctl job get\|logs\|result <id>`                               |
| stop a job                                 | `agentctl job cancel <id>`                                          |
| run it again                               | `agentctl job retry <id>`                                           |

Task mutations go through `bd` directly; see [[task-backend]].

A missing capability is a bead against the substrate. Declared operations are
the extension point: `.agentctl/project.toml` in the repo, live on the next
call.

Publication policy is per-repository. Polylogue gets one PR per coherent
integration batch. Sinnix publishes from `master` directly after one combined
review and verification pass. Candidate lanes do not publish themselves.

## The operating loop

1. Inventory live lanes, worktrees, Beads, and project rules. Integrate
   compatible candidate commits into one coherent batch.
2. Review and verify that combined diff, then publish according to the
   repository policy. Close Beads only after their commits are integrated.
3. Run the corpus once at the master boundary:
   `agentctl job start polylogue verify_all`. Never a corpus run per lane.
4. Remove integrated worktrees, reconcile the task state, then dispatch the
   next ready ownership groups.

**Stages on the view** and what follows mechanically: `lane queued/running`
→ wait; `unpublished` → review and integrate its candidate commit; `pr open` →
`gh pr merge --auto --squash`;
`auto-merge armed` / `checks running` → wait; `checks failing` or `changes
requested` → fix in the lane, push; `conflicting` → `lane rebase`;
`lane failed/timed-out` → `job logs`, then `lane rebase`; `merged` →
`lane sync`.

**Refill** skips epics, beads with a worktree, and beads with an open PR; it
dedupes nothing else. `--dry-run` lists the candidates.

**Verification**: lanes run focused tests and `verify_quick`; the integrated
batch runs affected verification when declared; the corpus runs once at the
master boundary as `verify_all`. `devtools verify` selects from the
checkout's one testmon datafile and writes back; `--all` runs everything; a
corrupt or foreign datafile stops with `graph_unusable` (delete it and
rerun). Wrongly skipped tests are acceptable, a refusal is not. A package or
interpreter change is a reported full run. Read
`.cache/verify/runs/<id>/run.json` receipts.

**Fix loops preserve batch ownership.** A finding isolated to one candidate
goes back to that lane. Integration conflicts and cross-candidate findings are
fixed on the integration branch so several workers do not rewrite the same
batch.

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
