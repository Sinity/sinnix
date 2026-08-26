# Coordinator contract (campaign overseer protocol)

A fresh session must be able to take over a running campaign from THIS
document plus the live carriers. Nothing here duplicates live state — it
tells you where state lives and what the loops are.

## State carriers (read these, never reconstruct from context)

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
  non-polylogue declared-operations — scheduled noise). Merge watchers
  (`merge_close.sh`) close beads themselves from decision-time receipts.
- **History**: per-project memory (`~/.claude/projects/<p>/memory/MEMORY.md`)
  and the repo's `docs/atlas/`.

## Capability map — READ BEFORE WRITING ANY PROCEDURE

The substrate owns more than this document historically described, and a
coordinator that does not know a verb exists will hand-roll a worse copy of it.
That happened all through 2026-08-26: a ~200-line shell harvest pipeline was
built and documented here as the sanctioned method while `agentctl workspace
publish` already did exactly the same thing as a typed operation with a
receipt; disposal was hand-scripted while `finish-integrated` already existed
with the correct squash-proof check. Two independent agents reimplemented the
same operation because neither had the verb in context. **That is a design
defect in this document, not in the agents.**

So: before scripting anything, look for the verb. `agentctl <noun> --help`.

| Need                                     | Verb (NOT a hand-rolled equivalent)                                                           |
| ---------------------------------------- | --------------------------------------------------------------------------------------------- |
| open a PR for a finished workspace       | `agentctl workspace publish --job <j> --title T [--body F] [--wait]`                          |
| land / integrate a workspace             | `agentctl workspace land --job <j>`                                                           |
| dispose after a GitHub merge             | `agentctl workspace finish-merged`                                                            |
| dispose when content is already in a ref | `agentctl workspace finish-integrated --target <ref>` (tree-contribution check; squash-proof) |
| protect work before risky integration    | `agentctl workspace checkpoint` / `restore` / `recover`                                       |
| stacked branches                         | `agentctl workspace stack` / `restack`                                                        |
| review state of a workspace              | `agentctl workspace review-status`                                                            |
| complete a packet                        | `agentctl packet finalize --verification-job <j> --packet-job <j>`                            |
| packet state                             | `agentctl packet status`                                                                      |
| task-backend mutations                   | `agentctl task create/claim/complete/note/update/relate/reconcile/snapshot`                   |
| wait on work instead of polling          | `agentctl job wait`, `agentctl agent wait`, `agentctl plan wait`                              |
| all evidence for a job or workspace      | `agentctl evidence <id>`                                                                      |

If a needed capability genuinely does not exist, that is a bead against the
substrate — not a reason to grow the shell pile. If you find yourself writing
git plumbing, gh calls, or bead mutations by hand, stop and check this table
first.

## The loops

**Dispatch**: prefer `agentctl packet launch <bead> --project <p>` (compiler
injects the worker contract; conflict keys declared + inferred). Ad-hoc work:
`dispatch_lane <project> <delta-file>` — author only the task delta; the
standing worker contract (worker-contract.md clauses 1–8) is injected by
reference. Launch packets SPACED (~30s, confirm fleet admission between);
duplicate-bead launches are refused typed when a live job owns the workspace.

**Harvest** (lane success event):

1. `actl result <job>` — expect the machine trailer
   (LANE-BRANCH/COMMIT/QUICK/CLASSIFICATION).
2. `redflags <worktree>` — deterministic scanner. No flags + small diff →
   stat-level skim. Flags → full adversarial read. The flags are the
   patterns that have actually caught dishonest lanes: deleted production
   lines, inverted/removed assertions, new xfail/skip, gate/baseline/
   migration/sidecar edits, deleted test files.
3. Judgment: honest classifications? scope respected? semantics not
   inverted? A lane that papered over a real defect gets REJECTED with the
   reason recorded on the bead — never merged "to keep moving".
4. Write the PR body AND the bead close-reason now (decision time), then
   `harvest_queue2.sh <wt> <title> <body> [<bead> <reason-file>]` — two-phase:
   the quick gate runs in PARALLEL across harvests (4-slot semaphore, one
   mechanical baseline pass), only push/PR/auto-merge serialize behind the
   repo flock (re-gating only if master moved). A bead-close receipt MUST
   carry a literal `DISPOSITION: close` line — slice receipts (bead stays
   open) queue WITHOUT bead args and the coordinator comments the bead
   instead. Queue with run_in_background; nohup survives the tool shell.
   (`harvest_queue.sh` is the retired serial v1 — same interface.)
5. Dispose worktrees only after content-equality/merge verification
   (`git worktree remove` + branch delete); live-process check first.
6. Dispatching into a worktree mid-harvest is MECHANICALLY refused, not left
   to memory: the harvest holds an exclusive `/realm/tmp/work/.wt-<name>.lock`
   for its whole run, and `dispatch_lane` exits 7 with `wt-busy` when that
   lock is held. If you see that refusal, wait for `HARVEST-OK`/`HARVEST-FAIL`.

**Launch wedges** (sinnix-dn4c): packet launch is an accidental saga — a
step failure is redacted to `OWNER_UNAVAILABLE "sinnixd is unavailable"` and
each retry advances one step (worktree → record → job). Retry ~3x spaced;
if a clean orphan worktree blocks recovery, `packet_unwedge <repo> <packet>`
removes it (refuses dirty/unpublished/live-process trees — a live-process
refusal means a provision is still running: wait, don't force).

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
frontier strategy. The measured pathologies live in worker-contract.md's
process-smells section; re-read after compaction.
