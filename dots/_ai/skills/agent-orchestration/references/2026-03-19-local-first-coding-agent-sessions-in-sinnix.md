# Local-First Coding-Agent Sessions in Sinnix

## Executive summary

Sinnix already contains substantial “agent operations” groundwork: a Kitty-first terminal environment with socket-only remote control, an always-on terminal capture wrapper (Asciinema + JSON metadata/events), an “agent session restore” mechanism that reopens interrupted sessions into Kitty tabs after reboot, and Codex “skills” that orchestrate multiple agent instances via Kitty remote control. fileciteturn23file0L1-L1 fileciteturn20file0L1-L1 fileciteturn31file0L1-L1 fileciteturn31file0L1-L1 fileciteturn22file0L1-L1 fileciteturn19file0L1-L1 fileciteturn29file0L1-L1

The missing layer for the desired outcome (“sessions independent from a terminal window; attach/detach; multiple viewports; legible state; many concurrent sessions”) is not raw tooling so much as **a session identity + metadata + control-plane** that sits above terminals and above any single agent vendor UX. The key design move is to explicitly separate:

- **Session identity** (stable, named, durable: “what work is happening?”)
- **Viewport identity** (ephemeral, attachable: “where am I looking from?”)

That separation can be solved generically and robustly today with a **tmux-first session-as-a-service model supervised by systemd user units**, while selectively using agent-native persistence and status surfaces where they exist (notably Codex App Server threads, Codex resume/fork commands, and Claude Code resume/fork/checkpointing). citeturn25search2 citeturn12view0 citeturn14view2 citeturn16view0 citeturn19view0

**Recommendation:** implement a Sinnix “agent session manager” as a small local-first control plane (CLI first, optional TUI later) that:

- launches each coding-agent session as a **named systemd user unit** that owns a **tmux session** (or a Codex App Server thread, when opted-in),
- records standardized metadata (repo/worktree/cwd/model/provider/session IDs),
- supports “list / attach / observe / interrupt / archive / fork” flows consistently across Codex + Claude Code, and
- integrates with **Polylogue** as the durable transcript index/search UI (especially for agent-native JSONL transcripts and exports). fileciteturn26file0L1-L1 fileciteturn24file0L1-L1 fileciteturn35file0L1-L1 citeturn14view0 citeturn23view0

This approach preserves terminal-native workflows, avoids browser-first assumptions, and uses NixOS/systemd patterns already present in Sinnix (graphical-session user services, hardening templates, timers). fileciteturn26file0L1-L1 fileciteturn27file0L1-L1

## Current-state constraints inferred from the repos

Sinnix’s current environment strongly shapes what will feel “pleasant day-to-day.”

### Terminal and capture baseline

Sinnix configures **Kitty** as the default terminal (`TERMINAL=kitty`) and enables Kitty remote control in **socket-only** mode, listening on a user runtime socket (`unix:${XDG_RUNTIME_DIR}/kitty-${USER}`). fileciteturn23file0L1-L1

Kitty is configured to launch a **captured shell wrapper** (`shell = ~/.local/bin/sinnix-captured-shell`). fileciteturn23file0L1-L1 This wrapper, together with Zsh hook scripts, builds a structured capture system:

- Shell sessions are recorded using Asciinema, with per-session metadata written to `session.json` and command/activity events written to `events.jsonl`. fileciteturn21file0L1-L1 fileciteturn22file0L1-L1
- The capture system is organized under a Sinnix “captures root” (used for Zsh history and capture artifacts). fileciteturn24file0L1-L1

This is already a strong foundation for “durable enough” and “inspectable later,” but it currently tracks **terminal lifetimes**, not a stable “agent session identity.”

### Existing session restoration and orchestration primitives

Sinnix includes an **agent session restore feature** plus an activation script that runs in the desktop session and attempts to restore sessions into Kitty after reboot. fileciteturn20file0L1-L1 fileciteturn19file0L1-L1

The restore script is explicitly oriented around Kitty remote control + prior capture metadata: it discovers sessions and reopens commands into new tabs/windows. fileciteturn19file0L1-L1

Sinnix also includes a Codex “agent-orchestration” skill that already treats agents operationally—discovering agent instances by Kitty window title, sending commands, launching many tabs, and supporting both batch and interactive “Kitty mode.” fileciteturn29file0L1-L1 fileciteturn31file0L1-L1 fileciteturn32file0L1-L1 fileciteturn33file0L1-L1 fileciteturn34file0L1-L1

This indicates a clear bias toward:

- terminal-native control surfaces,
- high transparency (“drive the terminal, not a hidden API”),
- and multi-session work across projects. fileciteturn29file0L1-L1

### Agent tooling and persistence already in scope

Sinnix’s shell feature persists the major agent state directories:

- `~/.config/claude` (Claude Code runtime + config) and a symlink `~/.claude -> ~/.config/claude`. fileciteturn24file0L1-L1
- `~/.codex` (Codex CLI config + state). fileciteturn24file0L1-L1
- `~/.claude.json` (Claude CLI auth token file). fileciteturn24file0L1-L1

Sinnix also ships a `claude-team` wrapper that launches Claude Code inside tmux, which is an existing integration point for “team split panes” and suggests tmux is already acceptable as an operator primitive. fileciteturn24file0L1-L1

### Security posture and risk

Sinnix’s Codex config includes settings that prioritize convenience over guardrails (for example, `approval_policy = "never"` and `sandbox_mode = "danger-full-access"`). fileciteturn19file0L1-L1

Separately, Sinnix includes a reusable systemd hardening library (templates for `ProtectSystem`, `ProtectHome`, `NoNewPrivileges`, syscall filtering, and service restart policies), which is a natural place to enforce optional containment for long-running agent services. fileciteturn26file0L1-L1

### Polylogue in the ecosystem

Polylogue’s mission is a **local-first AI chat archive** into SQLite (FTS5 + vector search) and includes parsing for Claude Code and Codex exports, plus an MCP server for assistant integration. fileciteturn35file0L1-L1

Polylogue also already has a Textual-based TUI browser for navigating stored conversations, which is relevant as a ready-made local “transcript viewer” surface. fileciteturn36file0L1-L1

Implication: Sinnix can treat Polylogue as the durable transcript “backend” and focus Sinnix work on session management and operator UX.

## Ecosystem survey

This section answers the research questions (A–H) with emphasis on primary/official sources and maintainer-grade discussions as of **2026-03-19**.

### Runtime and session architecture

**Codex App Server (current state, March 2026)**
The Codex App Server is explicitly designed as a long-lived process hosting Codex “threads” with a bidirectional JSON-RPC protocol over stdio (JSONL) or an experimental WebSocket transport. citeturn14view0turn13view3turn13view6

Key properties relevant to “session as service”:

- **Durable session container = thread.** App Server docs define a thread as a conversation containing turns and items, and expose lifecycle methods including `thread/start`, `thread/resume`, `thread/fork`, `thread/list`, `thread/read`, `thread/archive`, `thread/unarchive`, and `thread/rollback`. citeturn14view1turn14view2turn14view4turn8view1turn8view4
- **Persistence format and archival semantics.** App Server states that persisted thread logs are stored as JSONL on disk, and `thread/archive` moves the persisted JSONL log into an archived sessions directory. citeturn8view4turn13view5
- **Multi-client subscription model.** The App Server handshake is per-connection (`initialize` then `initialized`), and `thread/start` “automatically subscribes you to turn/item events for that thread.” Unsubscribe semantics are per connection; when the last subscriber unsubscribes, the server unloads the thread and emits `thread/closed`. citeturn13view2turn14view2turn8view3turn8view4
- **Blocked/waiting states are first-class.** App Server emits `thread/status/changed` with runtime status and active flags like `waitingOnApproval`. citeturn8view2turn8view3
- **Approvals are structured events.** Approvals occur via server-initiated JSON-RPC requests (e.g., command execution approval requests) that pause the turn until the client responds; the doc provides an explicit message order. citeturn8view6turn7view10
- **Protocol maturity caveat.** Codex CLI docs label `codex app-server` as “Experimental” and “primarily for development and debugging” that “may change without notice,” and WebSocket transport is explicitly described as experimental/dev-only. citeturn13view6turn14view0turn13view3

**Codex TUI attachment / remote workflows (current direction, March 2026)**
OpenAI’s App Server engineering post describes a plan to refactor the TUI/Codex CLI to use App Server so it behaves like any other client, enabling workflows where a TUI connects to a Codex server running remotely and continues work while a laptop sleeps/disconnects. citeturn7view9turn7view8

This is precisely the “session not bound to one terminal window” design philosophy, but the post frames it as an “unlock” / plan rather than a guaranteed present-state in the shipped CLI. citeturn7view9

**Codex CLI session persistence and lifecycle (current state, March 2026)**
Codex CLI’s command reference documents:

- `codex resume` for interactive sessions, resuming by session ID or resuming the most recent session scoped to the current working directory unless `--all` is used. citeturn12view0turn12view1
- `codex exec resume` for resuming exec sessions, with `--last` and `--all` semantics and optional follow-up prompt. citeturn12view0turn12view6
- `--ephemeral` mode, which “run[s] without persisting session rollout files to disk.” citeturn12view5
- `codex fork`, which creates a new thread from a previous interactive session (with `--last` support). citeturn12view1

Net: Codex already provides durable “conversation identity” separate from a terminal window, but App Server is the path to first-class multi-client status/approval/streaming control.

**Claude Code session equivalences (terminal-native, March 2026)**
Claude Code’s CLI reference provides:

- `claude -c` (continue most recent conversation in current directory), and `--continue` as an alias. citeturn16view0
- `claude -r "<session>" "query"` and `--resume` supporting resuming a session by ID or name, and an interactive picker when you don’t specify one. citeturn16view0
- `--fork-session` to fork on resume so a new session ID is created. citeturn16view0turn19view0
- `--no-session-persistence` to disable session persistence (print mode only). citeturn16view0

Claude Code also has a first-class “checkpointing” concept: checkpoints are created automatically before edits, persist across resumed conversations, and are cleaned up along with sessions after 30 days (configurable). citeturn19view0

However, Claude Code does not expose an App Server–like multi-client attach model in these docs; sessions are resumable state, but the process remains “single TUI per terminal window” at a time, with concurrency typically meaning multiple separate sessions. (This is an inference based on the surface area documented: resume/fork/continue, but no per-session multi-subscriber API.) citeturn16view0turn18view0turn19view0

### Multiplexing layers and known working patterns

**Terminal multiplexer as the session substrate (tmux)**
The tmux man page explicitly models a server managing clients and sessions; clients attach to sessions and can be detached. `attach-session -d` detaches other clients, and `-r` attaches as read-only. citeturn25search2turn25search1

This “client ↔ session” separation is exactly the same conceptual split we want for “viewport identity vs session identity,” and it is mature and battle-tested for terminal-native workflows.

**Terminal multiplexer as a multi-user/multi-client substrate (Zellij)**
Zellij’s command reference documents `zellij attach`, `list-sessions`, and `kill-sessions`. citeturn26search1

Zellij is explicitly “multiplayer”: a release post describes multiple users attaching to a session, with per-user cursor/focus indicators, and includes a built-in “disconnect other clients” function via the session manager. citeturn26search0turn26search6

Zellij also provides a built-in **web client** that can start/attach/resurrect sessions via a URL scheme and requires authentication with a token. citeturn26search7 This is highly relevant to “attach/detach from multiple surfaces,” but it violates the “terminal-native, not browser-first” preference unless treated as optional.

### Observability and transcript models in the ecosystem

**Codex App Server transcript structure**
App Server threads persist as JSONL logs on disk and can be read without resuming via `thread/read` (no subscription). citeturn8view4turn7view2turn13view5 This is ideal for “read without attaching” and “summaries/indexing.” The protocol also exposes status events and approvals as structured messages. citeturn8view2turn8view6

**Claude Code transcript structure and filesystem layout caveats**
Claude Code includes `CLAUDE_CONFIG_DIR` to customize where it stores configuration/data files. citeturn21view0

Historically, on Linux, a Claude Code issue reports that it wrote configs/cache to `~/.claude.json` and `~/.claude` rather than following XDG base directory conventions. citeturn24view0

A serious operator-oriented tool (`ccusage`) reports that Claude Code’s default session data location changed in Claude Code v1.0.30+ from `~/.claude/projects/` to `~/.config/claude/projects/` (and that this change was undocumented), and that session usage data is stored as JSONL per session under per-project directories. citeturn23view0
Because this is third-party documentation, treat it as “best-effort operational reality” rather than canonical, and validate on your machine by observing actual paths and files. (Validation experiments are included later.) citeturn23view0turn24view0

**Polylogue as a local transcript indexer and viewer**
Polylogue is designed to import multiple providers (ChatGPT, Claude, Codex, Gemini) into SQLite with FTS and vector search and provides an MCP server plus a Textual TUI for browsing conversations. fileciteturn35file0L1-L1 fileciteturn36file0L1-L1

This is strong prior art for the “searchable transcripts/logs” requirement—particularly if Sinnix ensures agent sessions generate ingestible artifacts (JSONL logs, exports, “output-last-message” snapshots, etc.). fileciteturn35file0L1-L1 fileciteturn33file0L1-L1 citeturn12view0

### Concurrency and orchestration patterns

Sinnix already favors multi-instance orchestration through:

- Kitty remote-control instance discovery and command injection patterns; fileciteturn31file0L1-L1
- batch prompt execution and mass tab launching for agent parallelism; fileciteturn32file0L1-L1
- explicit support for “agent teams” within Claude Code via tmux wrapper. fileciteturn24file0L1-L1

Externally, Codex App Server formalizes concurrency with a thread manager that hosts multiple core threads and streams events. citeturn7view8turn14view0

### Security and safety boundaries

Codex App Server’s design explicitly models approvals as protocol-level events that pause work until the client responds, and includes sandbox-related context in approval requests (including optional network approval context and additional permissions in experimental API mode). citeturn8view6turn7view10

Claude Code exposes extensive permission and tool gating flags in the CLI reference (allowed/disallowed tools, permission modes, and explicit “dangerously skip permissions” controls). citeturn16view0

Sinnix currently sets Codex approvals to never and sandbox to danger-full-access, which is a deliberate choice but increases the need for higher-level auditability and “safe abort” flows in the session manager. fileciteturn19file0L1-L1

## Architecture options and comparison table

The options below focus on _which layer owns session identity_ and _how viewports attach_.

| option                                                                                            | session persistence                                                                                                                          | attach/detach                                                                                                             | multi-view support                                                                                                         | UX quality                                                                                              | implementation complexity                                                              | compatibility with terminal-native agents                     | NixOS fit                                                                                                          | recommendation                                                                                          |
| ------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------- | ------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------- |
| tmux session as service (systemd user units start tmux sessions; Kitty is a viewport)             | strong (process survives terminal; can be boot-persistent with linger) citeturn25search2turn25search6                                    | excellent (`tmux attach`, detach; detach others; read-only attach) citeturn25search2turn25search1                     | excellent (multiple tmux clients; read-only observer) citeturn25search2turn25search1                                   | high for terminal power users; predictable                                                              | moderate (need wrapper CLI + metadata + systemd unit generator)                        | excellent (runs any agent TUI)                                | excellent (systemd user services are native; hardening templates available in Sinnix) fileciteturn26file0L1-L1 | **primary baseline**                                                                                    |
| zellij session as service (systemd user units start zellij sessions; optional web client)         | strong (sessions separate from terminal; can resurrect; web client can reattach) citeturn26search1turn26search7                          | good (`zellij attach`, session manager) citeturn26search1turn26search6                                                | good (multi-user attach; can disconnect other clients; resizing constraints exist) citeturn26search0turn26search6      | high for users who prefer zellij UX; web client is a bonus but not terminal-native citeturn26search7 | moderate-high (similar to tmux path + different affordances; possible browser surface) | excellent (runs agent TUIs)                                   | excellent                                                                                                          | viable alternative; consider if zellij is preferred                                                     |
| Codex App Server–centric (run `codex app-server` as daemon; build client(s); Claude via tmux)     | very strong for Codex threads (JSONL thread logs; archive; resume/fork; thread read without resume) citeturn8view4turn7view2turn13view5 | excellent for Codex (protocol-level resume, subscribe/unsubscribe; ws optional) citeturn14view2turn13view3turn8view3 | excellent for Codex (structured status, approvals, multi-connection subscriptions) citeturn8view2turn8view6turn8view3 | potentially best-in-class (blocked states, previews, list/read without attach)                          | high (you own a client and must track experimental API drift) citeturn13view6       | partial (Codex only; Claude still needs a separate substrate) | good (daemon as user service fits well)                                                                            | **optional “power-up”**, not baseline (API is explicitly experimental for dev/debug) citeturn13view6 |
| “PTY daemon” per session (dtach/pty virtualization + custom attach client; tmux-like but bespoke) | strong if done right                                                                                                                         | good if done right                                                                                                        | variable (hard to get multi-client + tty correctness right)                                                                | can be good, but likely rough edges                                                                     | very high (hardest correctness domain: terminals, input routing, scrollback)           | aims to be universal                                          | okay                                                                                                               | not recommended for Sinnix first pass; defer                                                            |

**Why the tmux-first baseline wins in Sinnix**
It matches Sinnix’s existing stance: terminal-native, keyboard-driven, local-first, and already shipping tmux and wrappers built around it. fileciteturn24file0L1-L1 It also cleanly separates session identity (tmux session + systemd unit) from viewports (Kitty tabs, SSH sessions, multiple terminals), which is the core framing of the problem.

Codex App Server offers a better _agent-native state model_ than tmux ever will (status flags, approvals, archive/read), but its own docs position standalone app-server usage as “development/debugging” and subject to change. citeturn13view6turn14view0 That makes it ideal as an opt-in “acceleration path,” not the base contract for all sessions.

## UX patterns and operator workflows

This section is intentionally concrete: proposed flows, commands, and semantics. The goal is “pleasant to operate day-to-day” under load (many concurrent sessions).

### Canonical objects and naming

Adopt three explicit IDs:

- **Sinnix session ID**: stable handle in Sinnix (human name + opaque UID). Example: `projX/auth-refactor#2026-03-19T1012Z`.
- **Agent-native ID** (optional):
  - Codex: session/thread UUID used by `codex resume` or App Server `threadId`. citeturn12view0turn7view2
  - Claude Code: session ID or name used by `claude --resume`. citeturn16view0
- **Viewport ID**: terminal window/tab/pane identity (Kitty window id, tmux client id, etc.). Sinnix already has Kitty window discovery machinery. fileciteturn31file0L1-L1

Store these mappings in a tiny local DB/ledger (SQLite or JSONL), not “in your head.”

### Start new agent session

**Proposed flow (interactive, “I want to work with an agent now”):**

1. Operator runs: `sx agent start codex` (or `sx agent start claude`) from a repo root.
2. Sinnix determines repo/worktree/cwd metadata (Sinnix already has a `find-flake-root` helper and uses git root detection patterns). fileciteturn24file0L1-L1
3. Sinnix creates a session record:
   - title (prompted, default derived from repo + branch),
   - cwd/worktree path,
   - agent type + model (default profile),
   - and chooses a tmux session name and systemd unit name.
4. Sinnix launches a _detached_ tmux session via systemd user service, then opens a Kitty tab that attaches.

This matches “session independent of a shell window,” because tmux (and systemd) own the process lifetime, not Kitty. citeturn25search2turn25search6

**Batch/overnight flow (unattended jobs, reproducible artifacts):**

Sinnix already has a strong batch runner pattern in its Codex skill scripts (`codex exec`, `--output-last-message`, JSONL mode, prompt files). fileciteturn33file0L1-L1
Make this first-class as: `sx agent run-batch codex --plan plan.json` which runs as a transient systemd user service and writes artifacts into a standardized session directory.

### Reattach an existing session

**Flow:**

1. `sx agent ls` shows active sessions grouped by repo/worktree, with:
   - name, age, last activity timestamp, agent type/model, and status summary.
2. `sx agent attach <id>` opens a Kitty tab and runs `tmux attach -t <tmux_session>`.

Advanced attach modes:

- `sx agent observe <id>` attaches read-only (`tmux attach-session -r`) so you can watch without taking control. citeturn25search2turn25search1
- `sx agent attach --steal <id>` detaches other clients (`tmux attach-session -d`). citeturn25search2turn25search1

### Inspect blocked sessions without attaching

Separate “peek” from “attach.”

**Codex (best-case):** if a session is Codex App Server–backed, show:

- `thread/status` and `activeFlags` (e.g., `waitingOnApproval`), and
- `thread.preview` and `thread.updatedAt`,
  using `thread/list`/`thread/read`. citeturn8view2turn8view3turn7view2

**Claude Code:** show:

- known session ID/name,
- last checkpoint age, and
- quick “resume/fork” hints, because checkpointing persists across resumed conversations. citeturn19view0turn16view0

**Generic/tmux sessions:** show a cheap preview:

- tail of the tmux pane capture (if you implement it), or
- tail of agent-native logs (preferred), or
- last N lines of terminal capture as a fallback (Sinnix already captures Kitty scrollback and writes `.ansi` + `.meta.json` sidecars). fileciteturn28file0L1-L1

### Switch between many sessions efficiently

Avoid “which tab is that?” by introducing a consistent selector:

- `sx agent pick` opens `fzf` with sessions; preview panel shows last transcript lines and metadata. Sinnix already uses fzf heavily and has preview/snippet conventions. fileciteturn24file0L1-L1
- Keys:
  - Enter = attach
  - Ctrl-O = observe (read-only attach)
  - Ctrl-K = terminate
  - Ctrl-A = archive
  - Ctrl-F = fork

### Review idle sessions and archive/terminate cleanly

Codex App Server provides explicit archive/unarchive semantics for thread logs. citeturn8view4turn13view5
Claude Code provides resumption and checkpointing across sessions, and sessions are cleaned up after a retention window (30 days configurable). citeturn19view0turn16view0

Sinnix’s layer should unify to:

- **idle**: no activity for N minutes/hours (configurable)
- **archived**: not running, but transcript preserved and searchable (Polylogue)
- **terminated**: process ended, transcript preserved, session record immutable (except tags/notes)

### Fork or branch a session

Use agent-native fork where it exists:

- Codex: `codex fork` (for interactive sessions) and App Server `thread/fork`. citeturn12view1turn8view1
- Claude Code: `--fork-session` when resuming. citeturn16view0turn19view0

Then have Sinnix map the new agent-native session/thread ID back into a new Sinnix session record.

### Notifications and at-a-glance status

Sinnix already runs a desktop notification system and uses systemd user services tied to `graphical-session.target`. fileciteturn27file0L1-L1 fileciteturn26file0L1-L1

Make blocked/approval-needed states visible without a terminal:

- On Codex App Server `thread/status/changed` to `waitingOnApproval`, raise a desktop notification. citeturn8view2turn8view6
- On “session idle for 2h with unmerged changes,” optionally notify.

## NixOS and service-management recommendations

### Service model: user services, persistent user manager, and linger

If you want agent sessions to survive logouts/reboots without depending on an interactive shell, use **systemd user services** and enable **linger** for your user.

`loginctl enable-linger` causes a user manager to be spawned at boot and kept after logouts, allowing user services to run even when not logged in. citeturn25search6turn25search5

This matters for:

- overnight Codex exec jobs,
- long compactions/ingestions (Polylogue already runs via a user service + timer), fileciteturn20file0L1-L1
- and “agent sessions as services.”

### Fit with existing Sinnix systemd patterns

Sinnix already has a strong pattern library:

- `mkGraphicalUserService` anchors services to `graphical-session.target` and sets consistent Unit/Service/Install semantics. fileciteturn26file0L1-L1
- `mkHardenedService` provides reusable “strict/moderate/minimal” hardening templates (ProtectSystem/Home/Proc, namespaces, syscall filtering). fileciteturn26file0L1-L1

Build the agent session manager module to reuse these primitives rather than inventing new patterns.

### Deployment and configuration shape

**Recommended NixOS/Home Manager module shape:**

- `sinnix.services.agentd.enable` (control plane, metadata store, optional background watchers)
- `sinnix.agent.sessionsRoot` (state directory; default under existing realm/captures pattern)
- `sinnix.agent.defaultMultiplexer = "tmux"` (or `"zellij"`)
- `sinnix.agent.agents.codex`, `.claude` defaults:
  - command path (already wrapped in `~/.local/bin/codex` and `~/.local/bin/claude`) fileciteturn24file0L1-L1
  - default model/profile
  - persistence directories and whether to opt into app-server integration

### Logs, retention, and discovery

Codex provides persisted rollout/thread logs and archive semantics through App Server and CLI resume/fork/ephemeral controls; use that for durable transcripts rather than relying on terminal scrollback. citeturn12view5turn8view4turn12view0

Claude Code provides resumable sessions, checkpoint persistence across sessions, and configurable cleanup windows; avoid duplicating this with a second transcript system when possible. citeturn19view0turn16view0

Then treat Polylogue as the unified index/search layer across these artifacts. fileciteturn35file0L1-L1

## Recommended design for Sinnix

This section is the decision-ready set (Research question I), integrating everything above.

### Best overall architecture

**A tmux-first “agent session manager” in Sinnix, augmented by agent-native persistence and Polylogue indexing.**

Concretely:

- **Session runtime**: each Sinnix agent session is a systemd user unit that ensures a tmux session exists.
  - systemd owns lifecycle: restart, resource controls, logging boundaries.
  - tmux owns attach/detach and multi-client viewports. citeturn25search2turn25search6
- **Session metadata**: Sinnix writes a single authoritative session record on creation capturing:
  - repo/worktree/cwd (and optionally branch),
  - agent type/provider + model,
  - tmux session name,
  - agent-native session/thread IDs when available (Codex/Claude),
  - timestamps and status fields.
- **Viewport surfaces**: Kitty remains the primary “attach target,” using existing remote-control infrastructure to open tabs/windows and run attach commands. fileciteturn23file0L1-L1 fileciteturn31file0L1-L1
- **Observability**:
  - Prefer agent-native logs (Codex thread JSONL / rollout files; Claude session JSONL; batch runner logs). citeturn8view4turn12view5turn23view0turn16view0
  - Use Sinnix terminal capture as a fallback and for non-agent shells. fileciteturn21file0L1-L1 fileciteturn28file0L1-L1
- **Transcript indexing/search**: use Polylogue as the “library + DB + TUI” for durable transcripts; ensure session artifacts land in places Polylogue can ingest (or extend Polylogue parsers for Sinnix-specific session manifests later). fileciteturn35file0L1-L1 fileciteturn36file0L1-L1

### Two to three viable alternatives

**Alternative A: Zellij-first session manager**
Use Zellij sessions instead of tmux, leaning on Zellij’s explicit multi-user model and built-in session manager UX. citeturn26search0turn26search1turn26search6
Pros: modern UX; native session manager; web client exists (optional). citeturn26search7
Cons: the web client conflicts with the “terminal-native first” preference unless strictly optional. citeturn26search7

**Alternative B: Codex App Server as the primary session substrate (Codex-only)**
Run Codex sessions via App Server and build a small Sinnix client that lists threads, shows blocked states, and attaches via streamed UI; use tmux only for Claude. citeturn14view0turn8view2turn8view6
Pros: best status model (waiting on approval, structured events) and strongest “inspect without attach.” citeturn8view2turn7view2
Cons: `codex app-server` is explicitly experimental/dev-debug and may change without notice; maintaining a client is a long-term commitment. citeturn13view6turn13view3

**Alternative C: “Kitty-only orchestration” (evolve existing skills + restore)**
Double down on Kitty remote-control orchestration and terminal capture, without introducing tmux/zellij as the stable session substrate. fileciteturn29file0L1-L1 fileciteturn19file0L1-L1
Pros: aligned with existing code; minimal new primitives.
Cons: session lifetimes remain tied to terminal-windows unless you build a new PTY daemon layer (high complexity), and multi-viewport semantics are inherently weaker.

### Why the preferred option wins

The tmux-first design best matches the decision lens:

- terminal-native, local operator UX (no browser required),
- strong attach/detach/multi-client story (including read-only observe), citeturn25search2turn25search1
- clean NixOS/systemd deployment (user services + linger; reuse existing Sinnix patterns), citeturn25search6turn25search5 fileciteturn26file0L1-L1
- and it composes with agent-native persistence rather than fighting it (Codex resume/fork/ephemeral; Claude resume/fork/checkpoints). citeturn12view0turn12view5turn16view0turn19view0

### What should explicitly not be built in this pass

- A bespoke PTY multiplexer / custom terminal emulator layer (too much correctness risk).
- A browser-first control plane (Zellij web client / App Server web UI) as _the_ primary interface; keep any web surface optional. citeturn26search7turn13view3
- A second transcript database rivaling Polylogue; prefer feeding Polylogue with better artifacts. fileciteturn35file0L1-L1

## Implementation plan, risks, and validation experiments

### Phased implementation plan

**Phase one: unify session identity and attach/detach UX (minimum lovable slice)**

Deliverables:

- `sx agent start|ls|attach|observe|stop|archive|fork` CLI.
- tmux-backed sessions launched via systemd user units (generated/transient units are acceptable initially; stabilize later).
- session metadata store (SQLite or JSONL) under a single root directory (aligned with existing Sinnix realm/capture layout). fileciteturn28file0L1-L1
- “observe” implemented via `tmux attach-session -r`. citeturn25search2turn25search1
- “steal control” implemented via `tmux attach-session -d`. citeturn25search2turn25search1
- Kitty-facing attach that opens a new tab and runs attach, using the same remote-control socket mechanism already in use by session restore and orchestration scripts. fileciteturn23file0L1-L1 fileciteturn31file0L1-L1 fileciteturn19file0L1-L1

**Phase two: legibility upgrades and transcript plumbing**

Deliverables:

- Status model in `sx agent ls`:
  - running/idle/dead/archived,
  - last activity,
  - repo/worktree grouping.
- “peek without attach” support:
  - Codex: if using App Server threads, call `thread/read` (no subscription) and show `preview` + status. citeturn7view2turn8view2
  - Claude: show `--resume` hint and “last checkpoint” age (derived from session files if you decide to parse them). citeturn16view0turn19view0
- Desktop notifications for “approval needed” and “job finished”:
  - Codex: `waitingOnApproval` flag from status events. citeturn8view2turn8view6
- Integrate Polylogue:
  - Ensure Codex/Claude artifacts are consistently discoverable by Polylogue’s ingest routines and scheduled runs (Sinnix already has a Polylogue timer/service). fileciteturn20file0L1-L1 fileciteturn35file0L1-L1

**Phase three: optional Codex App Server integration**

Deliverables:

- A `sx codexd` user service that runs `codex app-server` (stdio or ws transport) and a lightweight client command to:
  - list threads,
  - show blocked state (`thread/status/changed` / `waitingOnApproval`),
  - archive/unarchive threads,
  - and attach via a TUI client. citeturn13view3turn8view2turn8view4turn14view2

Treat this as optional because `codex app-server` is documented as experimental/dev-debug and may change without notice. citeturn13view6turn13view3

### Highest-risk UX decisions

- **What is “the” session list?** Mixing tmux sessions, Codex sessions, and Claude sessions can confuse users unless Sinnix owns a single canonical ledger and presents agent-native IDs only as metadata. (Inferred from the breadth of agent-native session mechanisms: Codex resume/fork vs App Server threads vs Claude resume/fork/checkpoints.) citeturn12view0turn7view2turn16view0turn19view0
- **Inspect-without-attach semantics for non-Codex sessions.** Codex has `thread/read` and status flags; tmux-only sessions need either heuristics (tail output) or instrumentation. citeturn7view2turn8view3turn25search2
- **Where transcripts live.** Claude has a history of non-XDG defaults and migrations; Sinnix should set `CLAUDE_CONFIG_DIR` explicitly (or continue its `~/.claude -> ~/.config/claude` pattern) to keep paths stable. fileciteturn24file0L1-L1 citeturn21view0turn24view0turn23view0

### Validation experiments (do these early)

- **Codex persistence reality check (on your workstation):**
  1. start an interactive Codex session, exit, then `codex resume --last`; verify what constitutes “most recent” and how it scopes to cwd. citeturn12view0turn12view1
  2. run `codex exec` and `codex exec resume --last`; verify artifact locations and how `--ephemeral` changes disk writes. citeturn12view0turn12view5
- **Claude persistence + path check:**
  1. set `CLAUDE_CONFIG_DIR` and verify where sessions/projects/logs land; confirm resumability with `claude --resume` and fork behavior with `--fork-session`. citeturn21view0turn16view0turn19view0
  2. confirm whether your install uses `~/.config/claude/projects` or `~/.claude/projects`, and align Sinnix persistence accordingly. citeturn23view0turn24view0
- **tmux multi-viewport correctness:**
  attach from two terminals; test read-only observer mode and “steal” attach; validate that your preferred copy/paste works under Kitty + tmux. citeturn25search2turn25search1
- **Zellij alternative spike (optional):**
  start one session, attach from two terminals, test the session manager’s “disconnect other clients” flow; assess resizing impact and whether it matches your multi-monitor setup. citeturn26search0turn26search6

### Appendix: sources with links and dates

Retrieved and inspected on **2026-03-19** unless otherwise indicated.

- Sinnix repo (selected files at commit `32d289c…`): Kitty terminal config, agent restore, terminal capture scripts, systemd helpers, Codex config and skill scripts. fileciteturn23file0L1-L1 fileciteturn19file0L1-L1 fileciteturn21file0L1-L1 fileciteturn22file0L1-L1 fileciteturn26file0L1-L1 fileciteturn29file0L1-L1
- Polylogue repo (selected files at commit `bd5c55b…`): Internals reference (SQLite/FTS/vector, parsers, MCP), Textual TUI browser widget. fileciteturn35file0L1-L1 fileciteturn36file0L1-L1
- entity["company","OpenAI","ai company"] Codex App Server documentation. citeturn14view0turn14view2turn8view4
- entity["company","OpenAI","ai company"] engineering blog: “Unlocking the Codex harness: how we built the App Server” (published 2026, crawled 2026-03). citeturn7view8turn7view9turn7view10
- Codex CLI command-line reference (resume/fork/app-server/ephemeral semantics). citeturn12view0turn12view1turn12view5turn13view6
- entity["company","Anthropic","ai company"] Claude Code CLI reference (resume/continue/fork-session/no-session-persistence). citeturn16view0
- entity["company","Anthropic","ai company"] Claude Code checkpointing reference (checkpoints persist across sessions; 30-day cleanup configurable). citeturn19view0
- Anthropic-maintained issue on XDG path behavior for Claude Code (opened 2025-05-31). citeturn24view0
- tmux man page excerpts (clients/sessions model; attach read-only; detach other clients). citeturn25search2turn25search1
- Zellij user guide and release notes (attach/list sessions; multi-user disconnect; web client). citeturn26search1turn26search0turn26search7turn26search6
- systemd `loginctl` man page excerpt for lingering (spawn user manager at boot; keep after logouts). citeturn25search6
