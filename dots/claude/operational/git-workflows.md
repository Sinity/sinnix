## Git Workflows

Universal git/GitHub protocol. Project-specific extensions go in each repo's CLAUDE.md / CONTRIBUTING.md.

### History is durable

`master` / `main` is a permanent artifact. Three readers pick it up cold — future-you, future-agents, `git bisect` — and all fail when a commit subject is `asdf`, the body is empty, or the PR boundary is lost. Every rule below exists so those readers succeed.

Navigable signals: conventional prefix (`feat:`/`fix:`/...), `(#N)` suffix on squash-merges, non-empty body, specific subject, one-logical-change-per-PR.

---

### Committing

**Commit freely and proactively.** Commit each logical unit as it lands on a feature branch — don't wait to be asked. Pushing is the explicit action; local commits are not.

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
- Don't repeat the prefix verbosely (`feat: add new feature` is redundant)

**Body (required for anything non-trivial):**

- Blank line between subject and body; wrap at 72 chars
- Four sections worth writing (not all always required): **Problem** (what observation/constraint triggered this), **What changed** (higher level than the diff), **Alternatives rejected** (only if there was a real fork), **Compatibility/migration** (breaking changes)
- Issue refs in body: `Closes #N`, `Ref #N`
- `BREAKING CHANGE: ...` footer for breaking changes (Conventional Commits detect it)
- Co-author trailer:
  ```
  Co-Authored-By: Claude <noreply@anthropic.com>
  ```

**Staging:** by name (`git add <file>`). Never `git add -A` / `git commit -a` on significant changes — sweeps in `.env`, credentials, build output. Review with `git diff --staged` before commit.

**Hooks:** never skip (`--no-verify`, `--no-gpg-sign`) unless the user explicitly asked. Hook failure = no commit; fix the root cause and make a NEW commit (don't `--amend` — that modifies the previous successful commit).

---

### Branching

- **All code lands via PRs** to default. No direct pushes to `master`/`main` — the PR flow enforces `(#N)`, reviews, CI gating, history navigability. Even on solo repos.
- **Feature branches start from fresh `origin/master`.** `git fetch --all` first.
- **Name:** `feature/<type>/<short-dash-separated-desc>` (lowercase, no dates/initials/ticket-nums in branch names — those go in commits/PR body).
- **Rebase, don't merge** when syncing feature branches from master. Global config sets `pull.rebase = true` and `rebase.autoStash = true`.
- **Before opening PR:** `git tidy` (interactive rebase on upstream) to squash fixups, reword subjects, reorder, drop reverted work. Then `git push --force-with-lease` (refuses if someone else pushed concurrently).

---

### Pull Requests

**Open an issue first** for: work spanning multiple PRs, architectural decisions, bug reports needing repro, research questions, follow-up chains, durable debt discovered mid-implementation. Skip for self-contained PRs where the body is sufficient record.

**Convert anonymous debt into tracked debt.** When you discover an expected-failure test, a persistent TODO, or out-of-scope work: open an issue and reference it from the code/PR. Anonymous TODOs rot.

**Issue comments are part of the spec.** Before implementing an issue, read the
full issue thread, not only the body. Later comments may supersede, narrow,
correct, or expand the body, and can be more important than the original
description. If the body and comments conflict, preserve the evidence in your
own issue/PR comment and state the interpretation you are implementing.

**Leave an implementation trail.** Agents working an issue should comment with:
their understanding of scope; important constraints or non-goals; what they
changed; what they intentionally did not change; acceptance criteria satisfied,
deferred, or found misframed; verification run; and follow-up issues opened.
Use PR comments when the work is already in review and issue comments when the
understanding changes the durable issue record. Do not let meaningful research,
scope decisions, or discovered drift survive only in chat or scratch notes.

**PR size and shape:** prefer substantial, cohesive PRs over micro-PRs that
burn CI/review cycles. A good PR may contain multiple atomic commits while it is
in review, then squash to one permanent master commit. Size the PR around a
complete issue slice or coherent implementation phase, not around one rename,
one helper, or one mechanical substep. Tiny PRs are appropriate only for urgent
fixes, risky isolated changes, or when a larger branch would mix unrelated
concepts. If a slice is large but coherent, keep it as one PR with a read order,
self-review notes, and focused commits; stack only when independent review
boundaries or merge ordering actually help.

**Issue phase batching:** when an issue has several adjacent acceptance criteria
that touch the same subsystem, keep them on one branch until the coherent phase
is exhausted. Use multiple commits as review waypoints, not multiple PRs by
default. Before opening a PR, update the issue/PR narrative with a compact
matrix: satisfied, intentionally deferred, misframed, and still open. If that
matrix would show only a tiny fraction of the phase satisfied, keep working
unless risk or reviewability genuinely argues for a smaller PR.

**Verification cadence:** do not run the slowest gate after every small edit.
During implementation, run the narrow command that proves the changed behavior
plus cheap static checks. Run the broad local gate once when the phase is ready
to publish, again only after material changes to the tested surface or after a
failure fix. If a broad suite exposes an unrelated flaky/pre-existing failure,
rerun the exact node to classify it, record the evidence, and avoid turning the
current PR into an unrelated cleanup unless the fix is necessary and local.

**CI/review economy:** don't wait passively on known-quota or known-slow CI when
local gates and required impact reports already give enough evidence for the
next action. Inspect substantive bot comments and proof reports, but classify
rate limits, pending capacity, and tool failures quickly instead of letting them
stall implementation. Green checks are not a substitute for reading substantive
comments; pending known-capacity checks are not a reason to burn more local or
agent cycles without a new signal.

**PR title = squash-merge subject.** Write it as the permanent history line:

- ≤72 chars, conventional prefix, imperative, describes what changed
- Ends with `(#N)` — clickable jump back to PR discussion
- Accurate: don't claim "unified"/"aligned"/"fixed" unless the diff actually achieves it

**PR body = squash-merge body.** Required sections: **Summary** (one para), **Problem** (evidence/motivation — not "user asked"), **Solution** (modules touched, non-obvious decisions, rejected alternatives), **Verification** (exact commands run + output line that matters, not "tests pass"). Optional: Migration notes, Follow-ups, Breaking changes. Link issues in body (`Closes #N` auto-closes).

**Claim verification — grep the diff before asserting:**

1. Grep for duplicated logic. If you claim "unified into one helper," is the old helper actually gone?
2. Check all call sites if claiming "every path now uses X."
3. Read the PR's GitHub diff (not just local) — catches force-push/merge artifacts.
4. Revise the claim if the code doesn't support it; "partially unified" is valid, "unified" when half-done is a lie.
5. Test the claim. If PR says "fixes #123," the verification section shows #123's repro passing.

**Acceptance-criteria honesty.** If an issue has acceptance criteria, address
each item explicitly in the PR or issue comment that claims completion. Mark
each criterion as satisfied, deferred to a follow-up issue, or misframed by new
evidence. If an issue has no AC list, say what concrete decision, behavior, or
verification closes it. Never close an issue on a partial subset without making
the remaining work durable.

**Automated reviews are review input.** Before merging, inspect every automated
review/comment/check that posts substantive text: CodeRabbit, Copilot, proof
packs, security scanners, PR policy bots, and custom repo reports. Classify
each item as actionable, false positive/noise, informational, or tool failure.
Address actionable items with code or tests. For false positives/noise, leave a
brief PR comment or issue note when the reason matters for future agents. Do not
merge while a bot reports unresolved actionable findings, and do not treat a
green checkmark as a substitute for reading the comment body.

**Proof/impact reports.** When a repo posts generated impact reports such as a
Proof Pack, use them to choose gates and focus review. Required/recommended
gates should be reflected in the PR verification plan. Known-gap dumps,
zero-claim domains, or boilerplate deployment gates should be triaged rather
than followed blindly. If the report is noisy or misleading, improve the report
or record the mismatch in the owning issue; do not just learn to ignore it.

---

### Squash-merge hygiene

**`(#N)` suffix on master.** GitHub's "Default commit message: Pull request title and description" setting auto-appends `(#N)` and copies the PR body. Enforcement options per repo:

- GitHub Ruleset with subject regex `^(feat|fix|refactor|perf|test|docs|chore|build|ci|style|archive)(\([^)]+\))?: .+ \(#\d+\)$`
- Repo setting "Default commit message" → "Pull request title and description"

When running `gh pr merge <N> --squash` with custom `--subject`/`--body`, supply `(#N)` manually — the default is bypassed.

**Granularity is forward-only.** Prefer fewer, fatter PRs. Post-hoc combining via rebase destroys PR boundaries (orphaned PR records + new canonical-less commit). Fix at PR-open time.

**Rewriting degraded history** (missing `(#N)`, empty bodies):

_Scope check first:_ solo repo + no external SHA links → cheap. External `/commit/<SHA>` links → those break (PR pages survive by number). Other active agents → ask / wait.

_Reconstruction:_ `gh pr list --state merged --json number,title,body,mergeCommit,mergedAt` gives everything needed to regenerate each commit's message.

_Tool:_ `git filter-repo --commit-callback` (modern; prefer over deprecated `filter-branch`). For small scopes: `git rebase -i --exec`.

_Safety protocol:_

1. `git branch backup-master-pre-rewrite` before starting.
2. Dry-run on a mirror clone (`git clone --mirror . /tmp/rewrite-test`).
3. Confirm with user before force-push.
4. Force-push with `--force-with-lease`, not `--force`.
5. Tell others to re-clone (don't rebase onto new history — gets messy).

**Committer-date traps:**

_Trap 1:_ `git rebase --exec 'git commit --amend --no-edit -S'` resets committer-date to now on every rebased commit. `--no-edit` preserves the message, not the dates. Correct pattern:

```bash
git rebase <base> --exec '
  GIT_COMMITTER_DATE="$(git show -s --format=%cI HEAD)" \
    git commit --amend --no-edit -S
'
```

_Trap 2:_ `git-filter-repo` rewrites committer-date on _modified_ commits only (to run time). Unmodified commits keep originals — partial corruption hard to spot. Recovery is a follow-up filter-repo pass that restores original committer-dates by mapping `(#N)` → `mergeCommit.oid` → committer-date on a backup branch. Filter-repo date format is bytes `"<epoch> <tz_offset>"` (e.g. `b"1776860027 +0200"`), not ISO 8601.

_Defense:_ always keep `backup-<date>-pre-rewrite` and spot-check `git log -5 --format='%aI %cI'` after the rewrite.

---

### Destructive operations — require explicit confirmation

Even in auto mode, state specifically what will happen and pause:

- `git reset --hard` on a branch with uncommitted changes
- `git push --force` on any branch (`--force-with-lease` on shared branches is still disruptive)
- `git branch -D` on unmerged branch
- Amending a pushed commit
- `git rebase` rewriting published history
- `git filter-repo` / `filter-branch` on any branch
- Deleting branches/worktrees/stashes/tags
- `git clean -fd`

Never force-push to shared branches without agreement. Never push to `master` / `main` directly — the PR flow is the enforcement surface.

**Force-push alternatives:** before reaching for `--force-with-lease`, ask if a non-destructive path works. Amending your own feature branch: fine. Fixing a typo in a recent master commit: _don't_ — live with it; history isn't worth rewriting over one character. Adding missing `(#N)` to one commit: don't — fix the process, accept the miss.

---

### Repository settings (set once per repo)

- Branch protection on default: require PRs, prevent direct pushes.
- Required CI status checks before merge.
- **Squash-merge only.** Disable merge commits + rebase-merges.
- **Default commit message:** "Pull request title and description".
- Auto-delete head branches.
- Allow "Update branch" for stale PRs.
- Optional ruleset for commit message format (regex above).

---

### Merge conflicts

Investigate before resolving — read both sides, don't auto-prefer `theirs`/`ours`. Global `conflictStyle = zdiff3` shows common ancestor alongside the two conflicting versions. Run the verify command after resolving. If the conflict reveals a genuine design collision, open a tension/issue — don't collapse silently.

---

### Worktrees

Parallel checkouts sharing `.git`. Useful for parallel feature work, isolated agent sessions (each worker in its own worktree), bisect without touching the working copy.

```bash
git worktree add ../repo-featureX feature/featureX
git worktree add -b feature/new ../repo-new
git worktree list
git worktree remove ../repo-featureX
```

Can't check out the same branch twice. Each worktree has its own HEAD/index; stashes are per-worktree.

---

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

---

### Tags / releases

- Signed tags for releases: `git tag -s vX.Y.Z -m "..."`.
- Always annotated (`-a` or `-s`), never lightweight.
- Canonical version file (`pyproject.toml`/`Cargo.toml`/`package.json`) matches the tag.
- Push with `git pst` (alias for `--follow-tags`).

---

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

---

### Stash / navigation

- Name stashes: `git stash push -m "desc"`. Unnamed stashes become mysteries.
- Don't stash long — if work deserves to survive a week, it deserves a branch.
- `git switch` (not `checkout`) for branches; `git restore` for files.

---

### Anti-patterns (tripwire list)

Read when you notice yourself about to do one.

- Empty body on non-trivial commit; subject describing work-done not change-landed; vague nouns (`fix: stuff`).
- Claiming "unified"/"fixed"/"converged" when the diff doesn't support it.
- Multi-topic commits; mixed formatting + logic; "final final"; committing unrelated sweeps silently.
- `git add -A` sweeping secrets/artifacts; `git commit -a` without review.
- `--no-verify` to bypass a failing hook; amending after hook failure.
- Pushing directly to `master`; "WIP:" PR titles that survive to merge; merging with red CI.
- Silently ignoring review comments; LGTM without reading; "CI will catch it" instead of running verify locally.
- Force-push without agreement; `rebase` onto default; `-D` on unmerged branch.
- Post-hoc squashing merges (destroys PR boundaries); rewriting to fix a typo.
- Ceremonial "done!" without `file:line` citation or verification output.

---

### Interaction patterns (quick)

**Proactive or requested commit:** parallel `git status`/`diff --staged`/`diff`/`log --oneline -10` → review → draft intent-shaped message → stage by name → commit with heredoc → `git status` → report `[git] N files — "<subject>"`. Don't push.

**PR:** parallel `status`/`diff`/`log origin/master..HEAD`/upstream-check → review full branch diff → push with `-u` if untracked → `gh pr create --title --body` (heredoc with Summary/Problem/Solution/Verification) → report URL.

**PR state check:** `gh pr view <N>` + `gh pr checks <N>` + `gh api .../pulls/<N>/comments` (inline) + `--comments` (top-level) → report state/CI/unresolved/next-action.

**History rewrite:** clarify scope → assess blast radius → propose specific transformation → dry-run on mirror clone → confirm → `--force-with-lease` → verify PR/issue links still resolve.
