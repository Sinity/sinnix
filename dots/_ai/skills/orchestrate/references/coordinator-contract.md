# Coordinator contract (campaign overseer protocol)

A fresh session must be able to take over a running campaign from THIS
document plus the live carriers. Nothing here duplicates live state — it
tells you where state lives and what the loops are.

## State carriers (read these, never reconstruct from context)

- **Board**: `/realm/tmp/work/campaign-board.json` — lanes → PRs → beads →
  review state. `board` prints it; `board sync` refreshes from
  fleet/GitHub/worktrees. Maintained by the watchers; trust it over memory.
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
   `harvest_queue.sh <wt> <title> <body> [<bead> <reason-file>]` — it
   flock-serializes, clears stale locks, rebases, runs the quick gate (one
   mechanical baseline pass), pushes, PRs, arms auto-merge + a watcher that
   closes the bead on merge and updates the board. Long gates: run it
   with run_in_background.
5. Dispose worktrees only after content-equality/merge verification
   (`git worktree remove` + branch delete); live-process check first.

**Refill** (keeper tick): `board` first — if lanes ≥ target and nothing
review-ready, say so and stop. Otherwise `bd ready` (repo cwd), plan with
`--plan` (shows declared + inferred conflict keys), launch disjoint spaced.
Hold semantically-overlapping beads apart even when keys are textually
disjoint (same subsystem orbit = same wave slot).

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
