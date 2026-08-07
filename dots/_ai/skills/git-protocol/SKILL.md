---
name: git-protocol
description: Use when committing, branching, pushing, opening or reviewing pull requests, resolving conflicts, staging files, or applying GitHub repository workflow rules.
---

## Git Protocol

Universal git/GitHub protocol. Project-specific extensions go in each repo's CLAUDE.md / CONTRIBUTING.md.

### History is durable

`master` / `main` is a permanent artifact. Three readers pick it up cold —
future-you, future-agents, `git bisect` — and all fail when a commit subject is
`asdf`, the body is empty, or the PR boundary is lost.

Navigable signals: conventional prefix (`feat:`/`fix:`/...), `(#N)` suffix on
squash-merges, non-empty body, specific subject, one-logical-change-per-PR.

### Committing

**Commit and push proactively within repo policy.** Commit each logical unit as it lands on a feature branch — don't wait to be asked. Push feature branches after verification so work is backed up and PRs can be opened or updated. For solo direct-master repos such as Sinnix and Lynchpin, committing and pushing `master` is allowed after local verification and deployment rules are satisfied. Do not push only when the user, repo, or current workflow explicitly says to hold.

**Signing must be GitHub-verifiable, not merely cryptographically valid.**
Before committing, confirm the effective committer identity is a verified
GitHub identity and the configured signing key belongs to that identity. Never
set a synthetic repository-local `user.name` or `user.email` for agent work;
use co-author trailers for agent attribution. A good local `git verify-commit`
result is insufficient when the signer cannot be bound to the recorded
committer. For any history-signing rewrite, preserve author date, committer
date, tree, message bytes (including PR/issue links), and parent topology in an
old-to-new manifest, then audit GitHub's `verification.verified` result after
publication.

**Merging is part of the job — standing authorization.** These are solo-operated repos: agent-opened PRs have no human co-reviewer, so the merge gate is checks + triage, not a human click. Squash-merge your own PR (`gh pr merge --squash`) as soon as (a) required checks are green and (b) every substantive automated-review finding is triaged — actionable items fixed, false positives answered with a brief reply. Do not park green, triaged PRs "for review"; do not ask permission to merge them. Hold a merge only when the user, repo policy, or the PR body explicitly says hold, or a red substantive gate remains. This authorization is durable and applies in auto mode.

**Atomicity test:** can you write a subject without "and"? If you need "and", split. Err toward more commits — you can always squash before PR.

**Conventional prefixes** (pick accurately — reviewers filter by type):

| Prefix           | Meaning                                  |
| ---------------- | ---------------------------------------- |
| `feat:`          | User-visible new capability              |
| `fix:`           | Bug fix                                  |
| `refactor:`      | Internal restructure, no behavior change |
| `perf:`          | Optimization (include measurement)       |
| `test:`          | Test-only                                |
| `docs:`          | Documentation only                       |
| `chore:`         | Tooling/deps/config                      |
| `build:` / `ci:` | Build system / CI config                 |
| `style:`         | Formatting only                          |
| `archive:`       | Move to `archive/` instead of delete     |

Use scopes (`fix(cli): ...`) when the repo is large enough that scope adds clarity.

**Subject line (≤72 chars):**

- Present-tense imperative (`add X`, not `added X`)
- Describes what _landed_, not what was _worked on_
- Specific nouns, not vague gerunds (`fix: handle null cursor in pagination`, not `fix: pagination bug`)
- No trailing period

**Body (required for anything non-trivial):**

- Blank line between subject and body; wrap at 72 chars
- Four sections worth writing (not all always required): **Problem** (what observation/constraint triggered this), **What changed** (higher level than the diff), **Alternatives rejected** (only if there was a real fork), **Compatibility/migration** (breaking changes)
- Issue refs in body: use neutral references only, e.g. `Ref #N`.
  Do not put GitHub resolver keywords adjacent to issue numbers in
  agent-authored text. If a human explicitly wants a specific PR to
  change a specific issue's GitHub state, get that instruction for that
  exact PR and issue immediately before writing the resolver phrase.
- `BREAKING CHANGE: ...` footer for breaking changes
- Co-author trailer:
  ```
  Co-Authored-By: Claude <noreply@anthropic.com>
  ```

**Staging:** by name (`git add <file>`). Never `git add -A` / `git commit -a` on significant changes — sweeps in `.env`, credentials, build output. Review with `git diff --staged` before commit.

**Shared-checkout safety:** multiple agent sessions may work the same live
checkout concurrently. Before committing, check `git status` for staged files
you did not stage and confirm the current branch is the one you think it is
(`git branch --show-current`) — another session may have switched it under
you. When contention is possible, commit by explicit pathspec
(`git commit -- <your paths>`) so a bare `git commit` cannot sweep a
co-worker's staged work into your commit; prefer a dedicated worktree for
anything longer than a quick fix.

**Hooks:** never skip (`--no-verify`, `--no-gpg-sign`) unless the user explicitly asked. Hook failure = no commit; fix the root cause and make a NEW commit (don't `--amend` — that modifies the previous successful commit).

### Branching

- **All product/project code lands via PRs** to default. No direct pushes to
  `master`/`main` — the PR flow enforces `(#N)`, reviews, CI gating, history
  navigability. This applies to repos such as Sinex and Polylogue.
  **Sinnix and Lynchpin are the exceptions:** both are operated solo and may be
  committed and pushed directly on `master` after local verification (and, for
  Sinnix, successful deployment). Still write navigable commit messages.
- **Feature branches start from fresh `origin/master`.** `git fetch --all` first.
- **Name:** `feature/<type>/<short-dash-separated-desc>` (lowercase, no dates/initials/ticket-nums in branch names — those go in commits/PR body).
- **Rebase, don't merge** when syncing feature branches from master. Global config sets `pull.rebase = true` and `rebase.autoStash = true`.
- **Before opening PR:** `git tidy` (interactive rebase on upstream) to squash fixups, reword subjects, reorder, drop reverted work. Then `git push --force-with-lease`.

### Pull Requests

**Substrate choice — check before writing "open an issue" anywhere below.**
Where `bd where` succeeds in the current repo, Beads (`bd create`) is the
task substrate — every "issue" reference in this section means "bead" there
(sinex retired GitHub Issues entirely 2026-07-10; see its CONTRIBUTING.md).
Where the repo has no `.beads/` workspace, GitHub Issues remain the
substrate and the text below applies literally. Do not let this section's
GitHub-flavored wording pull a beads-repo agent back toward opening a GitHub
issue out of instruction-following inertia.

**File a tracking item first** for: work spanning multiple PRs, architectural decisions, bug reports needing repro, research questions, follow-up chains, durable debt discovered mid-implementation. Skip for self-contained PRs where the body is sufficient record.

**Convert anonymous debt into tracked debt.** When you discover an expected-failure test, a persistent TODO, or out-of-scope work: file a bead or issue and reference it from the code/PR. Anonymous TODOs rot.

**Tracking-item comments/notes are part of the spec.** Before implementing a
bead or issue, read its full thread/notes, not only the description. Later
comments may supersede, narrow, correct, or expand the original. If they
conflict, preserve the evidence in your own bead note / issue-or-PR comment
and state the interpretation you are implementing.

**GitHub resolver keyword discipline (GitHub-issue repos only — beads has no
resolver-keyword hazard).** In issue comments, PR bodies, commit messages,
and bot/review replies, do not write GitHub resolver keyword forms next to
issue numbers in agent-authored text. This includes negative phrasing, audit
notes, prompts, examples, and descriptions of partial work. Use neutral
references plus explicit residual wording instead: `Ref #N` and
`Remaining #N scope:`. Do not include example resolver phrases in prompts or
docs; agents copy examples. Resolver phrases are permitted only when the user
explicitly instructs that a specific PR should change a specific issue's GitHub
state, and the current evidence proves the full issue scope is satisfied.

**Leave an implementation trail.** Agents working a bead or issue should
comment/update it with: their understanding of scope; important constraints
or non-goals; what they changed; what they intentionally did not change;
acceptance criteria satisfied, deferred, or found misframed; verification
run; and follow-up tracking items opened. Do not let meaningful research,
scope decisions, or discovered drift survive only in chat or scratch notes.

**PR size and shape:** prefer substantial, cohesive PRs over micro-PRs that
burn CI/review cycles. A good PR may contain multiple atomic commits while in
review, then squash to one permanent master commit. Size the PR around a
complete tracking-item slice or coherent implementation phase. Tiny PRs are
appropriate only for urgent fixes, risky isolated changes, or when a larger
branch would mix unrelated concepts. If a slice is large but coherent, keep
it as one PR with a read order, self-review notes, and focused commits.

**Phase batching:** when a bead or issue has several adjacent acceptance
criteria that touch the same subsystem, keep them on one branch until the
coherent phase is exhausted. Use multiple commits as review waypoints, not
multiple PRs by default. Before opening a PR, update the tracking-item/PR
narrative with a compact matrix: satisfied, intentionally deferred,
misframed, and still open.

**Verification cadence:** do not run the slowest gate after every small edit.
During implementation, run the narrow command that proves the changed behavior
plus cheap static checks. Run the broad local gate once when the phase is ready
to publish, again only after material changes to the tested surface or after a
failure fix. If a broad suite exposes an unrelated flaky/pre-existing failure,
rerun the exact node to classify it, record the evidence, and avoid turning the
current PR into an unrelated cleanup unless the fix is necessary and local.

**CI/review economy:** don't wait passively on known-quota or known-slow CI when
local gates and required impact reports already give enough evidence for the
next action. Classify rate limits, pending capacity, and tool failures quickly
instead of letting them stall implementation. Green checks are not a substitute
for reading substantive comments. This economy rule never authorizes merging
through a failed substantive gate: a red schema/build/test/security/proof check
is a blocker until fixed or until the user explicitly accepts that exact
failure.

**PR title = squash-merge subject.** ≤72 chars, conventional prefix,
imperative, describes what changed, ends with `(#N)`, accurate — don't claim
"unified"/"fixed" unless the diff achieves it.

**PR body = squash-merge body.** Required sections: **Summary** (one para),
**Problem** (evidence/motivation — not "user asked"), **Solution** (modules
touched, non-obvious decisions, rejected alternatives), **Verification** (exact
commands run + the output line that matters, not "tests pass"). Optional:
Migration notes, Follow-ups, Breaking changes. Link the tracking item: bead id
(e.g. `sinex-abcd`) or `Ref #N` for a GitHub issue.

**Claim verification — grep the diff before asserting:**

1. Grep for duplicated logic. If you claim "unified into one helper," is the old helper actually gone?
2. Check all call sites if claiming "every path now uses X."
3. Read the PR's GitHub diff (not just local) — catches force-push/merge artifacts.
4. Revise the claim if the code doesn't support it; "partially unified" is valid, "unified" when half-done is a lie.
5. Test the claim. If a PR claims to repair a bug, the verification section shows that bug's repro passing.

**Acceptance-criteria honesty.** If a bead or issue has acceptance criteria,
address each item explicitly in the PR or tracking-item comment that claims
completion: mark each as satisfied, deferred to a follow-up tracking item, or
misframed by new evidence. Never claim a partial subset satisfies the full
scope without making the remaining work durable. Tests are not a substitute
for missing runtime wiring: if the tracking item asks for an operator flow,
actuator behavior, CLI command, or replay path, data-model or test-only
changes do not close it unless the item was explicitly narrowed to that
surface.

**Automated reviews are review input.** Before merging, inspect every automated
review/comment/check that posts substantive text (CodeRabbit, Copilot, proof
packs, scanners). Classify each item as actionable, false positive/noise,
informational, or tool failure. Address actionable items with code or tests;
leave a brief comment for false positives when the reason matters. Do not merge
while a bot reports unresolved actionable findings.

**Proof/impact reports.** When a repo posts generated impact reports, use them
to choose gates and focus review. Triage known-gap dumps and boilerplate gates
rather than following them blindly; if the report is noisy or misleading,
improve the report or record the mismatch in the owning tracking item.

### Squash-merge hygiene

**`(#N)` suffix on master.** GitHub's "Default commit message: Pull request title and description" setting auto-appends `(#N)` and copies the PR body. Enforcement options per repo: a Ruleset with subject regex, or the repo default-commit-message setting. When running `gh pr merge <N> --squash` with custom `--subject`/`--body`, supply `(#N)` manually — the default is bypassed.

**Granularity is forward-only.** Prefer fewer, fatter PRs; fix granularity at PR-open time. Do not post-hoc combine or rewrite merged history — that destroys PR boundaries and external links. Live with imperfect merged commits; fix the process, not the past.

### Destructive operations — require explicit confirmation

Even in auto mode, state specifically what will happen and pause:

- `git reset --hard` on a branch with uncommitted changes
- `git push --force` on any branch (`--force-with-lease` on shared branches is still disruptive)
- `git branch -D` on a branch whose content is NOT on the default branch
- Amending a pushed commit
- `git rebase` rewriting published history
- Deleting unmerged branches, stashes, or tags
- `git clean -fd`

**Routine cleanup is not destructive — standing authorization, no
confirmation needed:** deleting local and remote branches whose PRs are
merged, removing their worktrees, and pruning stale remote-tracking refs.
Squash-merged branches fail `git branch -d` by design (the tip is not an
ancestor of master); verify the merge (`gh pr view <N> --json state` says
MERGED, or the squash commit is visible on the default branch), then `-D`
is the correct, routine command — not a pause-worthy act.

Never force-push to shared branches without agreement. Never push to `master` /
`main` directly in product/project repos. Sinnix and Lynchpin are intentionally
operated directly on `master`; do not invent a branch/PR boundary there unless
explicitly requested.

**Force-push alternatives:** amending your own feature branch is fine. Fixing a
typo in a recent master commit: _don't_ — history isn't worth rewriting over
one character. Adding a missing `(#N)` to one commit: don't — fix the process,
accept the miss.

### Repository settings (set once per repo)

- Branch protection on default: require PRs, prevent direct pushes.
- Required CI status checks before merge.
- **Squash-merge only.** Disable merge commits + rebase-merges.
- **Default commit message:** "Pull request title and description".
- Auto-delete head branches; allow "Update branch" for stale PRs.
- Prefer disabling GitHub's auto-close-issues-on-merge repository setting.

### Merge conflicts

Investigate before resolving — read both sides, don't auto-prefer `theirs`/`ours`. Global `conflictStyle = zdiff3` shows the common ancestor alongside both versions. Run the verify command after resolving. If the conflict reveals a genuine design collision, open a tension/bead/issue — don't collapse silently.

### Worktrees

Parallel checkouts sharing `.git`. Useful for parallel feature work, isolated agent sessions, bisect without touching the working copy.

```bash
git worktree add ../repo-featureX feature/featureX
git worktree add -b feature/new ../repo-new
git worktree list
git worktree remove ../repo-featureX
```

Can't check out the same branch twice. Each worktree has its own HEAD/index; stashes are per-worktree.

### History archaeology

```bash
git log --oneline -20 <file>         # file history
git log --follow <file>              # across renames
git log -S '<string>' -- <path>      # pickaxe (string appeared/disappeared)
git log -G '<regex>' -- <path>       # pickaxe regex
git log origin/master..HEAD          # commits on branch not yet in master
git log --first-parent               # main-line only (aliased: git lg)
git blame -w <file>                  # ignore whitespace-only changes
git blame --first-parent             # skip merge commits (aliased: blamef)
git log -L <s>,<e>:<file>            # evolution of line range over time
git show <commit>:<path>             # contents at commit
```

**Reflog** saves you from bad rebases/resets — commits retained ~30 days after being unreferenced. `git reset --hard HEAD@{5}` to go back.

**Bisect** works because history is clean. `git bisect start; git bisect bad; git bisect good <old>; ...; git bisect reset`.

### Tags / releases

- Signed tags for releases: `git tag -s vX.Y.Z -m "..."`.
- Always annotated (`-a` or `-s`), never lightweight.
- Canonical version file matches the tag.
- Push with `git pst` (alias for `--follow-tags`).

### GitHub (`gh`) essentials

```bash
gh pr list --state merged --json number,title,body,mergeCommit
gh pr view <N> --json title,body,mergeCommit
gh pr view <N> --comments                  # top-level
gh api repos/<org>/<repo>/pulls/<N>/comments   # inline review comments
gh pr create --title "..." --body "$(cat <<'EOF' ... EOF)"
gh pr merge <N> --squash                   # include (#N) in --subject if overriding
gh pr checks <N>
gh issue list --state open --label <label>
```

### Stash / navigation

- Name stashes: `git stash push -m "desc"`. Unnamed stashes become mysteries.
- Don't stash long — if work deserves to survive a week, it deserves a branch.
- `git switch` (not `checkout`) for branches; `git restore` for files.

### Anti-patterns (tripwire list)

- Empty body on non-trivial commit; subject describing work-done not change-landed; vague nouns (`fix: stuff`).
- Claiming "unified"/"fixed"/"converged" when the diff doesn't support it.
- Multi-topic commits; mixed formatting + logic; committing unrelated sweeps silently.
- `git add -A` sweeping secrets/artifacts; `git commit -a` without review.
- `--no-verify` to bypass a failing hook; amending after hook failure.
- Pushing directly to `master` in PR-flow repos; "WIP:" PR titles that survive to merge; merging with red CI.
- Silently ignoring review comments; LGTM without reading; "CI will catch it" instead of running verify locally.
- Force-push without agreement; `-D` on unmerged branch; post-hoc squashing of merged history.
- Ceremonial "done!" without `file:line` citation or verification output.

### Interaction patterns (quick)

**Proactive or requested commit:** parallel `git status`/`diff --staged`/`diff`/`log --oneline -10` → review → draft intent-shaped message → stage by name → commit with heredoc → `git status` → push when the branch/repo workflow allows it → report `[git] N files — "<subject>"` plus push/PR state.

**PR:** parallel `status`/`diff`/`log origin/master..HEAD`/upstream-check → review full branch diff → push with `-u` if untracked → `gh pr create --title --body` (heredoc with Summary/Problem/Solution/Verification) → report URL.

**PR state check:** `gh pr view <N>` + `gh pr checks <N>` + `gh api .../pulls/<N>/comments` (inline) + `--comments` (top-level) → report state/CI/unresolved/next-action.

---
