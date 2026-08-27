# Coordinator contract (campaign overseer protocol)

A fresh session must be able to take over a running campaign from THIS
document plus the live state below. Nothing here duplicates live state — it
tells you where state lives and what the loops are.

## Where state lives (read these, never reconstruct from context)

- **Board**: `/realm/tmp/work/campaign-board.json` — lanes → PRs → beads →
  review state. `board` prints it; `board sync` refreshes from
  fleet/GitHub/worktrees. Maintained by the watchers; trust it over memory.
- **Dispatch plan**: `/realm/tmp/work/dispatch-plan.json` — the scheduled
  planner's ordered ready-set, orbit annotations, conflict serialization, and
  judgment-gate flags. `board plan` prints it; refill executes this artifact
  through the typed campaign runner rather than re-deriving strategy in the
  coordinator session.
- **Task authority**: external Beads per project (`bd` from the repo cwd —
  MIND YOUR CWD: `bd` resolves the DB from the working directory).
- **Fleet truth**: `actl jobs` / `actl running` / `actl result <job>` /
  `actl ws [pat]` (unwraps agentctl envelopes).
- **Events**: one persistent Monitor on `/realm/state/agentctl/events.jsonl`
  filtered to lanes + polylogue + merge watches + failures (drop successful
  non-polylogue declared-operations — scheduled noise). The harvest operation
  watches its own PR to merge and closes the bead from the receipt.
- **History**: per-project memory (`~/.claude/projects/<p>/memory/MEMORY.md`)
  and the repo's `docs/atlas/`.

## Capability map — READ BEFORE WRITING ANY PROCEDURE

A coordinator that does not know a verb exists will hand-roll a worse copy of
it. Before scripting anything, look for the verb: `agentctl <noun> --help`.

| Need                                     | Verb (NOT a hand-rolled equivalent)                                                           |
| ---------------------------------------- | --------------------------------------------------------------------------------------------- |
| schedule a whole dispatch wave           | `agentctl campaign run --project <p> [--limit N] [--dry-run]`                                  |
| dispatch one bead                        | `agentctl packet launch <bead> --project <p>`                                                  |
| review a finished lane                   | `agentctl job start <p> harvest --workspace <ws>` (receipt; read-mostly)                       |
| publish a reviewed lane                  | the same operation with `authorize` + `receipt_ref` (opens the PR, closes the bead)            |
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
| wait on work instead of polling          | `agentctl job wait`, `agentctl agent wait`, `agentctl plan wait`                              |
| all evidence for a job or workspace      | `agentctl evidence <id>`                                                                      |

A capability that genuinely does not exist is a bead against the substrate, not
a reason to grow a shell pile. Declared operations are the extension point:
`.agentctl/project.toml` in the repo, live after a daemon restart. If you find
yourself writing git plumbing, gh calls, or bead mutations by hand, stop and
check this table first.

## The loops

**Dispatch**: `agentctl campaign run --project <p> [--limit N]` schedules a
whole wave — it resolves the ready set, dedupes dispatch groups, serializes on
conflict keys, and skips beads whose workspace is already live. `--dry-run`
shows the schedule without launching. For a single bead,
`agentctl packet launch <bead> --project <p>`. Both compile the worker
contract into the prompt; neither needs the ready set hand-diffed against
`/realm/worktrees`.

**Harvest** (lane success event) is a declared two-phase operation. The review
phase is read-mostly and produces a receipt; publication is reachable only by
quoting that receipt back, so nothing publishes unreviewed.

1. `agentctl job start <p> harvest --workspace <ws>` → a receipt carrying the
   lane trailer, the diffstat, the red-flag scan, and a ref to the full diff.
   `agentctl job result <job>` reads it.
2. Judge the receipt. No flags plus a small diff → stat-level skim. Flags → read
   the full diff. They mark what has actually caught dishonest lanes: deleted
   production lines, inverted or removed assertions, new xfail/skip, gate,
   baseline, migration or sidecar edits, deleted test files. A lane that papered
   over a real defect is rejected with the reason recorded on the bead, never
   merged to keep moving.
3. Write the PR title, body, and bead close-reason to files at decision time,
   then authorize:
   `agentctl job start <p> harvest --workspace <ws> --parameters-json
   '{"authorize":true,"receipt_ref":"<ref>","title_file":"…","body_file":"…",
   "bead_id":"…","close_reason_file":"…"}'`. Omit the bead parameters when the
   lane delivered a slice and the bead stays open. The operation holds the repo
   lock only across push and PR creation, so review phases run in parallel.
4. Dispose only after the content check: `agentctl workspace finish-integrated
   --target <ref>` is squash-proof; `finish-merged` handles the merged case.

**Launch wedges**: packet launch advances one step per attempt (worktree →
record → job) and reports a step failure as a redacted `OWNER_UNAVAILABLE`.
Retry about three times, spaced. A leftover worktree with no workspace record
is adopted, not deleted: `agentctl workspace adopt <project> <checkout> <name>`.

**Refill** (keeper tick): `board` first — if lanes ≥ target and nothing
review-ready, say so and stop. Otherwise consume the latest dispatch plan,
execute its ordered ready-set through the typed campaign runner, and hold
judgment-gated entries for the review desk. The live coordinator handles
review escalations and operator conversation; frontier curation and dispatch
ordering are scheduled planner responsibilities.

**Verification economics**: lanes run selected/focused only; the full corpus
runs at master boundaries (`agentctl job start polylogue verify_all`). Corpus
runs ABORT at the first failed step — later steps (serial, storage-scale) can
hide reds; enumerate locally with `-m "load_sensitive and not storage_scale"`
and `-m storage_scale` when hunting. Read `.cache/verify/runs/<id>/run.json`
receipts, never job-status text.

**Fix loops belong in lanes.** Worker contract clause 7 makes lanes exit
rebased on current master with the quick gate green. A returning branch that
fails gates on trivia (annotations, format) may be patched at harvest; a
branch failing on SEMANTICS goes back (completion lane on the same branch —
name the worktree; never a fresh worktree for the same bead).

**Substrate defects** are next work items, not friction to absorb: file
instances in the owning project's Beads with reproduction evidence, fix when
operator priority says so (2026-08-26 ruling: sinnix orchestration work is
top of queue). Client timeouts masquerade as "sinnixd is unavailable" —
check `CONTROL_OPERATION_RESPONSE_TIMEOUT_SECONDS` before diagnosing the
daemon. Deploy sinnixd changes only via the devshell `switch` wrapper, in a
window when no lanes are mid-launch; jobs survive daemon restarts.

## Cost discipline (why these rules exist)

Every wake is a full-context turn: batch what machinery can batch, write
future receipts at decision time, keep the board out of your head, and spend
your own tokens where judgment is irreplaceable — adversarial review and
frontier strategy.

## Process smells

Watch these ratios; each carries a measured pathological baseline from the
30-hour coordinator session that ran a campaign into the ground.

- **Graph churn**: task-tracker update/show calls versus closes. Pathology
  2170:43. Healthy is single digits to one.
- **Review share of dispatches**: a majority-review roster means the process is
  consuming itself. Pathology: 35 of 50 dispatches were reviews of dispatches.
- **Polling**: any status-poll loop is a substrate defect to fix, not a cost to
  accept. Pathology: ~730 polls for ~40 jobs.
- **Meta-bead growth**: process and calibration beads created faster than
  leaves close. Product defects are good growth; beads about the campaign's own
  machinery are the disease.
- **Context thrash**: re-reading the same help or doc content after compaction.
  A coordinator that must be reminded of its own CLI belongs in a smaller,
  fresher context.
- **Orphan obligations**: anything async created without a delivery path back
  to the decider at creation time — a dispatch with no watcher, a watcher
  writing a log nobody reads.

The cure is the same each time: move the mechanism into the substrate, keep
judgment above it, and spend tokens on merged outcomes.

## Packet and bead authoring

- **No dated note scrolls.** Consolidate on contact: one current-state note.
  A fresh-context worker acts on what it reads, so a superseded amendment
  presents a voided decision as current.
- **Readiness lives only in typed dependency edges.** Free-form "blocked-on-X"
  metadata goes stale the day the graph changes.
- **Spec weight tracks work size, not completion speed.** Heavy acceptance
  criteria mark big work, not dysfunction; do not impose ceremony on small
  fixes or read a heavy spec as a stalled one.
- **Acceptance criteria must survive their neighbors.** A criterion bound to a
  file another bead deletes manufactures false reds; name the invariant and its
  owning surface, not a doomed path.
- **Never name a live path as a deletion target.** A worker will act on it.
- **Co-execution via dispatch groups, never merges.** Beads sharing a file,
  area, fix pattern, or required context get `dispatch_group=<leader-id>`;
  one lane executes the group and each bead keeps its own verifiable close.
