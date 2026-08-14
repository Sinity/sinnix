# Sinity Environment Memory

> **This file is your persistent environment memory** — compressed
> understanding of the ecosystem, NixOS config, and project constellation.
> One flat file, no transclusion; Codex/Gemini read it via symlinks from the
> sinnix repo, so edits propagate to every agent instantly.

## Operating Contract

### Stance

- Be a finisher, not a planner. Carry work to a verified done-state unless a
  concrete blocker remains.
- No fake-temporal deferral. "Long session" / "it's getting late" framing is
  not a risk assessment; session length does not correlate with capability.
  Context budget does, and it is directly checkable. To defer or scope down,
  name the concrete blocker and what would change it — otherwise proceed.
- A concerning discovery is the next work item, not a stopping point. When
  investigation surfaces something real — a migration that left data behind,
  a crash-looping service, an anomaly near a planned deletion — the default
  is to keep going: find the root cause, fix it, verify the load-bearing
  fact directly, and finish the original task. "This needs its own
  investigation" names the next step, not a blocker; you are the
  investigator.
- Before halting or escalating, check the fact that actually decides the
  question, not a proxy for it. "Is the data byte-identical at the new
  location" is directly checkable even while "is the service healthy" is
  red; a failing proxy never justifies stopping when the direct check is
  available. Preconditions inherited from notes or earlier passes are
  re-verified, not obeyed — confirm the underlying reason still applies
  before propagating a halt.
- Escalate with reasoning attached: mark the judgment as your inference, and
  state the specific blocker, what you verified directly, and what evidence
  or decision would unblock it. Legitimate blockers are narrow: an
  irreversible step whose safety direct verification cannot establish,
  authority or consent the operator has not granted, or evidence that does
  not exist on this machine. None of this loosens destructive-action
  caution — verify-then-delete is part of finishing, and the stopping line
  stays at genuinely irreversible-and-ambiguous or consent-shaped
  questions, never at "I found something concerning."
- Preserve intent. Implement the requested outcome; do not substitute a safer,
  smaller, or more familiar product decision.
- Prefer surgical renewal. Remove obsolete paths, flags, wrappers, aliases, and
  stale docs in the same change that replaces them. No deprecation theater.
- Unfinished is not obsolete. When you find half-built work (a wired-but-unused
  parser, a dead-looking function with tests, a partially-connected pipeline),
  the presumption is to COMPLETE it, not delete it. Deletion needs positive
  evidence the capability is unwanted: superseded by a shipped replacement,
  contradicted by a recorded decision, or explicitly retired by the operator.
  "No production callers yet" is what half-done work looks like, not proof of
  abandonment; check git history, tracker items, and design docs for the
  intent before choosing removal over completion. When completion is too large
  for the current task, file a tracking item and leave the code; do not
  "clean it up" into a capability regression.
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
- Do not pipe command output into `tail`/`head`/`grep -c` truncating filters
  as a default habit — the transcript loses failures and stack traces behind
  a blind line count. Let commands print naturally; for genuinely voluminous
  output, redirect to a file and read it deliberately, or use the tool's own
  narrowing flags. Truncate only with a specific, stated reason.
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
- Do not add tests, static scans, policy gates, allowlists, or deny lists that
  merely memorialize a refactoring diff: a renamed variable/type/module,
  deleted spelling, moved command, removed list entry, changed literal, or
  import path. A refactoring is verified through independently valuable
  behavior, type, build, and architecture checks—not by forbidding the old
  textual shape or requiring the new one. If such fossilized-diff checks
  already exist in the touched surface, remove them instead of updating them
  to encode the latest spelling. For ordinary cleanup, rely on source review,
  evaluation, and focused behavior checks.
- Never enforce a process or invariant by pattern-matching natural language
  (grepping commit messages, close reasons, or notes for magic phrases). If
  an invariant matters enough to enforce mechanically, give it a structured
  carrier (typed field, id reference, exit code) and enforce that; otherwise
  it is enforced by judgment at review time — or not enforced. The reverse
  too: never write prose in a stilted register so a tool can grep it later.
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
- Do not turn transient live-host pressure into permanent project policy:
  handle resource incidents with one-shot overrides, stopping unrelated
  workloads, or the containment layer — never by permanently reducing build
  parallelism, cache behavior, retention, or coverage for a momentary spike.
- Before changing build policy for resource reasons, identify the pressure
  source in live evidence (process RSS/PSS, swap, PSI, cgroups, journal OOM
  events, active timers, disk IO state). A high `used` in `free` is not a
  leak; separate anon memory, tmpfs/zram, page cache, and D-state backlog.

## Writing Style

Load the shared `writing-style` skill when writing or editing human-facing prose. Its trigger and full rules cover GitHub content, commit messages, chat replies, and documentation.

## Ambient Control Model

Browser, desktop, and terminal control are normal local capabilities on this
machine. Interpret user language directly:

- **There is ONE browser** — the user's own Chrome, on `127.0.0.1:9222`, driven
  by `sinnix-chrome-control`. Agents share his profile deliberately: wherever
  he is authenticated, so are they, with nothing to seed and nothing that goes
  stale. The former agent-private profile is deleted, along with headless mode
  (headless announces itself in the User-Agent and loses to bot checks that a
  real window passes).
- **"your browser" / "an agent browser"** → `sinnix-chrome-control agent-window
  [--url ...]`. Opens a NEW WINDOW and parks it on the hidden
  `special:agentbrowser` workspace, so it takes no focus and touches none of
  his tabs. Isolation is per-window now, not per-profile. Hidden windows still
  run JS and still screenshot — verified — because CDP goes through the
  renderer, not the compositor. **F7** shows or hides it; do not activate it
  for him, just say it is there.
- **"my browser" / "the real browser" / "my tabs"** → the same Chrome, but act
  on his EXISTING pages (`list-tabs`, then operate on a specific page id).
  High-authority: authenticated pages, cookies, non-active tabs. Never
  navigate or close a page he is using unless he asked for exactly that.
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
interaction. Run `sinnix-observe` when you need a live, correlated probe of
runtime and control surfaces.

### Agent Runtime Control

The current Claude Code and Codex hook boundary is recorded in
`docs/agent-hook-parity.md`. Generated Codex lifecycle hooks are enforced
where its schema provides the event; Claude-only model, Bash-policy, and
SubagentStop guards remain manual or unsupported for Codex rather than being
recreated through terminal scraping.

Prefer native non-interactive runtimes for unattended work; use Kitty only
when a human needs a visible, interruptible process. Launch commands, auth
rules, and mode constraints live in the `agent-orchestration` skill
(`references/runtime-modes.md`). Standing rules: set model/effort per run,
never inherit stale defaults; the browser is shared by every concurrent agent
AND by the operator — own explicit page target ids, never activate another
agent's target, never touch a page you did not open; Kitty workers keep focus and route to other workspaces
silently; never inject model/effort changes into a live agent TUI while it is
sampling.

### Claude Code Dispatch Doctrine

Mechanics, caveats, and history live in the `claude-self-knowledge` skill.
The standing rules:

- **Explicit model on every fresh Agent dispatch** — Sonnet default, Haiku
  for triage-grade read-only lanes, Fable/Opus for judgment lanes as an
  explicit choice. Hard-enforced: a global PreToolUse hook DENIES model-less
  dispatches of every type and emits a visible confirmation on allowed ones.
- **Forks are exempt**: they inherit context and model by design. Using a
  fork as a de-facto implementation lane violates the rule in disguise.
- **Agent teams: narrowly adopted** (env-gated) for read-only
  research/synthesis tasks — own blinded pilot verdict 2026-08-12
  (adopt-qualified; see claude-self-knowledge skill). Implementation and
  write-capable work keeps the subagent doctrine; teammates do not inherit
  the lead's model.
- **Never poll background agents** — completion notifications are automatic.
  Monitor only with an until-condition; ScheduleWakeup only for genuine
  wall-clock deadlines.
- **Bake standing contracts into agent definitions** (`.claude/agents/*.md`);
  dispatch prompts carry only task content.
- **Scripted judgment calls**: `claude -p --output-format json
--json-schema` for validated verdicts; `--resume` for continuity;
  `--bare` for deterministic scripted invocations.

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

Raw-log lives at `/realm/data/knowledgebase/logs.raw-log.md`. It is the
append-only, low-friction operator stream used by `rawlog`, `rawlog-capture`,
and `oracle`; read it when the user references raw-log/rawlog, recent subjective
context, or "what have I been saying/thinking lately?"

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

> **Why**: only the nix-build.slice placement caps build memory; bypassing
> the wrapper lets Rust builds consume all 32 GB. Do not insert
> `check --no-build` before `switch` as hygiene — `switch` already
> evaluates/builds; repeating eval only loads the recovery path.

Agent CLIs self-update via npm bootstrap (`~/.local/state/<agent>/npm`,
persisted) — no Nix rebuild needed.

## Filesystem Structure

### /realm - The Data Kingdom

```
/realm/
├── project/           # All active project repositories
├── data/              # Canonical PERSONAL data lake (see below)
├── media/             # Consumption/media collections (Steam, books, model weights, stashbox)
├── state/             # Always-on service state (journal, polylogue, machine-telemetry, containers; nodatacow subvols)
├── staging/           # Backup staging (drained to /outer-realm by borg jobs)
├── worktrees/         # Agent/compile-heavy git worktrees (not aged)
├── inbox/             # Staging area for retired/incoming data + downloads
└── tmp/               # Throwaway analysis output, aged shell TMPDIR
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
  tmpfs and heavy churn belongs on NVMe. Put ad-hoc output FILES in
  `/realm/tmp/work/` (auto-aged 30d), never at the `/realm/tmp` root — the
  root is deliberately unaged and root litter requires manual sweeps.
- Use `/realm/worktrees/` for agent worktrees or any compile-heavy checkout.
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

Flow: sinnix enables the service stack → sinex captures events
(scribe-tap, polylogue) → lynchpin aggregates everything (ActivityWatch,
Atuin, git, health, chats) into calendar views, baselines, narratives.

### Environment Variables (set by sinnix)

```
SINEX_ROOT=/realm/project/sinex
LYNCHPIN_REPO_ROOT=/realm/project/sinity-lynchpin
POLYLOGUE_ROOT=/realm/project/polylogue
KNOWLEDGEBASE_ROOT=/realm/data/knowledgebase
```

### Documentation Map

Sinnix grok notes: `sinnix/.agent/scratch/` (architecture + machine map);
lynchpin data sources: `sinity-lynchpin/docs/reference/data-sources.md`;
data inventory: `/realm/data/INVENTORY.md`. Project detail (structure,
patterns, workflows) lives in each project's `CLAUDE.md`.

## Agent Context Conventions

- **`CLAUDE.md` is the canonical instruction file everywhere** — one flat file
  per repo, no `@`-transclusion. `AGENTS.md` in each repo is a committed
  symlink to `CLAUDE.md`, so Claude, Codex, and Gemini always read identical,
  current content.
- **MCP profiles**: registry source of truth is `flake/data/mcp-registry.nix`
  in sinnix; wiring in `modules/features/dev/agents/`. Plain `claude`/`codex`
  = lean profile; `claude-full`/`codex-full` = full (GitHub, Context7,
  Polylogue, Lynchpin, Serena); `*-browser` adds Chrome DevTools MCP. The
  bare `~/.local/bin/claude` is deliberately unmanaged (the installer
  clobbers it); `claude` aliases the managed lean wrapper.
- **Alternate backends**: `claude-deepseek`/`codex-deepseek` (agenix
  `deepseek-api-key`); `claude-local`/`codex-local`/`hermes-local` (local
  Ollama hub via LiteLLM `127.0.0.1:4000`; model names live once in
  `litellm.nix`); `muse-contrib`/`hermes-muse` (Muse Spark contributor tier
  via the Vercel AI Gateway, agenix `vercel-ai-gateway-key` — Meta gates the
  tier server-side; **prompts/completions on it may train Meta models — keep
  confidential material off it**). LiteLLM stays local-models-only; remote
  backends are wired per-wrapper with agenix keys.
- **Shared skills** live in `dots/_ai/skills/` (sinnix repo) and are linked
  into `~/.config/claude/skills`, `~/.codex/skills`, `~/.gemini/skills`.
- **Desktop environment**: Hyprland (Wayland) + Noctalia shell; terminals
  kitty; browser qutebrowser + Chrome (CDP on :9222).
- **Dotfile pattern**: everything in sinnix `dots/` reaches `$HOME` via Home
  Manager out-of-store symlinks — edits propagate instantly without rebuild.
- **Context7**: documentation discovery via `resolve-library-id` →
  `query-docs`. Cheap, prevents stale-API mistakes; use it for unfamiliar or
  fast-moving third-party APIs.

## Common Workflows

### Workspace Inventory

For a fast read-only snapshot across many repos, don't hand-roll `find`/`git
status` loops: `python3 dots/_ai/tools/workspace_recon_scan.py --root
/realm/project` (sinnix repo; `--changed-only --with-size --json` variants).

### Heavy Agent Work

Recognized project dev environments install transparent wrappers for common
heavy commands. In Sinex and Polylogue devshells, ordinary commands such as
`xtask`, `cargo`, `pytest`, `uv`, `polylogue`, and `nix` are routed into the
Sinnix build/background slices automatically, so agents should run the normal
project command first.

Invoke heavy test runners by their wrapper names (`pytest`, `cargo`,
`xtask`), never as `python -m pytest` or absolute `.venv/bin/` paths —
routing is by command name, and bypassing it bypasses slice containment,
stop-timeout caps, and oomd policy (2026-07-11: an unwrapped xdist swarm sat
resident in a protected scope for 35 hours).

Resource containment is not a verification contract: in Sinex use `xtask`,
which owns the schema/SQLx/feature/formatting assumptions — don't bypass it
with direct `cargo` for a narrower-looking signal. Resource pressure during
heavy work is a scheduling problem, not a project-semantics problem: one-shot
overrides or the wrapper/slice layer, never durable project defaults.

Outside a recognized devshell, scope long/heavy one-offs explicitly:
`sinnix-scope {background|build|nix-build} -- <cmd>`.

**Worktree placement (wear policy):** heavy-compile worktrees go under
`/realm/worktrees/` (NVMe), never `/tmp` — a Rust `CARGO_TARGET_DIR` writes
multiple GB per build.

**Sinex tests from a worktree** need the live dev-DB `DATABASE_URL` (and so
does `git push` past the drift guard) — recipe in sinex's CLAUDE.md.

### Data Analysis (lynchpin)

`cd /realm/project/sinity-lynchpin && just` lists all recipes;
`python -m lynchpin.cli.materialize --all` runs the DAG-orchestrated
substrate materialization; `...cli.current_state --start/--end` for windows.

### Agent Orchestration (Multi-Agent Work)

Full procedure (worktree discipline, write-scope separation, pre-flight and
post-merge checklists, batching shapes, Codex model contract) lives in the
`agent-orchestration` skill — read it before any multi-agent dispatch. The
non-negotiables:

- State the isolation model explicitly (worktree-isolated vs shared checkout;
  in shared checkouts the coordinator owns branching/committing/merging).
- Worktree agents MUST `git commit` every logical chunk — isolation
  auto-cleanup discards uncommitted work. Never `cd` to the main checkout
  from inside a worktree.
- After spawn, verify the worktree exists, is a linked worktree, and is on
  the expected branch before trusting output — `isolation: "worktree"` can
  silently fail and land the agent in the live tree.
- Foreground-only execution: workers run every command synchronously in
  their own turn; never background-and-wait.
- Workers verify their own changes with real-route tests plus an
  anti-vacuity statement; the coordinator still reviews independently.
- Codex contract: `gpt-5.6-luna` (coordinator) / `gpt-5.6-terra` (workers),
  high reasoning, always explicit, verified in the launch receipt.

### Cross-item batch execution (content-aware)

The unit of work is a cluster of related items, not one tracker item at a
time; full shapes in the `agent-orchestration` skill
(`references/batch-and-worktree-execution.md`). The rules:

- Overlapping footprints: one branch, rewrite the area once against every
  item's AC, per-item commits, one sweep PR with an AC matrix.
- Disjoint footprints: separate PRs, pipelined — never idle-wait on CI.
- Parallel worktree lanes only for ≥3 disjoint, execution-grade lanes with
  no shared hotspot files; otherwise one agent pipelining wins.
- Run one full, non-affected-only suite on merged master per heavy
  multi-merge session — per-PR CI cannot catch cross-PR drift latches.
- Beads under branch churn: every `bd` call reimports the invoking
  checkout's jsonl (stale branches/worktrees time-machine live state); lane
  agents make no `bd` writes; batch jsonl commits per unit of work, not per
  operation. Hazard recipes in the `beads` skill.

### Daily oracle digest

`scripts/oracle` (sinnix) builds a daily reverse-prompting digest from the
rawlog tail, project activity, and lynchpin state via `claude -p`
(subscription auth). Run `oracle`; flags via `--help`.

## Git Protocol

Load the shared `git-protocol` skill for detailed Git, GitHub, commit, branch, pull request, staging, merge, conflict, and publication procedure. The operating contract above remains authoritative for safety, repository policy, and direct-master exceptions.

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

Serena is registered for Codex, Claude, Gemini, and VS Code. Default sequence:

1. `rg` for exact literal text and unindexed/generated surfaces.
2. Serena near an edit boundary: symbol overviews, precise lookup, references
   grouped by containing symbol, diagnostics, rename, safe-delete, symbol-body
   replacement.

Serena is configured for `sinex`, `polylogue`, `sinity-lynchpin`, and `sinnix`
via `.serena/project.yml`; it activates from the current working directory. If
Serena tools are missing in Codex despite an active config, use tool discovery
for the exact operation name — lazy loading can hide active tools.

Serena state lives under `~/.local/share/serena` (installs under
`~/.local/state/serena`).

## Thinking in Markdown

Externalize reasoning to scratch files. Context is expensive, files are cheap.

**When:** non-trivial analysis, multi-step debugging, architectural decisions;
anything that took >1 tool call to discover; cross-session work.

**Where:** global → `~/.claude/scratch/NNN-<topic>.md`; project-specific →
`.agent/scratch/<date-or-NNN>-<topic>.md` (create early, ensure `.gitignore`
covers it). **Never `.claude/` for per-project content** — Claude Code
treats it as protected and prompts on every write. YAML frontmatter
(`created`, `purpose`, `status`, `project`), then Context/Findings/Outcome.
When referring the user to a scratch file, summarize the key points in your
reply — don't just point. Projects may pin notes in CLAUDE.md via a "Pinned
Notes" section of bare `@path` lines (Claude-only transclusion).

## Session Recall (hooks)

SessionStart hooks (`dots/claude/hooks/sessionstart-{polylogue,sinex}-recall.sh`
in the sinnix repo, referenced dots-direct from managed-settings.json; Codex
runs the
same commands) print recent matching sessions and a Sinex
machine-context block; both exit silently when data is unavailable. For deeper
history use Polylogue MCP/search rather than guessing from memory;
`polylogued.service` is the live ingestion daemon — verify freshness with
`polylogued status` when it matters.
