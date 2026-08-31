# Coordinator contract

A fresh session takes over a running campaign from this document plus the live
state below. It says where state lives and what the loops are; it holds no
campaign state itself.

## Where state lives

- **Fleet and jobs**: `agentctl fleet`, `agentctl evidence <id>`,
  `agentctl job result <id>`. Job ids may be abbreviated to any unambiguous
  prefix. `--plain` prints the payload as text.
- **Workspaces**: `agentctl workspace list`.
- **Task authority**: external Beads per project. `bd` resolves its database
  from the working directory, so mind your cwd.
- **Events**: one persistent watch on `agentctl events tail --follow` (spool:
  `/realm/state/agentctl/events.jsonl`), filtered to judgment signals only:
  failures/timeouts, harvest terminals, and review/needs-merge events. Lane
  successes need no coordinator wake — the reactor enqueues the harvest, the
  harvest watches its own PR to merge and closes the bead from its receipt.
- **History**: per-project memory (`~/.claude/projects/<p>/memory/MEMORY.md`)
  and the repo's `docs/atlas/`.

## Capability map

Look for the verb before writing any procedure: `agentctl <noun> --help`.

| Need                                     | Verb                                                                                          |
| ---------------------------------------- | --------------------------------------------------------------------------------------------- |
| schedule a dispatch wave                 | `agentctl campaign run --project <p> [--bead ID …] [--dry-run]`                               |
| dispatch one bead                        | `agentctl packet launch <bead> --project <p>`                                                 |
| publish a finished lane                  | `agentctl lane publish <ws>` (mints receipt, routes, authorizes, arms auto-merge)             |
| continue an interrupted lane             | `agentctl agent launch --checkout <worktree-id> --prompt-file …` (no `lane resume` verb yet)  |
| open a PR outside the harvest flow       | `agentctl workspace publish --job <j> --title T [--body F] [--wait]`                          |
| land / integrate a workspace             | `agentctl workspace land --job <j>`                                                           |
| dispose after a GitHub merge             | `agentctl workspace finish-merged`                                                            |
| dispose when content is already in a ref | `agentctl workspace finish-integrated --target <ref>` (tree-contribution check; squash-proof) |
| adopt an orphan worktree                 | `agentctl workspace adopt <project> <checkout> <name>`                                        |
| protect work before risky integration    | `agentctl workspace checkpoint` / `restore` / `recover`                                       |
| stacked branches                         | `agentctl workspace stack` / `restack`                                                        |
| review state of a workspace              | `agentctl workspace review-status`                                                            |
| complete a packet                        | `agentctl packet finalize --verification-job <j> --packet-job <j>`                            |
| packet state                             | `agentctl packet status`                                                                      |
| task-backend mutations                   | `agentctl task create/claim/complete/note/update/relate/reconcile/snapshot`                   |
| wait on work                             | `agentctl job wait`, `agentctl agent wait`, `agentctl plan wait`                              |
| all evidence for a job or workspace      | `agentctl evidence <id>`                                                                      |

Publication policy is per-repository: polylogue lands via `lane publish`
(PR + auto-merge); **sinnix publishes from `master` directly** (its CLAUDE.md)
— verify at exact head, plain merge or fast-forward, push; no PRs, no
`workspace publish`.

A missing capability is a bead against the substrate. Declared operations are
the extension point: `.agentctl/project.toml` in the repo, live after a daemon
restart.

## The loops

**Dispatch**: `agentctl campaign run --project <p>` resolves the ready set,
dedupes dispatch groups, serializes on conflict keys, and skips beads whose
workspace is already live. `--dry-run` shows the schedule; `--limit` bounds how
many lanes the wave launches, and everything it defers is reported with a
reason. For a single bead, `agentctl packet launch`. Both compile the worker
contract into the prompt.

**Harvest** is a declared two-phase operation. The review phase is read-mostly
and produces a receipt; publication is reachable only by quoting that receipt
back, so nothing publishes unreviewed.

1. `agentctl lane publish <ws> [--close]` runs the whole pass: mints the
   receipt (lane trailer, diffstat, red-flag scan, full-diff ref), routes it,
   and — when the route clears — authorizes, pushes, arms auto-merge, and
   releases. `agentctl job result <harvest-job>` reads the receipt. The verb
   enqueues a harvest job and may report RESULT_INVALID before that job runs;
   confirm via `job list`, do not re-invoke.
2. Routing: docs/tests-only with a clean scan is reactor auto-publish, no
   model at all. An ordinary production diff with a clean scan routes to a
   cross-family review lane — the coordinator dispatches that reviewer
   (nothing dispatches it automatically) with the packet, trailer, and scan;
   the reviewer identity lands in the publication body. Migrations, gate or
   baseline edits, security and excision work, large deletions, legacy shims,
   and uncleared flags route to the coordinator.
3. Judge a coordinator-routed receipt. No flags plus a small diff →
   stat-level skim. Flags → read the full diff. The flags mark deleted
   production lines, inverted or removed assertions, new xfail or skip, gate,
   baseline, migration or sidecar edits, and deleted test files. A lane that
   papered over a real defect is rejected with the reason recorded on the
   bead. Rewrite `.lane/title` and `.lane/body.md` at decision time,
   immediately before re-running `lane publish` — harvest restores `.lane/`
   from lane artifacts, so earlier edits are clobbered.
4. A receipt binds workspace HEAD at minting; a failed authorize invalidates
   it — re-mint before retrying. The operation holds the repo lock only
   across push and PR creation, so review phases run in parallel.
5. Dispose after the content check: `agentctl workspace finish-integrated
--target <ref>` is squash-proof; `finish-merged` handles the merged case;
   `lane gc --apply` owns bulk disposal of integrated units.

**Launch wedges**: packet launch advances one step per attempt (worktree →
record → job) and reports a step failure as a redacted `OWNER_UNAVAILABLE`.
Retry about three times, spaced. A leftover worktree with no workspace record
is adopted: `agentctl workspace adopt <project> <checkout> <name>`.

**Refill** (keeper tick): read the fleet. Lanes at target with nothing
review-ready → say so and stop. Otherwise harvest what finished and launch a
wave sized to free memory — lanes peak near a gigabyte each under verification.

**Verification economics**: lanes run selected verification; the full corpus
runs at master boundaries (`agentctl job start polylogue verify_all`). Corpus
runs abort at the first failed step, and later steps (serial, storage-scale)
can hide reds behind an early one — enumerate locally with
`-m "load_sensitive and not storage_scale"` and `-m storage_scale` when
hunting. Read `.cache/verify/runs/<id>/run.json` receipts.

**Fix loops belong in lanes.** Lanes exit rebased on current master with the
quick gate green. A returning branch failing gates on trivia (annotations,
format) may be patched at harvest; one failing on semantics goes back as a
completion lane on the same branch, in the same worktree.

**Substrate defects** are next work items: file instances in the owning
project's Beads with reproduction evidence. Sinnix orchestration work is top of
queue. A client timeout surfaces as "sinnixd is unavailable" — check
`CONTROL_OPERATION_RESPONSE_TIMEOUT_SECONDS` before diagnosing the daemon.
Deploy sinnixd through the devshell `switch` wrapper while no lane is
mid-launch; jobs survive daemon restarts.

## Cost discipline

Every wake is a full-context turn. Batch what machinery can batch, write future
receipts at decision time, and spend your own tokens where judgment is
irreplaceable: adversarial review and frontier strategy. Beads about the
campaign's own machinery grow faster than they close — file product defects
freely, process beads sparingly.

## Packet and bead authoring

- **One current-state note per bead.** Consolidate on contact; a fresh-context
  worker acts on what it reads, and a superseded amendment reads as current.
- **Readiness lives only in typed dependency edges**, where the validator owns
  it. Free-form "blocked-on-X" metadata goes stale the day the graph changes.
- **Spec weight tracks work size, not completion speed.** Heavy acceptance
  criteria mark big work; small fixes stay light.
- **Acceptance criteria must survive their neighbors.** Name the invariant and
  its owning surface — a criterion bound to a file another bead deletes
  manufactures false reds.
- **Name a deletion target in the source tree**, never at its installed path;
  a worker will act on the path it reads.
- **Co-execution via dispatch groups.** Beads sharing a file, area, fix
  pattern, or required context get `dispatch_group=<leader-id>`; one lane
  executes the group and each bead keeps its own verifiable close.
