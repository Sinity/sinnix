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
- No fake-temporal deferral. "This is a long session," "it's getting late,"
  "let's not push our luck," or similar wall-clock/turn-count framing is not a
  real risk assessment and must not be used to justify deferring, softening
  scope, or declining a task you have the context and tools to do now.
  Session length and turn count do not correlate with actual capability or
  actual risk; remaining context-window budget does, and it is directly
  checkable (ask, or read what the harness reports) instead of guessed at.
  Confirmed pattern (operator correction, polylogue, 2026-08-03, session at
  ~25% context): proposed deferring an architectural parser rewrite citing
  "end of an already very long session," when the actual state was
  well-informed (had just read the exact code in question) and low context
  pressure — the "long session" framing was empty filler standing in for an
  unstated real concern. If there is a genuine reason to defer or scope down
  (a concrete blast-radius/verification-cost tradeoff, needing operator
  sign-off on an irreversible action, a real missing capability), name that
  reason specifically and explain what state would need to change to resolve
  it — "some other time" is not a coherent answer unless you can say what is
  different about that other time. If nothing would concretely change, that
  is itself the signal the real blocker is something else (or there isn't
  one) — surface the real reason or proceed.
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
- Do not add tests, static scans, policy gates, allowlists, or deny lists that
  merely memorialize a refactoring diff: a renamed variable/type/module,
  deleted spelling, moved command, removed list entry, changed literal, or
  import path. A refactoring is verified through independently valuable
  behavior, type, build, and architecture checks—not by forbidding the old
  textual shape or requiring the new one. If such fossilized-diff checks
  already exist in the touched surface, remove them instead of updating them
  to encode the latest spelling. For ordinary cleanup, rely on source review,
  evaluation, and focused behavior checks.
- Never enforce a process or invariant by pattern-matching natural language.
  A lint or gate that greps prose — commit messages, close reasons, comments,
  docstrings, PR bodies, notes fields — for magic phrases ("follow-up",
  "tracked separately", resolver keywords, TODO markers) is machinery trying
  to programmatically interface with language it cannot parse. The results
  are reliably bad: false positives, phrasing chosen to satisfy the regex,
  suppression allowlists that themselves rot, and a false sense that the
  invariant is enforced. If an invariant matters enough to enforce
  mechanically, give it a structured carrier first (a typed field, a required
  id/link reference, a schema column, an exit code) and enforce that. If no
  structured carrier is worth adding, the invariant is enforced by judgment
  at authoring/review time — or it is not enforced. Prose is for readers.
  The same applies in reverse: never make prose load-bearing for machines by
  writing it in a stilted register so a tool can grep it later.
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

## Writing Style

Load the shared `writing-style` skill when writing or editing human-facing prose. Its trigger and full rules cover GitHub content, commit messages, chat replies, and documentation.

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
interaction. Run `sinnix-observe` when you need a live, correlated probe of
runtime and control surfaces.

### Agent Runtime Control

The current Claude Code and Codex hook boundary is recorded in
`docs/agent-hook-parity.md`. Generated Codex lifecycle hooks are enforced
where its schema provides the event; Claude-only model, Bash-policy, and
SubagentStop guards remain manual or unsupported for Codex rather than being
recreated through terminal scraping.

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

### Claude Code Dispatch Doctrine

Grounded in measured fanout ops (2026-08-02 report) + capability research
(2026-08-03, digest: polylogue `.agent/scratch/2026-08-03-claude-code-dispatch-capabilities.md`).
Facts here are version-gated; verify with `claude --version` / the
claude-code-guide agent when it matters.

- **Explicit model on every fresh Agent dispatch.** Sonnet default, Haiku for
  triage-grade read-only lanes, Fable/Opus permitted for judgment lanes
  (design review, adjudication, postmortem synthesis) as an explicit choice —
  never via inheritance. **This is mechanically enforced, hard, for every
  dispatch type** (tightened 2026-08-11 — the prior "named agent types get a
  soft warning only" exemption produced warnings with no enforcement teeth
  and was removed): a global PreToolUse hook DENIES any Agent dispatch —
  bespoke-prompt (general-purpose/claude/no type), a named agent definition
  (review/lane/triage/judge/Explore/Plan/...), or a teammate spawn — that
  omits `model` at the call site. A named agent's own frontmatter `model:`
  no longer exempts the call; the caller must still pass one explicitly, so
  every launch is auditable at the dispatch site, not only in a definition
  file the caller may not have open. Only `fork` is exempt (inherits
  context+model by design). On every ALLOWED dispatch the hook also emits a
  visible `systemMessage` confirming exactly which `subagent_type`/`model`
  (and teammate `name`, if any) was used — affirmative feedback, not just
  absence of a warning, visible across concurrent sessions' notification
  streams too.
- **Forks are exempt** (`/subtask`, `fork` subagent type, enabled via
  `CLAUDE_CODE_FORK_SUBAGENT=1`): they inherit the parent's context AND model
  by design (prompt-cache reuse). Right tool for context-heavy side-tasks;
  using a fork as a de-facto implementation lane violates the explicit-model
  rule in disguise. Forks cannot nest.
- **Agent teams are enabled experimentally**
  (`CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1`): teammates are full sessions
  sharing a task list + SendMessage mailboxes (`~/.claude/teams/`,
  `~/.claude/tasks/`). Known limits: no resume of in-process teammates, one
  team per session, no nesting, teammates do NOT inherit the lead's model
  (specify per spawn; they DO inherit effort). Treat as a lab capability:
  useful for coordinated parallel work, not yet load-bearing process.
- **Never poll background agents.** Completion notifications are automatic
  (Claude Code >=2.1.211). Monitor only with an until-condition; ScheduleWakeup
  only for genuine wall-clock deadlines (CI grace windows, external state).
- **Bake standing contracts into agent definitions** (`.claude/agents/*.md`):
  the markdown body IS the subagent's system prompt; frontmatter supports
  `model`, `effort`, `tools`/`disallowedTools`, `isolation: worktree`,
  `skills` preload, `memory`, `maxTurns`, per-agent hooks. Dispatch prompts
  should then carry only task content. `subagent_type` resolves against the
  frontmatter `name` field.
- **Scripted judgment calls** (durable drivers, cron, pipelines): prefer
  `claude -p --output-format json --json-schema '<schema>'` for validated
  structured verdicts (+ session id + cost), `--resume <id>` for continuity,
  `--bare` for deterministic scripted invocations. SIGTERM-safe (exit 143).

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
  sinnix-9u6). Plain `codex` uses the lean non-browser profile, while
  `codex-full` uses the full profile (GitHub, Context7, Polylogue, Lynchpin,
  Serena). Plain `claude` uses the lean profile.
  `claude-browser`/`codex-browser` add the Chrome DevTools MCP tier. `claude`
  is a shell alias to the `claude-lean` wrapper — the bare `~/.local/bin/claude`
  is deliberately unmanaged because Claude Code's installer claims and
  clobbers it on auto-update.
- **Alternate backends (full MCP profile)**: `claude-deepseek`/`codex-deepseek`
  (DeepSeek endpoints, key from agenix `deepseek-api-key`);
  `claude-local`/`codex-local` (local Ollama hub via the LiteLLM gateway on
  `127.0.0.1:4000`, `modules/services/litellm.nix` — local model names are
  defined once in its `model_list`); `muse-contrib`/`hermes-muse` (Muse Spark
  1.2 contributor tier via the Vercel AI Gateway, key from agenix
  `vercel-ai-gateway-key` — Meta gates the tier server-side and does not
  serve it to this account directly; prompts/completions on it may train
  Meta models, so keep confidential material on plain `muse`/standard
  tiers). LiteLLM stays local-models-only by design; remote backends are
  wired per-wrapper with agenix keys.
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

Invoke heavy test runners by their wrapper names (`pytest`, `cargo`,
`xtask`), never as `python -m pytest` or via absolute `.venv/bin/` paths: the
devshell routes commands into build/background slices by command name, and
bypassing the name also bypasses slice containment, stop-timeout caps, and
oomd policy (2026-07-11 forensics: a `python -m pytest` xdist swarm inherited
a protected agent scope and sat resident for 35 hours).

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
heavy-compile repos under `/realm/worktrees/` (NVMe), never `/tmp`:

```bash
mkdir -p /realm/worktrees
git -C /realm/project/<repo> worktree add -b <branch> /realm/worktrees/<name> origin/master
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
python -m lynchpin.cli.materialize --all    # DAG-orchestrated substrate materialization
python -m lynchpin.cli.current_state --start 2026-05-01 --end 2026-05-05
```

### Agent Orchestration (Multi-Agent Work)

When dispatching multiple coding agents to execute a plan (e.g., parallel lanes),
state the isolation model explicitly. The rules below are for worktree-isolated
agents only; if agents intentionally share one checkout, the coordinator owns
branching/committing/merging and agents should report patches or commit only by
explicit instruction.

**Codex model contract:** the coordinating interactive session uses
`gpt-5.6-luna` at high reasoning by default. Unattended implementation/review
workers use `gpt-5.6-terra` at high reasoning. Always pass the model and effort
explicitly and verify them in the launch receipt; never silently fall back to a
stale configured model. `gpt-5.5` is retired for new work.

**Worker verification ownership:** parallel workers verify their own changes,
not merely produce diffs. Prompts require focused real-route behavior tests,
exact-path static checks, and a broader affected-area check when a change spans
modules/contracts. Require an anti-vacuity statement naming the production
dependency exercised and the implementation mutation/removal that makes the
test fail. Toy replicas, test-only validators, self-authorized registries, and
mocks that only prove their own wrapping are rejected even when green. The
coordinator still performs independent review and publish-boundary gates.

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

**Foreground-only execution:** every command a worker runs must execute
synchronously in the worker's own turn; never launch a background job and
idle-wait on it across turns. A worker that backgrounds a test/build run
and then reports "waiting for it to finish" wastes real wall-clock and
coordinator attention every time (repeatedly observed, polylogue
2026-08-01 fanout) — always run it in the foreground and let the turn
take as long as it takes.

**Pre-flight checklist for each agent prompt:**

1. Specify exact files the agent OWNS vs AVOIDS
2. Include a "FIRST: comment on issue #N with scope" step
3. Include a "commit after each successful check" instruction
4. Warn about worktree cleanup: "commit or lose it"
5. After spawn, verify the worktree actually exists, is a linked worktree
   (not the main checkout), and is on the expected branch before trusting
   any output — `isolation: "worktree"` can silently fail to create one,
   in which case the agent runs directly in the main checkout and its
   diff is not isolated (confirmed incident, polylogue 2026-08-01: an
   agent's unreviewed schema-regeneration output landed directly in the
   coordinator's live tree). In repos with `devtools`:
   `devtools workspace verify-worktree <path> --expect-branch <branch>`.

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
- **Verification amortization**: workers run focused real-route checks plus the
  affected-area check their own change warrants. The coordinator runs the broad
  gate once per branch at the publish boundary, not once per item. In a
  multi-merge fanout session, run this broad gate on the *merged master
  state* at each merge-train boundary, not only pre-merge on the feature
  branch — a global drift-latch class (an unrelated enum/vocabulary change
  breaking an assertion elsewhere) is invisible to any single PR's affected-
  test selection and only surfaces when the merged result is tested as a
  whole. Schedule one full, non-affected-only suite run per heavy multi-merge
  session before declaring it done; per-PR CI deliberately skipping the heavy
  suite means nothing else will catch this class (confirmed incident,
  polylogue 2026-08-01: two master-red root causes found only by an
  incidental full-suite run after ~15 PRs had already merged clean).
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
  parses as JSON, then `git add`. The reimport hazard is not limited to
  checkout/merge: it fires on *any* `bd` invocation from an aging
  worktree, including a plain read-only `bd show <id>` — every `bd` call
  reimports the invoking checkout's `.beads/issues.jsonl` into the shared
  DB, so a worktree frozen at an older commit can silently time-machine
  live bead state on a coordinator's concurrent writes even from a lane
  that never touches beads intentionally (confirmed repeatedly, polylogue
  2026-08-01: 5+ coordinator closes reverted this way in one session).
  Lane agents dispatched into worktrees should make no `bd` writes at
  all; the coordinator should audit bead state (diff expected vs. `bd show
  --json`) at merge-train boundaries and re-apply anything reverted,
  rather than trust a single write to have stuck.
- **Batch `.beads/issues.jsonl` commits per unit of work, not per bd
  operation.** Confirmed pattern (polylogue, 2026-08-03): a single 5-hour
  fanout/triage session produced ~85 separate `chore(beads): ...` commits
  to `master`, one per bead closed/filed/annotated, drowning out real
  `feat`/`fix` commits in the log (67 of the last 100 commits on one repo
  were beads-only). The root cause was never subagents committing directly
  — lane agents correctly make no bd writes — it was the coordinator
  running `git commit` reflexively after every individual `bd close`/
  `bd create`/`bd update --notes` call instead of accumulating a batch.
  `bd export` re-derives the full jsonl regardless of how many bd calls
  preceded it, so batching costs nothing: do every bd write for one
  coherent unit of work (a full triage pass, one roadmap-digestion
  session, closing every bead landed by a merge train, one fanout wave's
  worth of findings), then `bd export` + a single `git commit` covering
  the whole batch, summarizing the batch in the subject (e.g. "close 10
  beads landed via merged PRs 3598-3605"). Do not commit mid-batch just
  because a natural pause occurred; commit at the boundary of the logical
  unit. A submodule/subrepo split for `.beads/` is not the fix — it
  relocates the same per-operation commit habit into a second repo's
  history and adds submodule-pointer-bump commits in the first; the fix
  is commit cadence, not commit location.

### Daily oracle digest

`/realm/project/sinnix/scripts/oracle` produces a daily reverse-prompting digest from the rawlog tail, recent project activity, open GitHub issues, and the latest lynchpin current-state pack, then asks `claude -p` for a four-section capped summary (Resume / Reverse-prompt questions / Drift / One thing — each bullet citation-required). Run `oracle` for today, `oracle --date YYYY-MM-DD` for a specific day, `--output PATH` to override the default `~/.local/share/oracle/YYYY-MM-DD.md` destination, and `--show` to also print to stdout. The CLI unsets `ANTHROPIC_API_KEY` before invoking claude so it uses the operator's subscription auth rather than the zero-balance automation key.

---

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
