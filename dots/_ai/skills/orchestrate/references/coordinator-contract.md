# Coordinator contract

A fresh session takes over a running campaign from this document plus the live
state below. It holds no campaign state itself.

## Where state lives

- **Lanes and jobs**: `agentctl campaign view --project <p>` is the screen;
  `campaign view --json` is the same payload; `campaign log --project <p>
--workspace <ws>` is one lane's timeline; `agentctl job result <id>` is one
  job's outcome. Job ids may be abbreviated to any unambiguous prefix.
  `--plain` prints the payload as text.
- **Workspaces**: `agentctl workspace list`.
- **Task authority**: external Beads per project. `bd` resolves its database
  from the working directory, so mind your cwd.
- **Events**: one persistent watch on `agentctl events tail --follow` (spool:
  `/realm/state/agentctl/events.jsonl`), filtered to judgment signals:
  failures, timeouts, harvest terminals, and review or needs-merge events.
- **History**: per-project memory (`~/.claude/projects/<p>/memory/MEMORY.md`)
  and the repo's `docs/atlas/`.

## Who drives

The reactor is stopped after every deploy:

```
systemctl --user stop sinnixd-reactor
```

Refill is opt-in. With the reactor stopped, the operator or the coordinating
agent takes every step by hand: `campaign view` to see what needs attention,
`campaign run` or `packet launch` to dispatch, the declared `harvest`
operation to publish, `campaign log` to explain one lane.

## Capability map

Look for the verb before writing any procedure: `agentctl <verb> --help`.

| Need                                      | Verb                                                                                                            |
| ----------------------------------------- | --------------------------------------------------------------------------------------------------------------- |
| see the campaign                          | `agentctl campaign view --project <p> [--json]`                                                                 |
| explain one lane                          | `agentctl campaign log --project <p> --workspace <ws>`                                                          |
| schedule a dispatch wave                  | `agentctl campaign run --project <p> [--limit N] [--bead ID …] [--dry-run]`                                     |
| dispatch one bead                         | `agentctl packet launch <bead> --project <p>`                                                                   |
| group unintegrated lanes into batches     | `agentctl campaign integrate --project <p> [--assemble N --name B]`                                             |
| publish a finished lane                   | `agentctl lane publish <ws> [--close]`                                                                          |
| record the operator's decision at a head  | `agentctl lane authorize <ws> [--reason R]`                                                                     |
| continue an interrupted lane              | `agentctl agent launch --project <p> --checkout <worktree-id> --prompt-file F --backend B --model M --effort E` |
| open a PR outside the harvest flow        | `agentctl workspace publish <ws> --job <verify-job> --title T [--body F] [--wait]`                              |
| land a workspace                          | `agentctl workspace land <ws> --job <verify-job>`                                                               |
| dispose after a GitHub merge              | `agentctl workspace finish <ws>`                                                                                |
| delete a workspace and everything it owns | `agentctl workspace drop <ws> [--target <ref>] [--force]`                                                       |
| protect work before risky integration     | `agentctl workspace checkpoint <ws>` / `restore <ws> <cp> [--recreate]`                                         |
| review state of a workspace               | `agentctl workspace review-status <ws>`                                                                         |
| run a declared operation                  | `agentctl job start <p> <operation> [--workspace <ws>] [--wait]`                                                |
| see what blocks the queue                 | `agentctl job admission [--project <p>]`                                                                        |
| wait on work                              | `agentctl job wait <id>`, `agentctl plan wait <id>`                                                             |

Task mutations go through `bd` directly; see [[task-backend]].

A missing capability is a bead against the substrate. Declared operations are
the extension point: `.agentctl/project.toml` in the repo, live after
`agentctl project reload`.

Publication policy is per-repository: polylogue lands via `lane publish`
(PR + auto-merge); **sinnix publishes from `master` directly** — verify at
exact head, merge or fast-forward, push.

## The operating loop

1. Merge everything in progress. Excisions land as whole merges.
2. Run the corpus once at the master boundary:
   `agentctl job start polylogue verify_all`. Never a corpus run per lane.
3. Read the result, decide, dispatch the next wave.

**Dispatch**: `campaign run` resolves the ready set, dedupes dispatch groups,
serializes on conflict keys, and skips beads whose workspace is already live.
`--dry-run` shows the schedule; `--limit` bounds the wave; everything deferred
is reported with a reason.

**Harvest** is a declared two-phase operation. The review phase is read-mostly
and produces a receipt; publication is reachable only by quoting that receipt
back, so nothing publishes unreviewed.

1. `agentctl lane publish <ws> [--close]` runs the whole pass: mints the
   receipt (lane trailer, diffstat, red-flag scan, full-diff ref), routes it,
   and — when the route clears — authorizes, pushes, arms auto-merge, and
   releases. `agentctl job result <harvest-job>` reads the receipt.
2. **Publication needs test evidence at the exact head.** The harvest refuses
   with `NO_TEST_EVIDENCE` unless it is given a succeeded `verify_affected`
   job for the current head (`affected_job`) or the operator has recorded an
   authorization for that head (`agentctl lane authorize`, which writes
   `.lane/authorization.json`). The publication sweep reports the same state as
   the verdict `no-test-evidence` and merges nothing on it.
3. Routing: docs- or tests-only with a clean scan publishes without a reader.
   An ordinary production diff with a clean scan routes to a cross-family
   review lane the coordinator dispatches. Migrations, gate or baseline edits,
   security and excision work, large deletions, legacy shims, and uncleared
   flags route to the coordinator.
4. Judge a coordinator-routed receipt: no flags plus a small diff → stat-level
   skim; flags → read the full diff. Flags mark deleted production lines,
   inverted or removed assertions, new xfail or skip, gate, baseline, migration
   or sidecar edits, and deleted test files. Rewrite `.lane/title` and
   `.lane/body.md` immediately before re-running `lane publish` — harvest
   restores `.lane/` from lane artifacts, so earlier edits are clobbered.
5. A receipt binds workspace HEAD at minting; a failed authorize invalidates
   it — re-mint before retrying.
6. Drop after the content check: `workspace drop <ws> --target <ref>` for a
   squash-merged branch, `workspace finish` for the merged case. Both delete
   the lane's job records and artifacts with it.

**Launch wedges**: `packet launch` advances one step per attempt (worktree →
record → job) and reports a step failure as a redacted `OWNER_UNAVAILABLE`.
Retry about three times, spaced. A leftover worktree with no workspace record
is not a workspace: remove it with `git worktree remove` and relaunch.

**Verification**: lanes run `verify_affected`; the corpus runs once at the
master boundary as `verify_all`. `devtools verify` selects from the checkout's
one testmon datafile and writes back; `--all` runs everything; a corrupt or
foreign datafile stops with `graph_unusable` (delete it and rerun). Wrongly
skipped tests are acceptable, a refusal is not. A package or interpreter change
is a reported full run. Read `.cache/verify/runs/<id>/run.json` receipts.

**Fix loops belong in lanes.** Lanes exit rebased on current master with the
quick gate green. A returning branch failing gates on trivia may be patched at
harvest; one failing on semantics goes back as a completion lane on the same
branch, in the same worktree.

**Substrate defects** are next work items: file instances in the owning
project's Beads with reproduction evidence. Deploy sinnixd through the devshell
`switch` wrapper while no lane is mid-launch; jobs survive daemon restarts, and
the reactor stays stopped afterwards.

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
