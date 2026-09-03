---
name: review-land
description: Review code or prose, audit acceptance criteria, resolve conflicts, commit, publish, merge, and close work through the repository's verified landing discipline.
---

# Review and land

## Review axes (report separately — never merge or rerank across axes)

A change can pass one axis and fail another; separation stops one masking
the rest. Pin the fixed point first (`git diff <base>...HEAD` against the
merge-base; confirm the ref resolves and the diff is non-empty before
anything else).

1. **Spec / whole-bead scope**: does the diff implement what the originating
   bead asked — every AC addressed (satisfied / deferred-to-named-successor
   / misframed), non-goals respected, no quiet scope substitution or creep?
   Quote the bead line per finding.
2. **Correctness & standards**: repo standards first (documented rules win);
   then the smell baseline (references/smells.md — Fowler set: mysterious
   name, duplication, feature envy, data clumps, primitive obsession,
   repeated switches, shotgun surgery, divergent change, speculative
   generality, message chains, middle man, refused bequest) as labelled
   judgment calls, skipping anything tooling enforces.
3. **Production reachability & test honesty**: new tests exercise
   production-reachable code at real seams; no tautological assertions (an
   expectation recomputed the way the code computes it proves nothing); no
   dead-engine certification; red twins where the change adds a detector;
   seams were pre-agreed, not discovered by the test.
4. **Operational safety**: durable-tier changes ride numbered migrations
   with consent; derived-tier changes declare their lifecycle class;
   deletions carry their declarations with them (no dangling CommandSpec,
   hook, config key, or doc line — a known breakage class).
5. **Verification authority**: what was actually RUN (exact commands, real
   output line), what was not run, and whether green means executed-green
   or selected/attested-green. A claim the evidence doesn't support is worse
   than no claim.

For risky or contested closures, add one adversarial pass: an independent
reviewer prompted to REFUTE the closure against the AC matrix, iterating
until it cannot find a legitimate gap (bounded — two clean passes suffice;
five means the change should be split).

## Landing

- **One PR per coherent batch** — lanes integrate into a batch branch; no
  per-lane PRs. Product repos: feature branch → squash-merge; the PR title
  is the permanent master subject (≤72 chars, imperative). Body sections:
  Summary, Problem (evidence), Solution (modules + non-obvious decisions),
  Verification (exact commands + the output line that matters).
- Stage by path, never `git add -A` on significant changes. Never
  `--no-verify` unbidden; a hook failure means fix the cause in a new
  commit. From a linked worktree, use `git -C /abs/path`.
- Lane flow where the repository lands via PRs: `agentctl lane publish
<worktree>` pushes the branch, opens the PR under the bead's type-prefixed
  subject (body from `.lane/body.md`), and arms `gh pr merge --auto
--squash`; branch protection, the required verify check and GitHub review
  decide when it lands. `agentctl lane sync <project>` closes the beads of
  merged lanes and removes their worktrees — no parallel merge ledger.
- A green hosted check is not test evidence where CI skips the heavy suite
  (recorded polylogue gotcha) — verify locally with the focused selector
  and say which tier ran. `devtools verify` selects from the checkout's one
  testmon datafile and writes back; `--all` runs everything; a corrupt or
  foreign datafile stops with `graph_unusable` (delete it and rerun). A
  selected green proves the selected scope only.
- Merge everything in progress, then run the corpus once at the master
  boundary (`agentctl job start polylogue verify_all`). Never a corpus run per
  lane; excisions land as whole merges.
- Before claiming "unified / complete / converged": grep the diff and check
  both paths. State partial work honestly; split remainder to a successor
  bead ([[task-backend]] close discipline).

## Conflicts

Resolve by intent traced to each side's primary sources (commit messages,
PRs, beads) — never by picking lines; preserve both intents where possible;
never invent behavior mid-merge; never `--abort` as a resolution. Commit
after every conflict-resolution edit. Autostash reapply can leave conflict
markers — grep for them before continuing.

## After landing

Complete the beads with PR + merge SHA, remove the integrated worktree
(`agentctl lane sync <project>` or `wt remove`), clean transient artifacts
you created, and carry any
deferred scope into named successors — landing is not done while the
tracker lies about what happened.
