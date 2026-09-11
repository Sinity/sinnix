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
2. **Correctness & standards**: repo standards first (documented rules win),
   then concrete code evidence and labelled judgment calls, skipping anything
   tooling already enforces.
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

- **Match the delivery route.** For an external batch,
  `agentctl batch land <run>` integrates the worker branches, runs the
  descriptor's declared candidate profile when present, applies its review
  policy, publishes, and records acceptance. A hosted profile waits for that
  named check; an agent review runs only when the descriptor requests it. For
  native work, the coordinator verifies the selected evidence and commits the
  cohesive result in the repository's normal publication route. Neither route
  adds a corpus or reviewer by default. Product repos (`publish = "pr"`): one
  PR whose title is the permanent master subject (≤72 chars, imperative),
  merged with `gh pr merge --squash --match-head-commit <candidate>` after the
  declared checks. Sinnix (`publish = "master"`): fast-forward the candidate
  once master still equals the run's base. Body sections for a hand-written PR:
  Summary, Problem (evidence), Solution (modules + non-obvious decisions),
  Verification (exact commands + the output line that matters).
- Stage by path, never `git add -A` on significant changes. Never
  `--no-verify` unbidden; a hook failure means fix the cause in a new
  commit. From a linked worktree, use `git -C /abs/path`.
- A green hosted check proves only the job it actually ran. Read the
  candidate's receipt and verification contract, run a focused selector when
  the task requires local test evidence, and state which tier ran; a selected
  green proves only the recorded scope.
- Land the requested cohesive scope. Run an affected/full suite only when the
  operator explicitly requests it; record it separately from focused checks.
  Excisions land as whole merges.
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

For native task-bound work, use `agentctl evidence file` to retain the result
with owner-checked publication and job references. Follow `docs/agentctl.md`;
missing historical receipts remain unknown rather than being reconstructed
from a successful commit or a worker assertion. This does not create a batch
or require another checkout.

`batch land` closes the beads whose criteria its worker results satisfy,
comments the residual on the rest, and removes the worker worktrees; read
the acceptance record in `batch status <run>`. Close beads you landed by
hand with the PR and merge SHA, remove your worktree (`wt remove`), clean
transient artifacts you created, and carry any deferred scope into named
successors — landing is not done while the tracker lies about what
happened.
