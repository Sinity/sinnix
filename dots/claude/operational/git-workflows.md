## Git Workflows

Comprehensive protocol for working with git and GitHub across every repo. Project-specific extensions (verify commands, branch names, release procedures) belong in each project's CLAUDE.md / AGENTS.md / CONTRIBUTING.md; this file covers what applies everywhere.

### Why git history matters

`master` / `main` history is a **durable artifact** that outlives every conversation, issue, and review. Years later, three readers pick it up cold:

- **Future-you**, who has forgotten why a decision was made.
- **Future-agents**, who grep `git log` for context before editing.
- **`git bisect`**, when something regresses and you need to find when.

Every rule below exists because one of these readers fails when it's violated. A commit subject that says "feat: diagnose query misses" with no body teaches nothing to any of them — it's indistinguishable from `asdf`. The shape of these rules is: make the commit and PR carry enough context that a cold reader can reconstruct the change without external state.

Signals that make history navigable:

- **Conventional prefix** (`feat:` / `fix:` / …) — filterable with `git log --grep='^feat:'`; types carry semantic weight.
- **`(#N)` suffix** on squash-merges — clickable jump to PR discussion, review, issue chain, CI runs.
- **Non-empty body** — captures the *why* the diff can't show.
- **Coherent, specific subject** — reads as a change description, not a task-tracker label.
- **Intact PR boundary** — one commit on master = one logical change, reviewable in isolation.

Degradation compounds. One vague commit is noise; fifty is a lost quarter.

---

### Committing

#### When to commit

**Commit freely and proactively as work progresses.** Commits are local operations — version control working as intended. Blocking on user approval for every commit turns agents into something worse than `vim` with autosave off.

- **Commit each logical unit as it lands.** Feature branch, implementing a multi-step change: commit after each coherent step. Reviewer sees a clean progression; you can rebase-clean before PR. Losing an hour of changes to a bad edit because you were "waiting to commit" is the failure mode to avoid.
- **Don't wait to be asked.** "Implement X" implicitly authorizes commits on the feature branch — that's how X gets implemented. The user reviews via `git log` / `git diff`, not by pre-approving each commit.
- **Subject + body matter.** Proactive commits don't excuse lazy messages. Every commit this session gets written as if future-you will read it via `git blame` in two years (because they will).
- **Pushing is the explicit action.** `git push` / PR creation / merge touches shared state — those require explicit user request. Local commits don't.
- **Don't commit in the middle of a failing state** unless specifically marking an in-progress checkpoint. A commit that breaks the build poisons `bisect` forever. Either finish the change, stash, or label the commit `wip:` (and squash it before pushing).
- **Don't commit unrelated sweeps silently.** If you notice a typo in an unrelated file while working on feature X and fix it, that fix is a separate commit — don't bundle it into X's commit.

**Auto-commit is good; auto-push is not.** This distinction is load-bearing for everything below.

#### Atomicity — what "one logical change" means

**The test:** can you write a commit subject without "and"? If you need "and" to describe what's in the commit, split.

Concrete cases:

- **Bug fix + adjacent refactor** → two commits, refactor first (so the fix's diff is small and focused).
- **Multiple unrelated bug fixes** → one commit per bug, even if found in the same session.
- **Test + implementation** → one commit (they validate each other). Exception: spec-first TDD, where the failing test is a commit on its own to mark the contract.
- **Formatting sweep + logic change** → separate commits. Mixed formatting/logic diffs are unreviewable.
- **Renaming + behavior change** → rename first (pure rename, no semantic change), then the behavior change on renamed files.
- **Library upgrade + fixing its breaking changes** → one commit, because the upgrade isn't valid without the fixes. Note the breaking changes in the body.

When in doubt: err on the side of more commits on a feature branch. You can always squash on merge; you can't split post-hoc without rewriting.

#### Conventional commit types

Each prefix carries semantic weight — reviewers filter by type, `CHANGELOG` generators trigger on them, `git log --grep='^fix:'` finds all bug fixes. Pick accurately.

| Prefix | Meaning | Examples |
|---|---|---|
| `feat:` | User-visible new capability | `feat: add --json output to list command` |
| `fix:` | Bug fix; restores intended behavior | `fix: handle null cursor in paginated search` |
| `refactor:` | Internal restructure, no behavior change | `refactor: extract storage layer from CLI` |
| `perf:` | Optimization (include a measurement or explain why) | `perf: avoid O(n²) dedup in archive scan` |
| `test:` | Test-only changes | `test: add integration test for GDPR export path` |
| `docs:` | Documentation only (README, docstrings, comments) | `docs: document cache invariants in storage.py` |
| `chore:` | Tooling, deps, config, CI that doesn't fit `build:`/`ci:` | `chore: bump pytest to 8.x` |
| `build:` | Build system, packaging, release infrastructure | `build: add nix flake check to devtools verify` |
| `ci:` | CI configuration only | `ci: run mypy on pull_request not push` |
| `style:` | Formatting only, no semantic change | `style: apply ruff format across polylogue/` |
| `archive:` | Moving content to archive/ rather than deletion | `archive: move resolved stream/012 to archive/` |

**Boundary cases:**

- Refactor that happens to fix a latent bug → usually `fix:` (the user-visible effect is the fix). Note the refactor in the body.
- New feature that also refactors its area → `feat:` (the headline is the capability).
- Changing a test to match new behavior → `test:` only if the test infrastructure changed; otherwise the commit is the behavior change (e.g., `feat:` / `fix:`), and the test update is part of it.
- Deps bump that requires code changes → `chore:` if minor, `feat:`/`fix:` if the upgrade's effect is user-visible.

Use **scopes** (`fix(cli): ...`, `feat(storage): ...`) when the repo is large enough that scope adds clarity. Don't force scopes on small repos.

#### Subject line craft

The subject is the first (often only) thing future-you reads. Make it pull weight.

Rules:

- **≤72 chars** (hard limit — breaks `git log` formatting beyond this).
- **Present tense imperative.** "add X" / "fix Y" / "remove Z", not "added" / "fixing" / "removes".
- **Describes what *landed*, not what was *done*.** "feat: add query diagnostics for empty-result paths" beats "feat: diagnose query misses."
- **Specific nouns, not vague gerunds.** "fix: handle null cursor in pagination" beats "fix: pagination bug."
- **Name the subsystem** if not obvious from the diff. `fix(archive): ...` or `fix: archive — ...` when the repo spans many areas.
- **Don't repeat the prefix** in the body of the subject. "feat: add new feature" — "new feature" is redundant with "feat:".
- **No trailing period.** Subjects are phrases, not sentences.

Bad → good:

| Bad | Good | Why |
|---|---|---|
| `feat: diagnose query misses` | `feat: log empty-result query paths with inputs` | Specific, names the mechanism |
| `fix: stuff` | `fix: double-decode of UTF-8 BOM in exporter` | Concrete, names the bug |
| `refactor: cleanup` | `refactor: extract pagination helper from list endpoints` | Names what moved where |
| `chore: update` | `chore: bump ruff to 0.7.0, fix new lint warnings` | What + why |
| `feat: WIP` | (don't commit WIP to shared branches) | WIP is a branch state, not a commit |
| `Fix bug` | `fix: reject NaN in stats aggregation` | Prefix + imperative + specific |

#### Body craft

Required for anything non-trivial. Skip only for self-documenting changes (typo fix, whitespace, pure formatting pass).

**Four sections worth writing, not all always required:**

1. **Problem / motivation** — what observation, bug, constraint, or design pressure triggered the change. Not "because the user asked" unless that truly was the only driver.
2. **What changed, in prose** — at higher level than the diff: key modules touched, contract changes, new invariants.
3. **Alternatives considered and rejected** — only if there was a real fork in the road. Captures the *why not* that's otherwise lost.
4. **Compatibility / migration** — breaking changes, deprecations, schema migrations, config changes that users must apply.

**Body conventions:**

- **Blank line between subject and body** (git parses this).
- **Wrap prose at 72 chars.** Makes `git log` readable.
- **Bullet lists are fine** — use for enumerating changes in a larger commit.
- **Breaking changes** get their own line in the footer: `BREAKING CHANGE: <description>`. Conventional Commits tools detect this.
- **Issue references** belong in the body: `Closes #123`, `Ref #456`. Not in the subject.
- **Co-author trailer** at the very bottom:
  ```
  Co-Authored-By: Claude <noreply@anthropic.com>
  ```

**Example of a body-less commit that should have had one:**

```
feat: diagnose query misses
```

Better:

```
feat: log empty-result query paths with inputs

When a search returns zero results, previously the path was silent —
users reported "search is broken" when in fact the query was invalid
(wrong archive slug, expired token). Log now captures: query text,
provider, time range, and archive filter at DEBUG level. Opt-in via
POLYLOGUE_DEBUG=1 to avoid polluting default logs.

Closes #342

Co-Authored-By: Claude <noreply@anthropic.com>
```

Future-you reads this in six months and immediately knows: what was broken, what was changed, how to enable the new behavior, what issue tracked it.

#### Staging

- **By name.** `git add <file>` / `git add <dir>/`. Never `git add -A` / `git add .` / `git commit -a` for significant changes — these sweep in `.env`, credentials, editor swap files, build artifacts, `AGENTS.md` renders.
- **Review before commit.** `git diff --staged` shows exactly what will be committed.
- **Partial files** with `git add -p` when you want only some hunks of a file. Better than splitting changes across multiple working copies.
- **Never commit** secrets (`.env`, tokens, keys), large binaries, compiled output, IDE state, OS cruft (`.DS_Store`, `Thumbs.db`). Use global `.gitignore` (`~/.config/git/ignore_global`, configured via `core.excludesFile`) for OS/editor junk; per-project `.gitignore` for repo-specific ignores.

#### Hooks and verification

- **Never skip hooks.** No `--no-verify`, `--no-gpg-sign`, `-c commit.gpgsign=false` unless explicitly requested. If a pre-commit hook fails, fix the root cause — bypassing hooks is how broken code lands on master.
- **Hook failure = no commit.** The commit did not happen. Do **not** `--amend` afterward — that would modify the *previous* (successful) commit. Fix the issue, re-stage, create a new commit.
- **Hooks enforce the floor**, not the ceiling. Passing hooks means "didn't break lint/format/tests" — it doesn't mean "the change is good." Reviewer + verification baseline cover the rest.

#### Signing

`user.signingkey` is set globally but `signByDefault = false`. When to sign:

- **Release tags** — always sign (`git tag -s vX.Y.Z`).
- **Feature commits** — project-dependent. Check repo convention.
- **Identity-sensitive commits** — when author verification matters (security fixes, author attribution disputes), sign.

---

### Branching

#### Workflow shape

- **All code lands via PRs** targeting the default branch (`master` or `main`). No direct commits to default — even on solo repos, the PR flow is what makes `(#N)` suffixes, review surface, CI gating, and history navigation work.
- **Feature branches start from `origin/master` / `origin/main`**, not from stale local state. `git fetch --all` first.
- **One branch = one logical unit of work.** When the branch's scope grows beyond that unit, either (a) tighten the PR and move extra work to a follow-up branch, or (b) acknowledge the stacked structure explicitly.

#### Naming convention

`feature/<category>/<short-description>`, where category is one of the conventional prefixes (`feat` / `fix` / `refactor` / `perf` / `test` / `docs` / `chore`).

Examples:

- `feature/feat/mcp-query-exports`
- `feature/fix/parser-null-guard`
- `feature/refactor/storage-product-splits`
- `feature/chore/bump-ruff-0.7.0`

**Dashes not underscores** in the description. **Lowercase** throughout. **Avoid dates, initials, ticket numbers** in the branch name — those belong in commits / PR body.

#### Iteration on the branch

Branch commits can be rough while working — "wip", "try this", "ugh forgot tests" is fine *pre-push*. But the **published branch** (what a reviewer sees) should tell one coherent story.

Before opening the PR:

```bash
git fetch origin
git rebase origin/master   # or: git tidy (aliased to 'rebase -i @{upstream}')
```

`git tidy` opens an interactive rebase where you can:

- **squash** fixup commits into their parents (`rebase.autoSquash = true` auto-organizes `fixup!` / `squash!` commits).
- **reword** subjects that no longer match what landed.
- **reorder** commits into a logical progression.
- **drop** commits that were reverted later in the branch.

After cleaning: `git push --force-with-lease` to the branch (safe on your own feature branch — `--force-with-lease` refuses if someone else pushed concurrently).

#### Rebasing vs merging

Global config sets `pull.rebase = true` and `rebase.autoStash = true`: `git pull` already rebases, stashing uncommitted changes across the rebase. No merge commits from routine syncing.

- **Rebasing feature branch onto updated `master`:** fine, expected — keeps branch linear against fresh base.
- **Rebasing default branch:** never. Default branch is the canonical spine.
- **Merge commits on feature branch:** avoid — adds noise to the eventual squash-merge body.
- **Merge from `master` into feature branch** (instead of rebase): avoid — pollutes branch history with merge commits. Rebase instead.

---

### Pull Requests

#### Issue-first for non-trivial work

Open a GitHub issue **before** starting work when any of these apply:

- Work spans multiple PRs.
- Introduces architectural decisions (new module, major abstraction, cross-system contract).
- Bug report that needs a repro record or acceptance criteria.
- Architectural or research question with no clear answer yet.
- Follow-up chain that will span more than one PR.
- Durable unresolved debt discovered mid-implementation (convert to tracked debt).

**Skip** the issue when the change is self-contained and the PR body itself is sufficient record.

**Convert anonymous debt into tracked debt** — this is the non-obvious rule. When you discover during implementation:

- An expected-failure test representing a real bug not in scope,
- A TODO comment that will persist beyond this PR,
- A warning or degraded behavior accepted for scope reasons,
- Follow-up work mentioned in PR text or scratch notes —

**open an issue for it** and reference the issue from the test / comment / PR body. Anonymous TODOs rot; tracked debt gets addressed.

When opening an issue: outcome + constraints + acceptance criteria. Not a task description.

#### PR size and review economy

Reviewer attention is finite. Size affects review quality:

- **Ideal: 200–400 LOC diff.** Reviewer holds the whole change in working memory.
- **400–1000 LOC:** acceptable with clear structure. Include a "read this order" hint in the PR body if multi-file.
- **>1000 LOC:** either break into stacked PRs, or accompany with an explicit "review commit-by-commit" instruction and self-review pass first.
- **<50 LOC:** fine if genuinely atomic. If it's trivially small *and* there are three other 30-LOC changes in flight touching adjacent code, consider bundling to save overhead.

Size rules of thumb conflict with granularity rules; the resolution is that **PR = one logical change**, and if a logical change is big, it's stacked, not crammed or split-mid-logic.

#### Stacked PRs

When one logical change is too big for a single reviewable PR:

- Branch each stack level off the previous: `branch1 → branch2 (off branch1) → branch3 (off branch2)`.
- Each PR targets the branch below it (not master).
- Merge **bottom-up**. Each merge rebases the subsequent PRs' bases (GitHub does this automatically if branches are tracked correctly).
- When the base moves (e.g., branch1 merges to master), rebase branch2 onto master: `git fetch && git rebase origin/master`.
- **Tooling:** `gh pr create --base <previous-branch>`.

Stacked PRs require discipline — they fail when agents edit multiple stacks in parallel without coordination. If you're unsure: open one big PR with "review commit-by-commit" rather than risk stack rot.

#### PR title = permanent history line

The PR title becomes the **squash-merge commit subject on `master`**. It's not a work-in-progress label. Write it as the history line you want.

"WIP: refactoring storage" → not a valid PR title at merge time. Rename before merging.

**Rules for the PR title (= squash-merge subject):**

- **≤72 chars.**
- **Conventional prefix** (`feat:` / `fix:` / etc., matching the same vocabulary as commits).
- **Describes what changed**, not what was worked on.
- **Ends with `(#N)`** — the PR number. This is the lever that makes `master` history navigable back to PR discussion, reviews, and linked issues.
- **Accurate.** Do not claim the change is "aligned" / "unified" / "converged" / "complete" / "fixed" unless the diff actually achieves it. An inaccurate claim in a commit subject poisons future greps — someone searching for "unified X" finds your commit, looks at the diff, and discovers only half of X was unified. Worse than silence.

Write titles for the reader who will find them two years from now via `git log --oneline`.

#### PR body discipline (= squash-merge body)

The PR description becomes the commit body on default branch. An empty body — or a body that's just "fixes #123" with no prose — is a failure mode.

**Required sections** (adapt to project template if one exists):

- **Summary.** One paragraph. What landed. Written for someone reading `git show <squash-commit>` cold.
- **Problem.** Why the work was necessary. The evidence that motivated it — repro steps, observed bug, user-visible symptom, benchmark, design constraint, compliance requirement. Not "because the user asked" unless that genuinely was the only trigger.
- **Solution.** What was done. Key modules and contracts touched. Non-obvious decisions. What alternatives were considered and why rejected.
- **Verification.** **Exact commands run.** Not "tests pass." Paste the command (`pytest tests/test_foo.py -v`), the output line that matters, or name the invariant verified. This distinguishes "I ran the tests" from "I typed the PR body without running the tests."

Optional but valuable:

- **Migration notes** — if users must do something on upgrade.
- **Follow-ups** — issue links for anonymous debt converted to tracked debt during this PR.
- **Breaking changes** — explicit callout if the change affects consumers.

**Link issues** in the body:

- `Closes #N` / `Fixes #N` / `Resolves #N` — auto-closes issue on merge. Use when PR fully addresses the issue.
- `Ref #N` / `Related-to #N` — cross-reference without closing. Use when PR partially addresses or just touches related area.

Put these in the body, not the subject. GitHub parses both, but subjects are already tight for size.

#### Claim verification — grep the diff before asserting

Before writing a PR body or commit message that claims alignment / unification / convergence / completion / fix:

1. **Grep the diff for duplicated logic.** If you claim "unified into one helper," search: is the old helper actually gone? Or did the new one get added next to the old one?
2. **Check both paths.** If claiming a refactor eliminated a split, verify every call site now uses the unified path.
3. **Read the PR's own diff on GitHub**, not just the local diff. GitHub's view sometimes shows things local `git diff` misses (merge conflicts, force-push artifacts).
4. **If the claim doesn't hold, revise the claim** — not the code. "Partially unified" is a valid description; "unified" when it's half-done is a lie.
5. **Test the claim.** If the PR claims "fixes issue #123," the PR's verification section should show the repro from #123 now passing.

---

### Squash-merge hygiene

#### The `(#N)` suffix

GitHub's squash-merge UI, when set to "Default commit message: Pull request title and description," auto-appends `(#N)` to the subject and copies the PR body as the commit body. When this setting is on and no one overrides it, hygiene happens by default.

Two bypass paths that cause drift:

1. **Agent runs `gh pr merge <N> --squash` with custom `--subject`/`--body` flags.** The default is bypassed; `(#N)` is *not* auto-appended. Agent must supply it manually.
2. **Agent runs `gh pr merge` without flags but the repo setting is on "Default to pull request title" (which omits body) or "Commit message by contributors"** — body may be lost or subject may lack `(#N)`.

**Enforcement options** (configure once per repo):

- **GitHub Ruleset** (Repository → Settings → Rules → Rulesets) requiring commit subject to match `.*\(#\d+\)$` on default branch. Rejects non-compliant merges at the server side.
- **Repo setting** "Default commit message" → "Pull request title and description" ensures the UI default is correct.
- **Commit-commands plugin** (local, `commit-push-pr`) can be hardened to always pass `-t "$(gh pr view $PR --json title -q .title) (#$PR)"`.

Belt-and-suspenders: enable ruleset (server-side) and set default commit message (UI default). Agents following either path get correct output.

#### Granularity — forward policy, not post-hoc

**Prefer fewer, fatter PRs.** Heuristic: if two PRs would share a reviewer concern and be reviewed in one sitting, they should be one PR.

**Why forward-only:** post-hoc combining destroys PR boundaries. Interactive-rebasing `master` to combine three squash-merges into one leaves three orphaned PR records (each pointing to a now-unreachable merge commit) and a new commit with no canonical PR. History becomes *less* structured, not more. Granularity must be fixed at PR-open time.

**Inverse trap:** cramming unrelated changes into one PR is equally bad — if a reviewer would ask "why are these together?", split.

**When you notice granularity drift mid-session** (e.g., agents opening 5 tiny PRs for adjacent changes): pause, ask the user, bundle on the branch before merging rather than after.

#### Rewriting degraded history — when and how

When past commits lack `(#N)` / have empty bodies / are otherwise degraded, and the user decides to fix it:

**Scope check first:**

- Solo repo with no external SHA-pinned links? Rewrite cost is near zero.
- External docs / blogs / wiki link to specific `github.com/org/repo/commit/<SHA>`? Those break. PR pages survive (identified by number, not SHA).
- Other agents / humans actively working the repo? Force-push disrupts their clones. Ask / wait.

**Reconstruction sources** (the data you need is still there):

- **PR metadata on GitHub** — `gh pr list --state merged --json number,title,body,mergeCommit,mergedAt` gives title + body + the squash-commit SHA for every merged PR. You can regenerate each degraded commit's message from this.
- **Issue cross-refs** — `gh issue list --state all --json number,title,body,closedAt` if you want to enrich with issue context.

**Rewrite tooling:**

- **`git filter-repo --commit-callback`** is the modern, correct tool. Walks every commit; you supply a Python callback that rewrites message/author/etc. Prefer over `git filter-branch` (deprecated, slow, footgun-heavy).
- **`git rebase -i --exec`** works for smaller scopes when you can enumerate commits manually.

**Safety protocol:**

1. Back up: `git branch backup-master-pre-rewrite` before starting.
2. Test on a clone: `git clone --mirror . /tmp/rewrite-test`, run filter-repo there, inspect output.
3. Confirm with user before force-pushing.
4. Force-push with `--force-with-lease`, not `--force` (refuses if anyone pushed in the meantime).
5. Tell others to re-clone (not rebase onto the new history — gets messy).

**Local-only rewrites** (commits not yet pushed) are always safe: `git rebase -i`, `git commit --amend`, `git commit --fixup`. Force-push-with-lease to your own feature branch is also safe in practice.

---

### Repository settings

These live in GitHub's repo settings, not in the code. Set once per repo:

- **Branch protection** on default branch: require pull requests, prevent direct pushes.
- **Required status checks** before merge: CI, linters, whatever the project runs.
- **Squash merge only.** Disable merge commits and rebase-merges. Squash is the canonical flow for PR→master.
- **Default commit message:** "Pull request title and description" (auto-appends `(#N)` and copies PR body).
- **Auto-delete head branches** after merge — keeps the branch list clean.
- **Allow "Update branch"** for stale PRs — lets the UI rebase the PR onto a new base without leaving the browser.
- **Do not require an issue for every PR** — many PRs are self-contained.
- **Ruleset for commit message format** (optional but recommended): subject regex `^(feat|fix|refactor|perf|test|docs|chore|build|ci|style|archive)(\([^)]+\))?: .+ \(#\d+\)$`. Enforces prefix + subject + `(#N)`.

---

### Destructive & hard-to-reverse operations

These require **explicit confirmation** even in auto mode:

- `git reset --hard` on a branch with uncommitted changes (overwrites work).
- `git push --force` on any branch (rewrites remote history; `--force-with-lease` is preferred when force-push is justified).
- `git push --force-with-lease` on a **shared branch** (still rewrites; less dangerous but still disruptive).
- `git branch -D` on an unmerged branch (loses commits).
- Amending a commit that's already been pushed (`--amend` + force-push).
- `git rebase` that rewrites published history.
- `git filter-repo` / `git filter-branch` on any branch.
- Deleting branches, worktrees, stashes, or tags.
- `git clean -fd` (deletes untracked files; can destroy work-in-progress).

**State specifically** what will happen:

> Confirming: about to force-push master after rewriting 47 commits to add (#N) suffix and regenerate bodies from PR descriptions. This rewrites SHAs — old `/commit/<SHA>` links will break, but PR pages survive (identified by number). Backup branch `backup-master-pre-rewrite` is in place. Proceed?

**Never force-push to shared branches without agreement.** Solo repos have low operational cost for force-push, but the confirmation cost is lower — always ask.

**Never push to `master` / `main` directly.** The PR flow is the enforcement surface for every other rule in this document.

#### Force-push alternatives

Before reaching for force-push, ask if a non-destructive path achieves the goal:

- **Amend just-pushed commit to your own feature branch** → `--force-with-lease` is acceptable. Feature branch is yours; lease check prevents overwriting concurrent pushes.
- **Fix typo in most-recent commit message on master** → *don't*. Live with the typo, or open a follow-up commit that notes it. History is not worth rewriting over a typo.
- **Add missing `(#N)` to a just-merged squash commit** → don't. Fix the process (ruleset, default commit message setting) and accept the one miss. Rewriting one commit's SHA isn't worth the cascade.
- **Reorder commits on a shared feature branch** → coordinate with others first.
- **Bulk-fix a span of degraded history** → confirm explicitly with user; run the full rewrite protocol above.

---

### Merge conflicts

- **Investigate before resolving.** Read both sides. Conflicts exist because two changes disagree about the same region — figure out which wins, or if they compose.
- **Don't auto-prefer `theirs` / `ours`.** That's not resolution, it's picking sides unread.
- **`conflictStyle = zdiff3`** is set globally — shows the common ancestor alongside the two conflicting versions. Use the ancestor to understand the original intent.
- **If the conflict reveals a genuine design collision** (both sides made the same decision differently), surface it rather than collapsing silently. Open a tension / decision / issue as appropriate.
- **Test after resolving.** Run the project's verify command — conflict resolution commonly introduces subtle bugs that compile but behave wrong.

---

### Post-merge cleanup

After a branch merges:

- **Delete local branch.** `git branch -d <name>` (lowercase `d` — refuses if unmerged, safer than `-D`). The `cleanup` alias (`git cleanup`) removes all merged branches in one shot.
- **Clean `[gone]` branches.** The `commit-commands:clean_gone` plugin command removes local branches whose remote is deleted, plus associated worktrees.
- **Fetch-prune** removes stale remote-tracking refs. `fetch.prune = true` is set globally, so `git fetch` prunes automatically.
- **Close associated issues** if the PR didn't auto-close them (`Closes #N` in PR body handles this).

---

### Worktrees

`git worktree add` creates a second checkout of the same repo at a different branch, sharing the `.git` directory. Relevant for the multi-agent architecture (`wiki/coding-agent-architecture.md`):

- **Parallel feature work** — one worktree per branch, no branch-switching overhead, no stashing across contexts.
- **Isolated agent sessions** — each worker agent gets its own worktree so simultaneous edits don't collide.
- **Bisect without disturbing working copy** — bisect in a secondary worktree.

Commands:

```bash
git worktree add ../repo-featureX feature/featureX   # new worktree on existing branch
git worktree add -b feature/new-branch ../repo-new   # new branch + worktree
git worktree list                                     # show all worktrees
git worktree remove ../repo-featureX                  # delete (branch unaffected)
git worktree prune                                    # clean up after directory deletion
```

**Gotchas:**

- Can't check out the same branch in two worktrees simultaneously.
- Each worktree has its own HEAD and index; stashes are per-worktree (not shared).
- `git-lfs` filters may need per-worktree setup.

---

### History archaeology

Techniques for understanding unfamiliar code's history — before editing, during debugging:

**`git log` variations:**

```bash
git log --oneline -20 <file>                  # recent history of one file
git log -p <file>                             # full diff history of one file
git log --follow <file>                       # follow across renames
git log -S '<exact-string>' -- <path>         # pickaxe: when did this string appear/disappear
git log -G '<regex>' -- <path>                # like -S but regex
git log --author=<name>                       # commits by author
git log --since='2 weeks ago' --until='1 week ago'
git log origin/master..HEAD                   # commits on current branch not yet in master
git log --first-parent                        # main-line only, ignore feature-branch detail
git lg / git lgg                              # aliased first-parent pretty-log
git review                                    # commits vs upstream (alias)
```

**Blame and attribution:**

```bash
git blame <file>                              # line-by-line authorship
git blame <file> -L <start>,<end>             # only a range
git blame -w <file>                           # ignore whitespace-only changes (better attribution)
git blame --first-parent                      # skip merge commits (aliased 'blamef')
git log -L <start>,<end>:<file>               # evolution of a line range over time
```

**Point-in-time:**

```bash
git show <commit>                             # diff + message of one commit
git show <commit>:<path>                      # contents of file at commit
git diff <commit1>..<commit2> -- <path>       # difference between two commits
```

**Matching commits to PRs:**

- Squash-merge commits with `(#N)` suffix → `gh pr view <N>` shows the full PR discussion.
- Commits without `(#N)` → try `git log --grep='feat:'`, then `gh pr list --search "<subject>"` to find the PR.

**Reflog — the safety net:**

```bash
git reflog                                    # every HEAD move for ~30 days
git reflog <branch>                           # reflog of a specific branch
git reset --hard HEAD@{5}                     # reset to state 5 moves ago
```

Reflog saves you from `reset --hard`, bad rebases, deleted branches — commits are retained ~30 days even after being unreferenced.

**Bisect — regression hunting:**

```bash
git bisect start
git bisect bad                                # current HEAD is bad
git bisect good <old-working-commit>          # name a known-good commit
# git checks out midpoint; test it; then:
git bisect good  # or: git bisect bad
# repeat until bisect finds the culprit
git bisect reset
```

Bisect works because history is clean (enforced by rules above). Noisy history makes bisect useless.

---

### Stash discipline

- **Always name stashes.** `git stash push -m "description of what's stashed"`. Unnamed stashes become mysteries within days.
- **Don't stash for long.** Stash is ephemeral — if work deserves to survive a week, it deserves a commit on a branch.
- **`git stash show -p <ref>`** before popping, to confirm you're applying the right stash.
- **`git stash list`** periodically to audit what's outstanding.
- **`git stash drop <ref>`** to explicitly clean up a stash that's obsolete.

---

### Tags and releases

- **Signed tags for releases:** `git tag -s vX.Y.Z -m "Release vX.Y.Z"`. Signature proves authorship.
- **Annotated tags, not lightweight:** always `-a` or `-s` (never just `git tag vX.Y.Z`). Annotated tags carry message + author; lightweight tags are bare refs.
- **Version in a canonical file** (`pyproject.toml`, `Cargo.toml`, `package.json`, etc.) matches the tag. Bump + tag are separate commits per the project's release procedure.
- **Push tags explicitly:** `git push --follow-tags` (aliased `git pst`) — pushes annotated tags reachable from pushed commits.
- **`fetch.prune = true`** doesn't prune tags. `git fetch --prune-tags` if you need to remove deleted upstream tags.

---

### Commands reference

#### Inspection

- `git status` — never `-uall` on large repos (memory issues).
- `git diff` / `git diff --staged` — word-diff by default (aliased `d`).
- `git diff --stat` — summary of what changed.
- `git log --oneline -10` — recent commits.
- `git lol` / `git lola` — pretty graph log (aliased).
- `git lg` / `git lgg` — first-parent log (master history only).
- `git review` — commits on current branch vs upstream.
- `git incoming` / `git outgoing` — what will be pulled / pushed.
- `git show <commit>` — a specific commit's diff.

#### GitHub (`gh`)

- `gh pr list --state merged --json number,title,body,mergeCommit` — bulk PR data for history reconstruction.
- `gh pr view <N>` — inspect a PR.
- `gh pr view <N> --json title,body,mergeCommit` — scriptable fields.
- `gh pr view <N> --comments` — top-level PR comments.
- `gh api repos/<org>/<repo>/pulls/<N>/comments` — inline review comments.
- `gh pr create --title "..." --body "$(cat <<'EOF' ... EOF)"` — heredoc preserves formatting.
- `gh pr merge <N> --squash` — squash-merge; supply `--subject` and `--body` to override defaults. Always include `(#N)` in `--subject` if overriding.
- `gh pr checks <N>` — CI status.
- `gh issue create --title "..." --body "$(cat <<'EOF' ... EOF)"` — heredoc for multi-line issue body.
- `gh issue list --state open --label <label>` — filter issues.

#### Rewrite (local, pre-push only unless confirmed)

- `git rebase -i @{upstream}` (aliased `git tidy`) — interactive rebase on unpushed work.
- `git commit --amend` — only on unpushed commits.
- `git commit --fixup <SHA>` / `git commit --squash <SHA>` — auto-organize during next rebase (`rebase.autoSquash = true`).
- `git filter-repo --commit-callback` — bulk history rewrite (destructive; confirm with user).

#### Navigation

- `git switch <branch>` — check out a branch (preferred over `checkout` for branch switching).
- `git switch -c <branch>` — create + switch.
- `git restore <file>` — discard unstaged changes (preferred over `checkout -- <file>`).
- `git restore --staged <file>` — unstage without losing changes.

---

### Interaction patterns

#### Making a commit (proactive or on request)

Same procedure whether the commit is part of ongoing implementation or the user explicitly asked:

1. Run in parallel: `git status`, `git diff --staged`, `git diff` (unstaged), `git log --oneline -10`.
2. Review what's staged and unstaged. Match commit vocabulary to repo convention (look at recent `git log`).
3. Decide the boundary: is this one logical change, or should it be split? Can the subject be written without "and"?
4. Draft intent-shaped message: prefix + subject + body (if non-trivial) + Co-Authored-By trailer.
5. Stage by name (`git add <files>`), never `git add -A`.
6. Commit with heredoc:
   ```bash
   git commit -m "$(cat <<'EOF'
   feat: add query diagnostics for empty-result paths

   Problem: silent on zero-result queries made debugging hard.
   Solution: log query + provider + time range at DEBUG.

   Closes #342

   Co-Authored-By: Claude <noreply@anthropic.com>
   EOF
   )"
   ```
7. `git status` to verify.
8. Report: `[git] N files — "<subject>"`.
9. **Do not push** without a separate explicit request.

#### User requests a PR

1. Run in parallel: `git status`, `git diff`, `git log origin/master..HEAD`, check upstream tracking (`git rev-parse --abbrev-ref @{upstream}` or parse `git status`).
2. Review the full branch diff (not just latest commit) to understand what PR will contain.
3. Push with `-u` if branch isn't tracked remotely.
4. `gh pr create` with heredoc body:
   ```bash
   gh pr create --title "feat: add query diagnostics for empty-result paths" --body "$(cat <<'EOF'
   ## Summary
   …

   ## Problem
   …

   ## Solution
   …

   ## Verification
   - [x] `devtools verify` (green)
   - [x] `pytest tests/test_query.py -v` (all 12 tests pass)

   Closes #342

   🤖 Generated with [Claude Code](https://claude.com/claude-code)
   EOF
   )"
   ```
5. Report the PR URL.

#### User asks to check a PR's state

- `gh pr view <N>` — overall state.
- `gh pr checks <N>` — CI status.
- `gh api repos/<org>/<repo>/pulls/<N>/comments` — inline review comments (the detailed feedback).
- `gh pr view <N> --comments` — top-level comments.
- Report: state, CI green/red, unresolved comments, next action.

#### User requests history rewrite

1. **Clarify scope** — span of commits, what's being fixed (message format, `(#N)` suffix, body).
2. **Assess blast radius** — solo repo? External SHA links? Other agents active? Report.
3. **Propose the rewrite** — specific commits, specific transformation, tool (`git filter-repo` usually).
4. **Dry-run** on a clone if scope is large.
5. **Confirm** before force-push.
6. **Force-push with `--force-with-lease`.**
7. **Verify** PR pages / issue links still resolve.

---

### Anti-patterns (failure-mode catalogue)

Read this list when you notice yourself about to do one:

**Commit subject / body:**

- Empty or trivial body on a non-trivial change (`feat: diagnose query misses` with no explanation).
- Subject describing what was worked on, not what landed (`feat: pagination work`).
- Subject that repeats prefix redundantly (`feat: add new feature`).
- Claiming "unified" / "fixed" / "converged" without the diff supporting it.
- Missing Co-Authored-By trailer on agent-authored commits.
- Subject >72 chars (breaks `git log`).
- Past-tense subject (`feat: added X` instead of `feat: add X`).
- Vague nouns (`fix: stuff`, `chore: cleanup`, `refactor: improvements`).

**Commit granularity:**

- Multi-topic commits ("feat: add X, also fix Y, also refactor Z").
- Formatting sweep bundled with logic change (unreviewable diff).
- "Final final" or context-free messages on branch commits.
- Committing unrelated work together because "they happened in the same session."

**Staging:**

- `git add -A` sweeping in secrets, build artifacts, editor files.
- `git commit -a` on a large diff without review.
- Committing `.env`, credentials, tokens, large binaries, compiled output.

**Hooks:**

- `git commit --no-verify` to bypass pre-commit.
- Amending after hook failure (modifies previous commit, doesn't make failed commit happen).

**Branching / PR flow:**

- Pushing directly to `master` / `main`.
- Opening PR with "WIP:" title and forgetting to rename.
- Merging with red CI.
- Merging without filling PR body sections.
- Merging without `(#N)` in squash subject.

**Review discipline:**

- Silently ignoring review comments.
- "LGTM"-ing changes without reading.
- Not running verification before PR ("CI will catch it").
- Claiming tests pass in PR body without having run them.

**Destructive:**

- Force-push without agreement.
- `git reset --hard` with uncommitted changes.
- `git rebase` onto default branch.
- `git branch -D` on unmerged branch without confirming.
- Amending a pushed commit and force-pushing without explicit approval.

**History:**

- Post-hoc squashing of squash-merges (destroys PR boundaries).
- Rewriting published history without confirmation.
- Rewriting to "fix" a typo at the cost of breaking external SHA links.
- Not backing up before `filter-repo`.

**Coordination:**

- Force-pushing another agent's in-flight branch.
- Rebasing a shared branch everyone else is based on.
- Stashes left unnamed for weeks.

**General:**

- Ceremonial completion claims ("Done!" without citing `file:line` or verification).
- Stubs committed silently (user must know if partial).
- Agreeing-with-canonical-text instead of stress-testing (see `wiki/working-methodology.md` on rejection-based design).
