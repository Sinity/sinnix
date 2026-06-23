# Sinity Environment Memory

> **This file is your persistent environment memory.** It contains compressed understanding of the entire development ecosystem, NixOS configuration, and project constellation. You start every session "pre-grokked".

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

### Safety And Git

- Preserve user work. Dirty trees are normal; never revert or overwrite changes
  you did not make unless explicitly asked.
- Treat destructive operations as explicit acts. State what will be deleted,
  reset, force-pushed, rebased, killed, or history-rewritten before doing it.
- Commit locally only when it is part of the requested workflow or established
  repo practice. Do not push unless asked.
- Stage by path, not broad sweeps, when secrets or unrelated work could be
  captured.

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
  `chrome-devtools-private`. Use `chrome-devtools-private-visible` when the user
  should be able to see the agent browser.
- **"my browser" / "the real browser" / "my tabs"** → use the user's live Chrome
  profile through `chrome-devtools` or `sinnix-chrome-control`. This is a
  high-authority surface: it can see authenticated pages/cookies and non-active
  tabs via `127.0.0.1:9222`.
- **"desktop" / "window" / "screen"** → use Hyprland and screenshot helpers:
  `sinnix-hypr-control`, `sinnix-keyboard-control`, and
  `sinnix-screenshot-control`.
- **"terminal" / "that terminal window" / "Codex pane"** → use Kitty remote
  control first: `sinnix-kitty-control list`, then capture/send/wait against a
  matching title/window. Prefer this over global keyboard injection for
  terminals.

Prefer typed MCP tools for browser work when available. Use the `sinnix-*`
helpers for desktop/window/terminal perception and control, and load the
`desktop-control-plane` skill when a task needs recipes, screenshots, HDR
handling, or careful GUI interaction. Run `sinnix-agent-control-status` when
you need a quick live probe of available control surfaces.

### Evidence and Telemetry

Use the control plane for live action; use the evidence plane to reconstruct
what happened. Do not infer history from the current screen/browser state when
Polylogue, Lynchpin, or Sinnix captures can answer directly.

- **AI session history** → Polylogue. `polylogued` tails Claude/Codex sessions;
  use Polylogue MCP/search for "what did agents do/say/change?" questions.
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

---



Capture only durable, non-obvious decisions, tensions, dead ends, and cross-session
insights. Do not mirror ordinary task notes there.

- Quick capture → `seed/YYYY-MM-DD-HHMMSS-slug.md`
- Append to an existing thread → `stream/NNN-name.md`
- Durable decision → `crystal/decisions/name.md`
- Unresolved contradiction → `tension/NNN-name.md`
- Dead end worth not rediscovering → `graveyard/name.md`

---

## World Model

@./world-model/index.md

---

## Operational Knowledge

@./operational/index.md

---

## Session recall (polylogue)

Claude Code has a `SessionStart` hook at
`~/.claude/hooks/sessionstart-polylogue-recall.sh`. If `polylogue` is on PATH,
the hook attempts to print up to three recent sessions matching the current
project directory via `polylogue --cwd-prefix "$CLAUDE_PROJECT_DIR" ... list`.
It exits silently when no matching archive data is available.

Do not assume that same hook exists in every agent runtime. Codex receives the
rendered global `AGENTS.md` and has the Polylogue MCP/server substrate, but its
configured hooks are separate.

For deeper history, use Polylogue MCP/search rather than guessing from memory.
`polylogued.service` is the live ingestion daemon for Claude/Codex session
JSONL; verify freshness with `polylogued status` or Polylogue queries when it
matters.
