# Orchestration: what the evidence says

Working sketch. Evidence first, design second; nothing here is settled.

## Throughput record

`devtools` lines on polylogue master against PRs merged per day:

| date | devtools lines | PRs/day |
| --- | ---: | ---: |
| 2026-06-15 | 23,331 | — |
| 2026-08-10 | 89,884 | 1–12 |
| 2026-08-18 | 66,591 | 12–24 |
| 2026-08-27 | 39,068 | 36 |

agentctl/sinnixd landed 2026-08-22; campaign/packet/reactor 2026-08-26.
The throughput trough sits on the peak of tooling mass, and recovery begins
with `c17e38539` (2026-08-14), which deleted 324 files and ~79,000 lines of
"self-attesting campaign bureaucracy".

That commit names the failure mode precisely: generated mirrors, passive
ledgers, duplicate tracker projections, and *tests that proved only their
declarations*, which together *made process artifacts look like runtime
authority*. `b0cee7b99` adds the sharpest form: the artifact registry
*duplicated runtime relationships as manually curated descriptors* and
*could attest to itself without proving a production route*.

**Design rule that follows.** Rank every change by the ongoing obligation it
imposes on future contributors. Prefer mechanisms needing no declaration and
no protocol. A declaration that duplicates a runtime fact, and can be
satisfied without touching the runtime, is the thing that failed here before.

Declarations that earn their place: those a machine must read to act at all
(what an operation runs, what a bead needs to be dispatchable). Those that
restate what the runtime already knows: no.

## Per-lane vs batched publication

| | 2026-08-26 | 2026-08-27 |
| --- | ---: | ---: |
| PRs merged | 144 | 36 |
| lines changed | 47,435 | 22,028 |
| files touched | 870 | 397 |
| files per PR | 6.0 | 11.0 |
| shape | 114/144 `feature/packet/*` | hand-driven `integration/batch-*` |

Per-lane publication moved roughly twice the volume. Batching was introduced
because it catches defects no per-lane gate sees — cross-lane type errors, a
lane merging clean but semantically stale against a moved master. Both are
real.

The mistake was putting the cross-lane check *on the critical path*. It
belongs continuously against master, not as a precondition for landing.

## Containment

Measured, not assumed:

- A double-forked `setsid` daemon stays in its launching cgroup, is reparented
  to the user manager, and dies when the scope is stopped. Nothing escapes a
  cgroup; a process is only outside one if it was never inside one.
- Lane jobs already land in `sinnixd-work-{agent,normal,bulk}.slice` with
  `KillMode=control-group`, so they self-clean.
- The coordinator session runs in the terminal's scope, unmanaged. Every
  leaked `dmypy` daemon (12 of them, 15.8 GB of swap, host at 85% swap and in
  the measured pre-freeze regime) was coordinator-side.

So containment belongs to the launcher, applied at the outermost process the
machine starts. Projects declare semantics; the host decides mechanism.
`devtools verify` must keep working on a laptop with no daemon.

Two corollaries:

- **Admission happens at the outermost managed ancestor.** Inner work is
  accounted, never separately admitted; nesting admission deadlocks an agent
  behind its own reservation.
- **Scope is not throttle.** Scoping is lifecycle and accounting; slices and
  weights are priority. Interactive work can be scoped without being slowed.

## Friction observed while landing one lane

Closing `sinnix-ygjw` end to end took six commands and an identifier lookup:
rebase, fix, test, merge, push, `bd close`, then `workspace dispose` — which
rejects the `name` that `workspace list` prints and requires the `workspace_id`
it also prints. Landing must settle its own beads and workspaces
(`sinnix-oj9s`), and one identifier should work everywhere it appears.

## Open questions

- Do workers open their own PRs (`sinnix-a23x`), with the coordinator reviewing
  only flagged ones (`sinnix-rroi`)? The throughput record favours it.
- What is the smallest thing that gives composites (campaign, packet, plan) a
  real executor, so the coordinator sets policy rather than driving items
  (`sinnix-b3jn`, `sinnix-235w`)?
- Which of today's coordinator actions were genuinely judgment, and which were
  mechanical? Recorded per session, this answers the previous question with
  evidence instead of taste.

## Shared-checkout hazard

Sinnix's own development happens directly in `/realm/project/sinnix`, with no
per-change workspace. Two sessions working at once therefore share one dirty
tree: on 2026-08-27 an unrelated commit appeared on both master and an active
integration branch mid-rebase, and an earlier uncommitted change was swept into
someone else's commit. Polylogue lanes get worktrees; sinnix work does not.

## The coordinator is the unmetered workload

On 2026-08-27 a coordinator dispatched seven integration agents at once. Each
fanned out to per-lane subagents, and each of those started a verification gate:
nineteen concurrent gates against a 24-core, 32 GB host. Swap reached 95.7% and
the host entered the measured pre-freeze regime. Two of the coordinator's own
shell commands were killed under the pressure it had created.

Nothing metered any of it. Lane jobs launched through `agentctl` land in
`sinnixd-work-*.slice` with real admission; work an agent starts from its own
shell inherits the terminal's scope, where the only policy is `MemoryLow=4G`
protecting it from reclaim. The scheduler saw none of the load it was supposed
to govern.

This is the same failure the freeze work addressed, reproduced from the other
side: not a runaway job, but an orchestrator with no admission control over
what it spawns. Contained coordinators would have queued those gates instead
of stampeding, without any cap on how much work is in flight.

Concurrency is not the lever. Nineteen gates is a reasonable amount of work for
this machine to *want*; it is an unreasonable amount to run simultaneously. The
missing piece is a queue, and the queue already exists — the work simply is not
in it.
