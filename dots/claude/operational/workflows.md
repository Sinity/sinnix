## Common Workflows

### Project Navigation

```bash
cd /realm/project/<name>    # Enter project
direnv allow                # Activate devshell (auto on cd)
```

### Workspace Inventory

For a fast read-only snapshot across many repos, use the shared scanner rather
than hand-rolling `find`/`git status` loops:

```bash
python3 /realm/project/sinnix/dots/_ai/tools/workspace_recon_scan.py --root /realm/project
python3 /realm/project/sinnix/dots/_ai/tools/workspace_recon_scan.py --root /realm/project --changed-only --with-size --json
```

### Heavy Agent Work

Recognized project dev environments install transparent wrappers for common
heavy commands. In Sinex and Polylogue devshells, ordinary commands such as
`xtask`, `cargo`, `pytest`, `uv`, `polylogue`, and `nix` are routed into the
Sinnix build/background slices automatically, so agents should run the normal
project command first.

Use an explicit scope only outside a recognized devshell or for one-off custom
commands that are expected to run for a long time or scan/write large stores:

```bash
sinnix-scope background -- <long-running scan/import/db command>
sinnix-scope build -- <project build/test command>
sinnix-scope nix-build -- nix build .#target
```

**Agent worktree placement (wear policy):** `/tmp` is on the root MX500
(NOT tmpfs; the wear-limited drive with a 60 GB/day write SLO). A Rust
worktree's per-checkout `CARGO_TARGET_DIR` writes multiple GB per build.
Place agent worktrees for heavy-compile repos under `/realm/tmp/worktrees/`
(NVMe, 400 GB/day budget) instead of `/tmp`:

```bash
mkdir -p /realm/tmp/worktrees
git -C /realm/project/<repo> worktree add -b <branch> /realm/tmp/worktrees/<name> origin/master
```

**Sinex tests from a worktree:** the devshell's `DATABASE_URL` points at the
worktree's own (non-running) dev postgres, so sqlx macros fail; and
`SQLX_OFFLINE=true` breaks test files whose queries aren't in `.sqlx`.
Point macros at the main checkout's live dev DB instead:

```bash
nix develop --command env \
  DATABASE_URL="postgresql:///sinex_dev?host=/realm/project/sinex/.sinex/run" \
  cargo test -p <crate> --lib <filter>
```

The pre-push drift guard inherits the same broken `DATABASE_URL` — pushing
from a worktree devshell needs the identical `env DATABASE_URL=… git push`
override, or sqlx compile errors masquerade as drift-guard rejections.

### Data Analysis (lynchpin)

```bash
cd /realm/project/sinity-lynchpin
just                        # List remaining heavyweight pipelines
just baseline               # Rebuild ActivityWatch/git/health rollups
python -m lynchpin.views.calendar_views build 2026-03-01 2026-03-07
```

### NixOS Rebuild (sinnix)

```bash
cd /realm/project/sinnix
direnv allow                    # Activate devshell
check --no-build                # Fast pre-flight: curated default checks, sequential
```

All rebuild commands use `nh` with systemd-run containment (nice=10):

```bash
switch                          # nh os switch — build + activate immediately
boot                            # nh os boot — build + set boot default (safer: reboot)
test-system                     # nh os test — build + activate without persisting
test-vm                        # nixos-rebuild test-vm — test in QEMU (nh doesn't wrap this)
clean                           # nh clean all — garbage collect + optimise store
```

For risky changes, test in VM first: `test-vm` → launch QEMU → verify → `switch`.

**All three agent CLIs self-update via FHS npm bootstrap** — no Nix rebuild
needed. `claude update`, `codex update`, `gemini` self-update inside
`~/.local/state/{claude-code,codex,gemini}/npm/`. State directories are
persisted under impermanence.

### Agent Orchestration (Multi-Agent Work)

When dispatching multiple coding agents to execute a plan (e.g., parallel lanes),
state the isolation model explicitly. The rules below are for worktree-isolated
agents only; if agents intentionally share one checkout, the coordinator owns
branching/committing/merging and agents should report patches or commit only by
explicit instruction.

**Worktree discipline — CRITICAL when using worktree isolation:**

- Agents run in isolated worktrees (`isolation: "worktree"`). The isolation system auto-cleans worktrees on completion, discarding uncommitted working-tree changes. **Agents MUST `git commit` every logical chunk.** Even a WIP commit is fine; the branch persists.
- **Never `cd /realm/project/<name>` from inside a worktree agent.** The worktree is the agent's root. Git operations run against the worktree branch by default. If an agent `cd`s to the main checkout, commits land on the main branch — corrupting both the main branch and the worktree.
- **Verify git remote.** Before pushing, confirm `git remote -v` and `git branch --show-current` match the worktree branch.

**Write-scope separation:**

- Before dispatching, identify shared files (e.g., `schema/mod.rs`, `apply.rs`, `lib.rs`). These are conflict hotspots.
- When two lanes MUST touch the same file, serialize them: first lane commits + merges, second lane rebases.
- For additive changes to shared files (module declarations, table registrations), pre-define which lane owns each line range to minimize conflicts.

**Commit cadence:**

- Agents should commit after each project check passes, not after "all work done."
- First commit: "wip: <lane> — types and module wiring" (after the first relevant project check passes)
- Second commit: "feat: <lane> — <next milestone>"
- This prevents worktree auto-cleanup data loss and makes incremental merge possible.

**Pre-flight checklist for each agent prompt:**

1. Specify exact files the agent OWNS vs AVOIDS
2. Include a "FIRST: comment on issue #N with scope" step
3. Include a "commit after each successful xtask check" instruction
4. Warn about worktree cleanup: "commit or lose it"

**Post-agent merge checklist:**

1. Verify the worktree branch has commits: `git log <worktree-branch> --oneline -5`
2. If no commits, check working tree: `git -C <worktree> status --short`
3. Cherry-pick or diff-apply if the agent committed to wrong branch
4. `git worktree remove` stale worktrees after merging

### Context7

Use for unfamiliar APIs: `resolve-library-id` → `query-docs`. Cheap, prevents mistakes.

### Daily oracle digest

