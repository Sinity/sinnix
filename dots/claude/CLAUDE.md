# Sinity Environment Memory

> **This file is your persistent environment memory.** It contains compressed
> understanding of the development ecosystem, NixOS configuration, and project
> constellation. You start every session "pre-grokked".
>
> This is a single flat file — no transclusion. Codex and Gemini read the same
> content through symlinks (`~/.codex/AGENTS.md`, `~/.gemini/GEMINI.md` →
> `~/.config/claude/CLAUDE.md` → this file in the sinnix repo). Edits propagate
> to every agent instantly; there is no render step.

---

## Operating Contract

### Stance

- Be a finisher, not a planner. Carry work to a verified done-state unless a
  concrete blocker remains.
- Preserve intent. Implement the requested outcome; do not substitute a safer,
  smaller, or more familiar product decision.
- Prefer surgical renewal. Remove obsolete paths, flags, wrappers, aliases, and
  stale docs in the same change that replaces them. No deprecation theater.
- Respect the local architecture. Use established modules, helpers, data flows,
  and typed interfaces before adding machinery.
- Work evidence-first. When uncertain, inspect the live config/source/history
  instead of relying on memory.

### Execution

- On ambiguous or multi-step requests, first state the understood scope and any
  exclusions. Then proceed.
- Batch related edits: gather context, decide the coherent change, apply it, and
  verify once with the narrow command that exercises the changed surface.
- When a check fails, diagnose the whole failure shape and batch the fixes.
  Avoid fix-one-error-at-a-time loops.
- Do not expand scope opportunistically. If adjacent cleanup is valuable but not
  implied, ask or record it as follow-up.
- Use the right substrate: `rg` and structured parsers for exact search,
  semantic tools near code edits, Context7 for current third-party APIs, and
  Polylogue/Lynchpin for historical reconstruction.
- Cross-reference related functions/modules before declaring a pattern fixed.
  A single call site is not proof of consistency.
- Keep communication concise but concrete: state assumptions, tactics, changed
  files, verification, and residual risk.
- Do not pipe command output into `tail`/`head`/`grep -c`/similar truncating
  filters as a default habit (e.g. `devtools test ... 2>&1 | tail -60`). The
  user reviewing the transcript loses the actual output — failures, stack
  traces, warnings — behind a fixed line count you chose blind. Let commands
  print their natural output; if a command is genuinely voluminous, redirect
  to a file and read/grep that file deliberately afterward, or use a
  narrower selector/flag the tool itself provides (verbosity flags, `-k`
  filters) rather than truncating post hoc. Reserve `tail`/`head` for cases
  where you have a specific, stated reason (e.g. re-reading a known-large
  log file's final section after already having seen the full run once).
- When `bd where` succeeds in the current repository, use Beads (`bd`) for
  durable task state: ready work, claims, blockers, dependencies, discovered
  follow-ups, and persistent project memory. Use local plans only for the
  current turn's execution checklist; do not make markdown TODOs the shared
  source of truth. Run `bd prime` for the current Beads workflow context.

### Safety And Git

- Preserve user work. Dirty trees are normal; never revert or overwrite changes
  you did not make unless explicitly asked.
- Treat destructive operations as explicit acts. State what will be deleted,
  reset, force-pushed, rebased, killed, or history-rewritten before doing it.
- Commit locally when a coherent change is verified. Push proactively when the
  repository workflow allows it; for product repos this means pushing feature
  branches and opening/updating PRs, not direct pushes to protected default
  branches. Do not push when the user, repo, or active workflow says to hold.
- Stage by path, not broad sweeps, when secrets or unrelated work could be
  captured.
- Don't leave transient work-in-progress artifacts (git stashes, scratch merge
  files, temp branches) sitting around once they're confirmed superseded or
  redundant — clean them up as part of finishing the task, not as a separate
  ask. This applies to things you created yourself this session for your own
  bookkeeping (e.g. a stash you popped and merged, a scratch file used to
  resolve a conflict): once you've verified its content is fully captured
  elsewhere (committed, merged, or superseded by a newer state), remove it
  rather than leaving it as clutter for the user to notice and ask about
  later. This is distinct from destructive-operation caution around content
  you did NOT create or haven't verified is redundant — verify first, then
  clean up without waiting to be asked.

### Verification

- Tests should protect behavior, contracts, invariants, reproduced bugs,
  security boundaries, parser semantics, or cross-module contracts.
- Do not add tests that merely memorialize a diff: a rename, deleted spelling,
  moved command, removed list entry, or changed literal. For ordinary cleanup,
  rely on source review, evaluation, and focused behavior checks.
- If baseline checks are already failing, classify whether the failure is
  related before claiming completion. Do not hide inherited failure state.
- Before declaring completion, cite the changed files, report exact verification
  commands, and say what was not run.

### Runtime Discipline

- For long-running commands, do not busy-wait or spawn duplicates against the
  same resource. Redirect to a known log or let the harness report completion.
- Do not run multiple heavy builds/tests against the same checkout, database,
  lockfile, or output path. If restarting, stop the old run first.
- Reuse one output artifact per purpose and clean stale processes when they are
  part of the task.
- Do not turn transient live-host pressure into permanent project policy.
  Resource incidents during a rebuild, deploy, or local verification should be
  handled with one-shot environment overrides, stopping unrelated live
  workloads, changing the service/runtime containment layer, or retrying under
  an appropriate wrapper. Do not permanently reduce build parallelism,
  optimization level, cache behavior, retention, or feature coverage merely to
  make the current host survive a momentary RAM/IO spike.
- Before changing build policy for resource reasons, identify the pressure
  source in live evidence: process RSS/PSS, swap, PSI, cgroups, journal OOM
  events, active timers, and disk IO state. A high `used` number in `free` is
  not itself a leak; separate anonymous process memory, tmpfs/zram, page cache,
  and D-state IO backlog before acting.

---

## Ambient Control Model

Browser, desktop, and terminal control are normal local capabilities on this
machine. Interpret user language directly:

- **"your browser" / "an agent browser"** → use an agent-private Chrome through
  `sinnix-chrome-control --target private`. This private profile is seeded from
  the live Chrome profile by default, so agents can use authenticated state
  without opening tabs or navigating in the user's visible browser. Use
  `--target private-visible` when the user should be able to see the agent
  browser.
- **"my browser" / "the real browser" / "my tabs"** → use the user's live Chrome
  profile through `sinnix-chrome-control --target live`. This is a high-authority
  surface: it can see authenticated pages/cookies and non-active tabs via
  `127.0.0.1:9222`.
- **"desktop" / "window" / "screen"** → use Hyprland and screenshot helpers:
  `sinnix-hypr-control`, `sinnix-keyboard-control`, and
  `sinnix-screenshot-control`.
- **"terminal" / "that terminal window" / "Codex pane"** → use Kitty remote
  control first: `sinnix-kitty-control list`, then capture/send/wait against a
  matching title/window. Prefer this over global keyboard injection for
  terminals.

Prefer the `sinnix-*` helpers for browser/desktop/window/terminal perception and
control. Use `claude-browser`/`codex-browser` only when Chrome DevTools MCP
capabilities are specifically needed. Load the `desktop-control-plane` skill
when a task needs recipes, screenshots, HDR handling, or careful GUI
interaction. Run `sinnix-agent-status` when you need a quick live probe of
available control surfaces.

### Agent Runtime Control

Prefer native non-interactive runtimes for unattended work; use Kitty only
when a human or coordinator needs a visible, interruptible process or a
deliberately interactive agent session.

- **Codex local**: use `codex exec -C <repo> --model <model> -c
  'model_reasoning_effort="<effort>"' ...`; use `codex exec resume <id>` for a
  continued worker. Set model and effort per run instead of relying on the
  interactive session's defaults.
- **Claude local**: use `env -u ANTHROPIC_API_KEY claude-full --print ...` for
  subscription-backed batch work. Use `claude-full --background` for a
  resumable native worker, and manage it with
  `~/.local/state/claude-code/launch.sh agents|logs|stop`. Preserve the key only
  when API-key billing is explicitly intended.
- **Codex Cloud**: use `codex cloud exec|list|status|diff|apply`; the CLI is the
  control plane and the task id is the recovery handle. Do not automate the
  Codex web UI when the CLI covers the operation.
- **Browser-backed cloud work**: prefer background CDP targets. The
  `private-visible` profile is shared by concurrent agents, so own explicit
  page target ids, never activate another agent's target, and avoid coordinate
  clicks. Verify the focused Hyprland window when operator focus matters.
- **Kitty workers**: launch with keep-focus semantics and route separate OS
  windows with `movetoworkspacesilent` when isolation is useful. Do not bring
  worker windows to the current workspace as a side effect of dispatch.

Do not try to change the current agent's model or reasoning effort by injecting
commands into its own live TUI while it is sampling. Choose these controls at
worker launch or between turns.

For coordination, Beads owns work and dependencies. Polylogue blackboard
assertions are durable asynchronous notes, not a delivered group chat: until
`polylogue-1hj` / `polylogue-s7ae.3` provide watch, unread, addressing, ack, and
wakeup semantics, use explicit runtime task ids plus an append-only shared
dialogue for active cross-agent design.

### Evidence and Telemetry

Use the control plane for live action; use the evidence plane to reconstruct
what happened. Do not infer history from the current screen/browser state when
Polylogue, Lynchpin, or Sinnix captures can answer directly.

- **AI session history** → Polylogue. `polylogued` tails Claude/Codex sessions;
  use Polylogue MCP/search for "what did agents do/say/change?" questions.
  Raw session JSONL also lives under `~/.claude/projects/<project>/*.jsonl`
  when you need to grep something Polylogue has not ingested yet.
- **Cross-source personal/system history** → Lynchpin. It materializes chats,
  git, ActivityWatch, shell, health, and machine telemetry into queryable
  analysis products. Use it for timelines, correlations, and "what happened
  around X?" questions.
- **Host/runtime evidence** → Sinnix observability. `/etc/sinnix/runtime-inventory.json`,
  `sinnix-observe`, and `/realm/data/captures/**` are the raw/runtime truth for
  services, captures, pressure, screenshots, terminal recordings, and machine
  telemetry.
- **Live browser/desktop/terminal state** → DevTools and `sinnix-*` helpers.
  Capture screenshots or terminal scrollback into the capture lake when the
  observation should survive the session.

Look up history proactively when the user references past work ("remember
when…", "like before"), after context compaction, or when an error pattern
feels previously solved. When history access yields durable insight, write it
down (scratch note, `bd remember`, or the owning CLAUDE.md) instead of
re-discovering it next session.

---



Raw-log lives at `/realm/data/knowledgebase/logs.raw-log.md`. It is the
append-only, low-friction operator stream used by `rawlog`, `rawlog-capture`,
and `oracle`; read it when the user references raw-log/rawlog, recent subjective
context, or "what have I been saying/thinking lately?"

Capture only durable, non-obvious decisions, tensions, dead ends, and cross-session
insights. Do not mirror ordinary task notes there.

- Quick capture → `seed/YYYY-MM-DD-HHMMSS-slug.md`
- Durable decision → `crystal/decisions/name.md`
- Unresolved contradiction → `tension/NNN-name.md`
- Dead end worth not rediscovering → `graveyard/name.md`
- Per-subject threads → `subject/{goal,project}/...`

---

## System Context

### Hardware

- **Host**: `sinnix-prime` (desktop workstation)
- **CPU**: Intel i7-13700K (16 cores, 24 threads); **GPU**: RTX 3080; 32 GB RAM
- **OS**: NixOS, unstable channel
- Storage: MX500 1TB SATA = root/system (wear-limited — avoid gratuitous
  writes); Crucial P3 4TB NVMe = `/realm`; 6TB HDD = `/outer-realm` (backup
  target); 14TB HDD = `/neo-outer-realm` (bulk media, automount).

### NixOS Environment

```
# NEVER use nix profile commands - all packages via modules
# Use nix shell/nix develop for temporary tools

direnv allow           # Activate project devshell
nix develop            # Enter flake devshell manually
nix build .#<output>   # Build specific flake output
```

**Sinnix rebuild** — ALWAYS use the devshell commands (they wrap `nh` with idle
CPU/IO scheduling and a shared rebuild lock):

```
# From inside the devshell (direnv allow or nix develop):
test-vm                     # Test risky changes in QEMU VM first
switch                      # Apply to live system (resource-scoped nh os switch)
boot                        # Safer alternative: set boot default without immediate activation

# From outside the devshell (e.g. Claude Code, non-devshell shell):
cd /realm/project/sinnix && nix develop --command switch
# NEVER: nix shell nixpkgs#nh --command nh os switch ...
# NEVER: nh os switch ... (bypasses idle-scheduling wrapper)
```

> **Why this matters**: `nix.daemonCPUSchedPolicy=idle` only affects scheduler
> priority — it does NOT cap memory. Without the nix-build.slice placement the
> daemon runs unconstrained and Rust builds can consume all 32 GB, thrashing
> the system even though CPU cycles were yielded correctly. Always use
> `switch`/`boot` devshell commands or `nix develop --command switch`.
>
> Do not insert `check --no-build` before `switch` as routine agent hygiene.
> `switch` already evaluates/builds, and repeating eval adds latency/load on the
> exact path used for recovery. Use focused tests for edited modules, then
> `switch` when applying live Sinnix changes.

All three agent CLIs self-update via npm bootstrap — no Nix rebuild needed.
`claude update`, `codex update`, `gemini` self-update inside
`~/.local/state/{claude-code,codex,gemini}/npm/` (persisted under
impermanence).

---

## Filesystem Structure

### /realm - The Data Kingdom

```
/realm/
├── project/           # All active project repositories
├── data/              # Canonical data lake (see below)
├── db/                # nodatacow DB subvolumes (polylogue, machine-telemetry)
├── inbox/             # Staging area for retired/incoming data + downloads
└── tmp/               # Throwaway analysis output, agent worktrees
```

User home is `/home/sinity`. It is intentionally not under `/realm`: the live
home directory is recreated on each boot and populated from `/persist` via the
impermanence module plus Home Manager activation. Persistent home state such as
SSH keys lives at `/persist/home/sinity/.ssh` and appears at runtime as
`/home/sinity/.ssh`.

### Orientation Rules

- Do not assume freedesktop directories live under `/home/sinity`. Query them
  with `xdg-user-dir <NAME>` when the user says Downloads, Documents, Desktop,
  etc.
- The configured downloads directory is `/realm/inbox/download`; `~/Downloads`
  may not exist. Incoming bundles, patches, browser downloads, and cleanup
  artifacts usually land there or under `/realm/inbox/download/misc`.
- Use `/realm/tmp/` for throwaway analysis output that may be large or useful
  across a short session. Avoid `/tmp` for heavy repo work; it is a small
  tmpfs and heavy churn belongs on NVMe.
- Use `/realm/tmp/worktrees/` for agent worktrees or any compile-heavy checkout.
  This keeps build output on NVMe and avoids root-disk wear.
- Treat `/realm/data/` as canonical user data, not scratch. Read from it for
  evidence; only write there through the owning tool or workflow. Read
  `/realm/data/INVENTORY.md` before reorganizing anything in the lake.

### /realm/data - Data Lake Structure

```
/realm/data/
├── captures/          # Continuous local telemetry
│   ├── activitywatch/ # Window/AFK/browser tracking
│   ├── webhistory/    # Browser history exports
│   ├── asciinema/     # Terminal recordings
│   ├── keylog/        # Keystroke captures (scribe-tap)
│   ├── audio/         # Audio captures
│   ├── comms/         # Communication captures
│   ├── screenshot/    # Screenshots
│   ├── shell/         # Shell history (Atuin)
│   ├── syslog/        # System log exports
│   ├── machine/       # Canonical host machine telemetry
│   ├── polylogue/     # Polylogue archive root
│   └── kitty-scrollback/ # Terminal scrollback
├── exports/           # GDPR/Takeout provider exports
│   ├── chatlog/       # AI chat archives (Claude, ChatGPT, Codex)
│   ├── health/        # Samsung Health, Sleep As Android
│   ├── google/        # Takeout archives
│   └── ...            # reddit, spotify, raindrop, goodreads, wykop, ...
├── libraries/         # Curated collections (finance, doc, books, model, ...)
├── derived/           # Derived analysis products
└── knowledgebase/     # PKM vault (Obsidian-friendly MOCs, raw-log)
```

---

## Project Constellation

### Core Infrastructure

| Project             | Path                             | Purpose                                                        |
| ------------------- | -------------------------------- | -------------------------------------------------------------- |
| **sinnix**          | `/realm/project/sinnix`          | NixOS system configuration (flake-parts, home-manager, agenix) |
| **sinex**           | `/realm/project/sinex`           | Event-driven data capture platform (Rust, NATS, PostgreSQL)    |
| **sinity-lynchpin** | `/realm/project/sinity-lynchpin` | Analysis coordination hub (Python, DuckDB, HPI-style modules)  |

### Capture & Integration Tools

| Project              | Path                              | Purpose                                                     |
| -------------------- | --------------------------------- | ----------------------------------------------------------- |
| **polylogue**        | `/realm/project/polylogue`        | AI chat export archiver (Claude, ChatGPT, Codex → Markdown) |
| **scribe-tap**       | `/realm/project/scribe-tap`       | Wayland keystroke mirror for Hyprland                       |
| **intercept-bounce** | `/realm/project/intercept-bounce` | Keyboard debouncing filter (Rust)                           |

### Knowledge & Analysis

| Project           | Path                        | Purpose                            |
| ----------------- | --------------------------- | ---------------------------------- |
| **knowledgebase** | `/realm/data/knowledgebase` | PKM vault (Obsidian-friendly MOCs) |
| **stashbox**      | `/realm/project/stashbox`   | Media library tooling              |

Inactive/archived work lives under `/realm/project/_inactive/` and
`/realm/project/archives/`; third-party checkouts (snix, tvix, codex) are not
Sinity projects.

### Project Relationships

```
sinnix ──────► System packages, services, dotfiles
    │
    └──► Enables: sinex service stack, polylogued daemon, scribe-tap

sinex ◄────── Captures events from scribe-tap, polylogue
    │
    └──► Feeds: lynchpin via DuckDB/modules

lynchpin ◄─── Aggregates: ActivityWatch, Atuin, git, health, chats
    │
    └──► Produces: Calendar views, baselines, narratives
```

### Environment Variables (set by sinnix)

```
SINEX_ROOT=/realm/project/sinex
LYNCHPIN_REPO_ROOT=/realm/project/sinity-lynchpin
POLYLOGUE_ROOT=/realm/project/polylogue
KNOWLEDGEBASE_ROOT=/realm/data/knowledgebase
```

### Documentation Map

| Topic                 | Location                                                             |
| --------------------- | -------------------------------------------------------------------- |
| Sinnix modules        | `/realm/project/sinnix/modules/`                                     |
| Sinnix grok notes     | `/realm/project/sinnix/.agent/scratch/` (architecture + machine map) |
| Sinex architecture    | `/realm/project/sinex/AGENTS.md`                                     |
| Lynchpin data sources | `/realm/project/sinity-lynchpin/docs/reference/data-sources.md`      |
| Data inventory        | `/realm/data/INVENTORY.md`                                           |

**Project-specific details** (module structure, patterns, workflows) live in
each project's `CLAUDE.md`.

---

## Agent Context Conventions

- **`CLAUDE.md` is the canonical instruction file everywhere** — one flat file
  per repo, no `@`-transclusion. `AGENTS.md` in each repo is a committed
  symlink to `CLAUDE.md`, so Claude, Codex, and Gemini always read identical,
  current content. `verify-agent-topology /realm/project` audits this
  invariant.
- **MCP profiles**: registry source of truth is `flake/data/mcp-registry.nix`
  in sinnix; wiring lives in `modules/features/dev/agents/` (`mcp.nix` +
  sibling helpers `mcp-tools.nix`/`client-profiles.nix`/`serena.nix`/
  `browser.nix`/`hooks.nix`; regrouped from the former `mcp-servers.nix`,
  sinnix-9u6). Plain `claude`/`codex` use the full non-browser profile
  (GitHub, Context7, Polylogue, Lynchpin, Serena, Codebase Memory).
  `claude-lean`/`codex-lean` keep GitHub, Context7, and Polylogue only.
  `claude-browser`/`codex-browser` add the Chrome DevTools MCP tier. `claude`
  is a shell alias to the `claude-full` wrapper — the bare `~/.local/bin/claude`
  is deliberately unmanaged because Claude Code's installer claims and
  clobbers it on auto-update.
- **Alternate backends (full MCP profile)**: `claude-deepseek`/`codex-deepseek`
  (DeepSeek endpoints, key from agenix `deepseek-api-key`);
  `claude-local`/`codex-local` (local Ollama hub via the LiteLLM gateway on
  `127.0.0.1:4000`, `modules/services/litellm.nix` — local model names are
  defined once in its `model_list`).
- **Shared skills** live in `dots/_ai/skills/` (sinnix repo) and are linked
  into `~/.config/claude/skills`, `~/.codex/skills`, `~/.gemini/skills`.
- **Desktop environment**: Hyprland (Wayland) + Noctalia shell; terminals
  foot/kitty; browser qutebrowser + Chrome (CDP on :9222).
- **Dotfile pattern**: everything in sinnix `dots/` reaches `$HOME` via Home
  Manager out-of-store symlinks — edits propagate instantly without rebuild.
- **Context7**: documentation discovery via `resolve-library-id` →
  `query-docs`. Cheap, prevents stale-API mistakes; use it for unfamiliar or
  fast-moving third-party APIs.

---

## Common Workflows

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

Resource containment is not a verification contract. In Sinex, use `xtask` for
build/check/test verification because it owns the repo's schema, SQLx, database,
feature, and formatting assumptions. Do not bypass it with direct `cargo`
commands merely to get a narrower-looking signal.

Resource pressure during heavy work is a runtime scheduling problem first, not
a project semantics problem (see Runtime Discipline above). If throttling is
needed to finish the immediate operation, prefer a one-shot environment
override or the Sinnix wrapper/slice layer; leave durable project defaults
alone unless the project itself has a reproducible, cross-machine resource bug.

Use an explicit scope only outside a recognized devshell or for one-off custom
commands that are expected to run for a long time or scan/write large stores:

```bash
sinnix-scope background -- <long-running scan/import/db command>
sinnix-scope build -- <project build/test command>
sinnix-scope nix-build -- nix build .#target
```

**Agent worktree placement (wear policy):** a Rust worktree's per-checkout
`CARGO_TARGET_DIR` writes multiple GB per build. Place agent worktrees for
heavy-compile repos under `/realm/tmp/worktrees/` (NVMe), never `/tmp`:

```bash
mkdir -p /realm/tmp/worktrees
git -C /realm/project/<repo> worktree add -b <branch> /realm/tmp/worktrees/<name> origin/master
```

**Sinex tests from a worktree:** use a live dev database socket, not sqlx's
offline query cache. Plain `nix develop` relocates the per-checkout dev
database under `/var/cache/sinex/$USER/<checkout-hash>/dev-state`; read the
current checkout's `DATABASE_URL` from its devshell before overriding another
worktree:

```bash
SINEX_MAIN_DATABASE_URL="$(
  git -C /realm/project/sinex status --short >/dev/null &&
  nix develop /realm/project/sinex --command sh -c 'printf %s "$DATABASE_URL"'
)"

env DATABASE_URL="$SINEX_MAIN_DATABASE_URL" \
  nix develop --command cargo test -p <crate> --lib <filter>
```

The pre-push drift guard inherits the same broken `DATABASE_URL` — pushing
from a worktree devshell needs the identical `env DATABASE_URL=... git push`
override, or sqlx compile errors masquerade as drift-guard rejections.

### Data Analysis (lynchpin)

```bash
cd /realm/project/sinity-lynchpin
just                                        # List all recipes
python -m lynchpin.analysis materialize     # DAG-orchestrated substrate materialization
python -m lynchpin.cli.current_state --start 2026-05-01 --end 2026-05-05
```

### Agent Orchestration (Multi-Agent Work)

When dispatching multiple coding agents to execute a plan (e.g., parallel lanes),
state the isolation model explicitly. The rules below are for worktree-isolated
agents only; if agents intentionally share one checkout, the coordinator owns
branching/committing/merging and agents should report patches or commit only by
explicit instruction.

**Worktree discipline — CRITICAL when using worktree isolation:**

- Agents run in isolated worktrees (`isolation: "worktree"`). The isolation
  system auto-cleans worktrees on completion, discarding uncommitted
  working-tree changes. **Agents MUST `git commit` every logical chunk.** Even
  a WIP commit is fine; the branch persists.
- **Never `cd /realm/project/<name>` from inside a worktree agent.** The
  worktree is the agent's root. If an agent `cd`s to the main checkout, commits
  land on the main branch — corrupting both.
- **Verify git remote.** Before pushing, confirm `git remote -v` and
  `git branch --show-current` match the worktree branch.

**Write-scope separation:**

- Before dispatching, identify shared files (e.g., `schema/mod.rs`, `apply.rs`,
  `lib.rs`). These are conflict hotspots.
- When two lanes MUST touch the same file, serialize them: first lane commits +
  merges, second lane rebases.
- For additive changes to shared files, pre-define which lane owns each line
  range.

**Commit cadence:** commit after each project check passes, not after "all work
done". First commit once the first relevant check passes, then per milestone.
This prevents worktree auto-cleanup data loss and makes incremental merge
possible.

**Pre-flight checklist for each agent prompt:**

1. Specify exact files the agent OWNS vs AVOIDS
2. Include a "FIRST: comment on issue #N with scope" step
3. Include a "commit after each successful check" instruction
4. Warn about worktree cleanup: "commit or lose it"

**Post-agent merge checklist:**

1. Verify the worktree branch has commits: `git log <branch> --oneline -5`
2. If no commits, check working tree: `git -C <worktree> status --short`
3. Cherry-pick or diff-apply if the agent committed to the wrong branch
4. `git worktree remove` stale worktrees after merging

### Cross-item batch execution (content-aware)

The unit of work is a **cluster of related items**, not one tracker item at a
time. Before claiming, look at what else in the ready set touches the same
files/area (in beads repos: design-field anchors, prework packets, or a
clustering helper where the repo has one).

- **Overlapping footprints** (same modules): claim the cluster, one branch,
  rewrite the area once satisfying every item's AC, per-item commits as review
  waypoints, one sweep PR with a per-item AC matrix. Paying the area-reading
  cost once and avoiding self-conflicts between successive PRs is the point.
- **Disjoint footprints**: separate PRs (squash-merge = one master commit per
  logical change), but pipeline them in one session/checkout: branch A →
  commit → push → PR, then branch B from fresh master immediately while A's
  CI runs. Never idle-wait on CI.
- **Parallel subagent worktrees** only when ≥3 disjoint lanes exist, each
  execution-grade (full design or packet), with no shared hotspot files —
  then the packet/design IS the subagent prompt. Otherwise one agent
  pipelining beats coordination overhead.
- **Verification amortization**: narrow per-item checks while batching; the
  broad gate once per branch at the publish boundary — never per item.
- **Content-aware shapes**: mechanical sweeps (lint/docs/renames) batch
  hardest; schema/migration bumps must batch per tier/window; investigation
  items batch over a shared evidence pass; decision items batch into one
  operator review session.
- **Beads repos**: closing/updating beads on a feature branch can silently
  revert on `git checkout` (the post-checkout hook re-imports the target
  branch's committed jsonl) — this is bd's correct, by-design sync model, not
  a bug, but it actively fights a workflow that spins up many short-lived
  branches: a bead closed on branch A reads back as open on branch B if B was
  created from an older `master` and hasn't merged A's commit yet. Nothing is
  lost (the close is safe in git history), but `bd show`/`bd ready` output is
  stale until a commit carrying that state lands on your current branch.
  Mitigate by (1) not spinning a new `chore(beads): ...` branch while one is
  already open — merge it first or add to it; (2) merging bd-only bookkeeping
  branches immediately rather than leaving them open while other branches
  diverge from `master` in the meantime; (3) folding a single `bd
  claim`/`close` into the same branch as the code change it accompanies
  instead of a dedicated branch per mutation; (4) re-verifying with `bd show
  <id> --json` after any checkout/merge/worktree-add before trusting bd's
  query output for a bead you just touched. `bd export` (and the pre-commit
  hook that calls it) resolves its output path from bd's own database
  location, independent of the invoking shell's cwd — inside a temporary
  conflict-resolution worktree it silently no-ops on that worktree's own
  file, so resolving a `.beads/*.jsonl` merge conflict via `bd export` can
  leave literal conflict markers in place. Instead extract both sides
  directly (`git show :2:.beads/issues.jsonl` / `:3:...`), hand-merge bead-by-
  id preferring whichever side has the later `updated_at`, verify every line
  parses as JSON, then `git add`.

### Daily oracle digest


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

## Codebase Analysis

### Survey → Narrate → Synthesize

For thorough code review or bug hunting, use the `analyze` or `swarm` skill:

1. **Survey** (BFS): List all items at the current level, note concerns without deep-diving
2. **Narrate** (DFS): For the highest-concern item, verbalize line-by-line what each piece does
3. **Synthesize**: Return to the broad view, cross-reference findings across related code

Empirically validated techniques: line-by-line narration (forces attention),
cross-referencing related functions (e.g. `register()` vs `list()` key-format
mismatches), checking get→modify→put patterns for races in distributed code.

### Semantic MCPs

Serena and `codebase-memory-mcp` are registered for Codex, Claude, Gemini, and
VS Code. They overlap but are not interchangeable. Default sequence:

1. `rg` for exact literal text and unindexed/generated surfaces.
2. Codebase Memory `search_code` for broad "where does this concept show up?"
   queries — fast, persistent, returns containing symbols with graph metadata.
3. Serena near an edit boundary: symbol overviews, precise lookup, references
   grouped by containing symbol, diagnostics, rename, safe-delete, symbol-body
   replacement.

Serena is configured for `sinex`, `polylogue`, `sinity-lynchpin`, and `sinnix`
via `.serena/project.yml`; it activates from the current working directory. If
Serena tools are missing in Codex despite an active config, use tool discovery
for the exact operation name — lazy loading can hide active tools.

Codebase Memory: use `get_code_snippet` after `search_graph`/`search_code`
yields an exact qualified name. Treat `get_architecture`, vector search,
`trace_path`, `detect_changes`, and custom Cypher as exploratory hints until
validated against source/Serena; re-index before relying on change-impact
answers:

```bash
codebase-memory-mcp cli index_repository '{"repo_path": "/realm/project/<repo>"}'
codebase-memory-mcp cli search_code '{"project": "realm-project-<repo>", "pattern": "MaterialReadySet"}'
```

Indexes live under `~/.local/share/codebase-memory-mcp`; Serena state under
`~/.local/share/serena` (installs under `~/.local/state/serena`).

---

## Thinking in Markdown

Externalize reasoning to scratch files. Context is expensive, files are cheap.

**When:** non-trivial analysis, multi-step debugging, architectural decisions;
proactively for anything that took >1 tool call to discover; especially for
cross-session or compaction-spanning work.

**Where:**

| Scope                | Location                                  |
| -------------------- | ----------------------------------------- |
| Global/cross-project | `~/.claude/scratch/NNN-<topic>.md`        |
| Project-specific     | `.agent/scratch/<date-or-NNN>-<topic>.md` |

- If a project lacks `.agent/scratch/`, create it early and ensure `.gitignore`
  covers it before accumulating notes.
- **Never use `.claude/` for per-project auxiliary content** — Claude Code
  treats it as protected and prompts on every write. `.agent/` is the
  project-local convention.
- Structure: YAML frontmatter (`created`, `purpose`, `status`, `project`), then
  Context / Findings / Outcome.
- When referring the user to a scratch file, always summarize the key points in
  your response — don't just point at the file.
- Projects can pin ongoing-relevance notes in their CLAUDE.md via a "Pinned
  Notes" section with bare `@path` lines (Claude-only transclusion; keep repo
  CLAUDE.md flat otherwise).

---

## Session Recall (hooks)

Claude Code has a `SessionStart` hook at
`~/.claude/hooks/sessionstart-polylogue-recall.sh`: if `polylogue` is on PATH it
prints up to three recent sessions matching the current project directory, and
exits silently when no archive data is available.

`~/.claude/hooks/sessionstart-sinex-recall.sh` (Codex calls the same command as
`sessionstart-sinex-recall`) prints a compact Sinex machine-context block from
`sinexctl recall`, preferring a project-local
`.sinex/state/runtime-target.json`, then `SINEX_RUNTIME_TARGET_CONFIG`, then
ordinary `sinexctl` config. It exits silently on missing runtime, auth,
timeout, or empty output. Tune with `SINEX_SESSIONSTART_RECALL=0` (disable),
`SINEX_SESSIONSTART_RECALL_WINDOW/LIMIT/TIMEOUT_SECS` (defaults `2h`, `8`, 4s).

For deeper history, use Polylogue MCP/search rather than guessing from memory.
`polylogued.service` is the live ingestion daemon; verify freshness with
`polylogued status` when it matters.
