# Batch and worktree execution

Extracted from the global operating contract (2026-08-11); this is the full
procedure behind the compact rules that remain in CLAUDE.md. The unit of work
is a **cluster of related items**, not one tracker item at a time.

## Worktree-isolated fanout

The rules here are for worktree-isolated agents only; if agents intentionally
share one checkout, the coordinator owns branching/committing/merging and
agents report patches or commit only by explicit instruction.

- Agents run in isolated worktrees (`isolation: "worktree"`). The isolation
  system auto-cleans worktrees on completion, discarding uncommitted
  working-tree changes. **Agents MUST `git commit` every logical chunk.** Even
  a WIP commit is fine; the branch persists.
- **Never `cd /realm/project/<name>` from inside a worktree agent.** The
  worktree is the agent's root. If an agent `cd`s to the main checkout,
  commits land on the main branch — corrupting both.
- **Verify git remote.** Before pushing, confirm `git remote -v` and
  `git branch --show-current` match the worktree branch.
- **Commit cadence:** commit after each project check passes, not after "all
  work done". First commit once the first relevant check passes, then per
  milestone. This prevents worktree auto-cleanup data loss and makes
  incremental merge possible.

### Write-scope separation

- Before dispatching, identify shared files (e.g., `schema/mod.rs`,
  `apply.rs`, `lib.rs`). These are conflict hotspots.
- When two lanes MUST touch the same file, serialize them: first lane
  commits + merges, second lane rebases.
- For additive changes to shared files, pre-define which lane owns each line
  range.

### Pre-flight checklist for each agent prompt

1. Specify exact files the agent OWNS vs AVOIDS
2. Include a "FIRST: comment on issue #N with scope" step
3. Include a "commit after each successful check" instruction
4. Warn about worktree cleanup: "commit or lose it"
5. After spawn, verify the worktree actually exists, is a linked worktree
   (not the main checkout), and is on the expected branch before trusting
   any output — `isolation: "worktree"` can silently fail to create one, in
   which case the agent runs directly in the main checkout and its diff is
   not isolated, and its writes land in the live tree. For AgentCTL-managed
   workspaces, use
   `agentctl workspace get <workspace-id>` and require `identity_matches`,
   the expected path and branch, and the exact reported HEAD.

### Post-agent merge checklist

1. Verify the workspace's reported exact HEAD and clean/dirty state with
   `agentctl workspace get <workspace-id>`.
2. Checkpoint dirty work before recovery or integration; do not copy changes
   between checkouts as a substitute for preserving their Git identity.
3. Use `agentctl lane publish <workspace-id> [--close]` for delivery;
   dependent histories rebase onto their parent branch by hand.
4. After GitHub merges the PR, use `agentctl workspace drop <workspace-id>`;
   for abandoned work drop with `--force` once its checkpoint and divergence
   evidence is resolved.

### Foreground-only execution

Every command a worker runs must execute synchronously in the worker's own
turn; never launch a background job and idle-wait on it across turns. A
worker that backgrounds a test/build run and then reports "waiting for it to
finish" wastes real wall-clock and coordinator attention every time
(repeatedly observed, polylogue 2026-08-01 fanout) — always run it in the
foreground and let the turn take as long as it takes.

## Cross-item batch execution (content-aware)

Before claiming, look at what else in the ready set touches the same
files/area (in beads repos: design-field anchors, prework packets, or a
clustering helper where the repo has one).

- **Overlapping footprints** (same modules): claim the cluster, one branch,
  rewrite the area once satisfying every item's AC, per-item commits as
  review waypoints, one sweep PR with a per-item AC matrix. Paying the
  area-reading cost once and avoiding self-conflicts between successive PRs
  is the point.
- **Disjoint footprints**: separate PRs (squash-merge = one master commit per
  logical change), but pipeline them in one session/checkout: branch A →
  commit → push → PR, then branch B from fresh master immediately while A's
  CI runs. Never idle-wait on CI.
- **Parallel subagent worktrees** only when ≥3 disjoint lanes exist, each
  execution-grade (full design or packet), with no shared hotspot files —
  then the packet/design IS the subagent prompt. Otherwise one agent
  pipelining beats coordination overhead.
- **Verification amortization**: workers run focused real-route checks plus
  the affected-area check their own change warrants. The coordinator runs
  the broad gate once per branch at the publish boundary, not once per item.
  In a multi-merge fanout session, run this broad gate on the _merged master
  state_ at each merge-train boundary, not only pre-merge on the feature
  branch — a global drift-latch class (an unrelated enum/vocabulary change
  breaking an assertion elsewhere) is invisible to any single PR's
  affected-test selection and only surfaces when the merged result is tested
  as a whole. Schedule one full, non-affected-only suite run per heavy
  multi-merge session before declaring it done; per-PR CI deliberately
  skipping the heavy suite means nothing else will catch this class.
- **Content-aware shapes**: mechanical sweeps (lint/docs/renames) batch
  hardest; schema/migration bumps must batch per tier/window; investigation
  items batch over a shared evidence pass; decision items batch into one
  operator review session.
- **Beads hazards** (JSONL export conflict resolution and per-operation
  commit noise): see the `beads` skill's
  "Hazards" section — lane agents make no `bd` writes; coordinators audit
  bead state at merge-train boundaries and batch jsonl commits per unit of
  work.

## Codex model contract

The coordinating interactive session uses `gpt-5.6-luna` at high reasoning by
default. Unattended implementation/review workers use `gpt-5.6-terra` at high
reasoning. Always pass the model and effort explicitly and verify them in the
launch receipt; never silently fall back to a stale configured model.
`gpt-5.5` is retired for new work.
