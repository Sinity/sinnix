# Worker contract template and process smells

> Direction (operator, 2026-08-26): defaults should be AUTOMAGIC, not
> contractual. Every mechanizable clause below migrates into machinery
> (launch snapshot → packet-launch compiler; managed verification →
> `lane verify`; report-once → `lane done`; seeds → workspace provisioning;
> exit honesty → bounded.py). This document trends toward the machinery's
> spec plus only the unmechanizable residue: red-first judgment, honest
> report content, no scope expansion.

## The dispatch contract (v2, 2026-08-25)

Every implementation dispatch carries, verbatim in the prompt:

1. **Task content as a launch snapshot**: the bead's description + AC
   compiled into the prompt FROM the task authority at dispatch time (a
   fresh `bd show` at prompt-build, or the worker running `bd show` as its
   first act) — never a hand-copied paraphrase, and never "read bead X"
   with no content when the worker may lack task-backend access. Exact
   worktree/branch, files in scope. This reconciles the pointer rule with
   content-carrying: the content travels, but only as a dispatch-time
   snapshot of the authority, so no stale copy accumulates. Where the repo
   has an atlas (`docs/atlas/`), the prompt names the relevant area sheet —
   orientation comes from the atlas, not from the worker re-deriving it.
2. **Self-verification loop**: the worker fixes → tests → iterates until
   green _within its own run_. It owns its defects. It never spawns review
   subagents, and no dispatcher builds review→fix→review chains around it —
   hosted PR review (Codex/CodeRabbit) plus the test oracle are the
   structural check.
3. **Red-first for bug fixes**: demonstrate the failure, then fix, then show
   green. Each new test names its anti-vacuity condition (what mutation
   would make it red).
4. **Managed commands only** (per repo contract, e.g. `devtools test <sel>`
   never bare pytest), commit by path, push, one summary comment at the
   destination (PR/bead), never merge.
5. **Honest report, once**: per-finding/per-AC disposition, exact commands +
   the result line that matters, diffstat, residual risk. Refuted findings
   need evidence, not dismissal. Going idle without a report is a contract
   violation — the report IS the deliverable. Report in ONE place (the job
   result / final message); PR or bead comments only for information that
   cannot live in the typed result — duplicated summaries become stale
   copies. Piped exit codes lie: `cmd | tail` reports tail's status — use
   pipestatus (or capture to file) before claiming a gate passed.
6. **No scope expansion**: discoveries become bd filings or report notes,
   never inline extra work.
7. **Exit at current master** (2026-08-26, from a wave where every stale-base
   branch cost a coordinator fix loop): before the final report, `git fetch`
   and rebase the branch onto `origin/master`, rerun the repo's quick gate in
   the REBASED state (gates added mid-wave — reachability, closure — only run
   here), fix what it surfaces, and push. A conflict the lane cannot resolve
   honestly is reported as such — never force-resolved to green.
8. **Machine trailer**: end the report with exact lines
   `LANE-BRANCH: <branch>` / `LANE-COMMIT: <sha>` / `LANE-QUICK: green|red|blocked-env`
   / `LANE-CLASSIFICATION: <one line per finding for fix lanes>` so the
   harvester parses state instead of prose.

9. **Never mutate live operator state** (2026-08-26, from a lane that deleted
   a coordinator tool out of `~/.local/bin` mid-campaign because its bead text
   named that path): a lane's writes stop at its own worktree. No writes under
   `$HOME`, no edits to installed tools or live service state, no
   `switch`/`boot`/system or Home-Manager rebuild — a rebuild from a lane
   worktree would deploy that BRANCH to the live machine. Retiring an
   installed tool means deleting it from the source-of-truth tree and saying
   so in the report; removing the live copy is a coordinator act, sequenced
   after the replacement actually ships. Bead authors: never name a live path
   as a deletion target (that authoring defect caused this one).

Verification economics in lanes (operator ruling, 2026-08-26): lanes run
SELECTED verification from the seed inherited off the main checkout — never
the corpus, and never bootstrap-from-scratch; selected-run false negatives
are acceptable risk, caught by the full corpus at merge/master boundaries.
A lane that finds no compatible seed refuses-and-reports rather than
silently running broad.

Escalation: a stuck lane gets a hint, a respecified bead, or a model switch —
never an effort bump (see model-landscape reference). One flounder → escalate
tier; never retry the same model against the same failure.

## Process smells (from the 2026-08-25 coordinator postmortem)

Watch these ratios in any long-running orchestration; each has a measured
pathological baseline from the 30h coordinator session that ran the campaign
into the ground:

- **Graph-churn ratio**: task-tracker update/show calls vs closes. Pathology:
  2170 bookkeeping : 43 closes (~50:1). Healthy: single-digit:1.
- **Review share of dispatches**: majority-review dispatch rosters mean the
  process is consuming itself (pathology: ~35 of 50 dispatches were
  reviews/audits of other dispatches).
- **Polling calls**: any status-poll loop is a substrate defect to fix, not
  a cost to accept (pathology: ~730 polls for ~40 jobs).
- **Meta-bead growth**: process/validator/calibration beads created faster
  than leaves close. Finding product defects is GOOD growth; filing beads
  about the campaign's own machinery is the disease.
- **Coordinator context thrash**: re-reading the same help/task/doc content
  after compaction (pathology: 64 compactions, 14 re-reads of one --help).
  A coordinator that must be reminded of its own CLI belongs in a smaller,
  fresher context — or replaced by the setup itself.

The structural cure each time: move the mechanism into the substrate (typed
readiness, completion events, validators), keep judgment above it, and spend
tokens on merged outcomes.

One more smell with its cure (2026-08-26, from three finished-unprocessed
jobs): **orphan obligations** — anything async created without a delivery
path back to the decider AT CREATION (a dispatch without a watcher, a
watcher writing a log nobody is prompted to read). Cure: one event stream
(everything terminal appends — jobs via the daemon, scripts via the append
convention), one persistent consumer, and an acknowledgment cursor making
"unprocessed backlog" a queryable fact (SessionStart prints it; the
dispatch breaker refuses past a threshold) instead of a session memory.

## Packet/bead authoring rules (from the 2026-08-25 quality audit of 44 beads)

- **No dated note scrolls.** Consolidate on contact: one current-state note;
  superseded amendments die. A fresh-context worker acts on what it reads —
  several audited beads presented voided decisions as current.
- **Readiness lives only in typed dependency edges.** Free-form
  "blocked-on-X" strings in metadata went stale the day the graph changed
  (13 of 42 audited beads). If the validator owns it, prose must not.
- **Spec weight tracks work size, not completion speed** (corpus-measured,
  n=956 closed): small bounded fixes close in days with light AC; heavy
  AC/design marks big work, not dysfunction. Don't impose ceremony on small
  fixes, and never read a heavy spec as a stalled one.
- **Oracles must survive their neighbors.** An acceptance criterion binding
  to a file another bead deletes manufactures false reds; name the invariant
  and its owning surface, not a doomed path.
- Bead state updates mechanically where possible: completion events →
  task-note automation beats manual reconciliation.
- **Co-execution via dispatch groups, never merges**: beads sharing a file,
  area, fix pattern, or required context get `dispatch_group=<leader-id>`
  metadata; the leader's notes list members; one lane executes the group
  (packet-launch compiles it). Merging beads is NOT the mechanism — each
  instance keeps its own verifiability and typed close. Utility-plus-adopters
  is the canonical shape (kernel lands, batch adopts, ratchet closes behind),
  but any shared-context cluster qualifies, related or not.
