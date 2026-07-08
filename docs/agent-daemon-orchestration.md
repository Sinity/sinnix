# Daemonic multi-agent orchestration

Scope: powerful multi-agent flows where agent work is never an opaque foreground terminal. Every live agent or helper must have an explicit runtime identity, lifecycle owner, programmatic control surface, and evidence trail.

Non-goals:

- No new grand self-model vocabulary.
- No replacing Polylogue/Lynchpin/Sinex as evidence substrate.
- No all-in ecosystem migration.
- No Docker/security-theater default. Isolation is for dependency/worktree conflicts, not because local agents are untrusted.

## Verdict

The elegant shape is not one swarm framework. It is five deliberately separate planes:

1. Runtime plane: persistent processes, panes, sessions, wait/read/send/kill.
2. Coordination plane: tasks, claims, file reservations, threaded handoffs.
3. Protocol plane: MCP for tools/resources, ACP for editor clients, CLI/stdin for batch agents.
4. Evidence plane: terminal capture, Polylogue, Lynchpin, Git, future Sinex events.
5. Projection plane: TUI/web/F-key/editor surfaces over the same live runtime.

Near-term default:

- Herdr for terminal-native persistent agent runtime and socket/CLI orchestration.
- MCP Agent Mail + Beads (`br`/`bv`) for multi-agent coordination when several agents touch one repo.
- Existing Hermes/Codex/Claude/Gemini wrappers remain the agent binaries; Sinnix wraps and scopes them.
- ACP adapters stay editor interop, not the core substrate.
- Agent Deck / AgentsView / Workmux are mined or optionally used as projections/worktree helpers, not appointed as source of truth.

## Research notes

### Herdr

Fit: strongest candidate for the runtime plane.

Relevant properties from upstream docs:

- Persistent terminal sessions survive client detach and terminal closure.
- Real terminal panes rather than browser/GUI pseudo-terminals.
- Workspaces/tabs/panes around repos or folders.
- Agent status awareness: blocked, working, done, idle.
- Local Unix socket / CLI API lets agents create workspaces, split panes, spawn helpers, read output, and wait for state changes.
- Remote SSH attach exists.

Why it matters here:

- It directly answers the foreground-terminal problem: a terminal is just one view onto a persistent runtime server.
- It gives agents a programmable control surface without forcing everything through fragile `wtype`/window focus.
- It preserves terminal-native workflows and does not invent a web app as the primary environment.

Adopt if this 10-minute eval passes after deployment:

```bash
herdr --help
herdr workspace create --cwd /realm/project/sinnix --label sinnix-eval
herdr tab create --label smoke
herdr pane split 1-1 --direction right
herdr pane run 1-2 "printf HERDR_OK; sleep 2"
herdr pane read 1-2 --source recent-unwrapped
herdr wait agent-status 1-2 --status done || true
```

Reject or defer if:

- The CLI cannot reliably create/read/wait on panes from outside the TUI.
- It requires manual TUI focus for routine orchestration.
- Its state model conflicts with terminal-capture or loses logs.

### MCP Agent Mail

Fit: strongest candidate for the coordination plane.

Relevant properties from upstream docs:

- MCP server exposing project-scoped identities, threaded inboxes, searchable threads, and advisory file reservations.
- SQLite/FTS plus Git-backed audit trail.
- File reservation TTLs and optional pre-commit guard.
- Human overseer UI and message audit history.
- Integrates with Beads task graph: agents claim ready beads, reserve files, work, report, close.

Why it matters here:

- Multi-agent collisions are not mainly a pane problem. They are ownership/file/task/handoff problems.
- Advisory leases are better than hard locks: visible conflict without deadlocks.
- Git-backed mail provides durable, inspectable coordination evidence without polluting raw-log.

Adopt if:

- It can run as a local systemd user service with storage under `~/.local/state/mcp-agent-mail` or `/realm/data/agent-mail`.
- MCP clients can register identities and reserve files from Claude/Codex/Hermes without awkward per-client hacks.
- Its Git trail can be indexed later by Polylogue/Lynchpin/Sinex.

Reject or constrain if:

- It turns into a parallel task tracker replacing GitHub/beads/project scratch by default.
- It requires agents to broadcast every thought instead of only claims, conflicts, and handoffs.

### Beads (`br`) and Beads Viewer (`bv`)

Fit: per-repo task/dependency graph for multi-agent execution.

Useful loop:

1. Human/Hermes writes plan.
2. Convert plan into detailed beads with dependencies and acceptance criteria.
3. Agents use `bv` to pick ready, high-leverage work.
4. Agent claims bead in Agent Mail, reserves file paths, implements, tests, closes bead.

Adopt per repo only when parallel execution is real. Do not create a global life/task migration.

### Workmux

Fit: worktree isolation helper, not primary runtime.

Relevant properties:

- Creates git worktree plus tmux window/session.
- Can launch agents with prompts.
- Handles `.env`/cache copy/symlink patterns.
- Dashboard/sidebar tracks agent status.

Why it is not the default core here:

- It is tmux/worktree-centered, while Sinnix already has wrappers, terminal capture, and Herdr is a better runtime candidate.
- Worktrees are useful when agents need independent dependency/build states, but not every parallel task wants merge debt.

Adopt selectively for repos where parallel branches are normal. Prefer Agent Mail advisory reservations for same-tree coordination.

### Agent Deck

Fit: useful source of ideas and possible dashboard/conductor projection.

Relevant properties:

- Tmux-backed TUI session manager for Claude/Gemini/OpenCode/Codex.
- Conductors/watchers, Telegram/Slack escalation, MCP manager, worktree management, cost tracking, web mode.

Risk:

- It overlaps with Sinnix wrappers, Hermes modes, MCP registry, scratchpads, and potential Agent Mail/Herdr control plane.
- Its conductor/watchers can become another opaque jurisdiction.

Use as projection only if Herdr lacks a needed dashboard/escalation feature. Do not let Agent Deck become source of truth.

### AgentsView

Fit: session intelligence viewer, possibly redundant with Polylogue.

Relevant properties from search results:

- Local-first app for browsing/searching/analyzing past AI coding sessions across Claude Code, Codex, and other agents.

Risk:

- Polylogue already owns AI conversation archive locally.
- AgentsView is valuable only if it gives better UI over existing logs or supports agents Polylogue does not cover.

Adopt as viewer/export source only. Do not fork archival truth into it.

### ACP (`codex-acp`, `claude-agent-acp`)

Fit: protocol plane for editor/client interoperability.

Relevant properties from ACP docs:

- Standardizes editor/IDE-to-coding-agent communication.
- Local mode is JSON-RPC over stdio from editor subprocess.
- Remote support exists as direction but is still evolving.
- ACP reuses MCP-ish representations where possible but is focused on coding UX/diffs.

Boundary:

- ACP is like LSP for editor-agent interop.
- It is not a daemon supervisor, not evidence storage, not multi-agent coordination.

Adopt for Zed/editor projection after the runtime plane works.

### AgentSys

Fit: pattern mine, not substrate.

Useful ideas:

- One agent, one job.
- Deterministic tools first; LLMs judge where needed.
- Pipeline gates with persistent JSON state.
- Commands for next-task, prepare-delivery, ship, repo-intel, drift-detect, deslop, debate.

Risk:

- 24 plugins / 50 agents / 45 skills is exactly the kind of surface that becomes jurisdiction here.
- Sinnix/Hermes already has skills, wrappers, MCP registry, project conventions, and Polylogue/Lynchpin evidence.

Mine specific commands/evals. Do not install as a parallel operating constitution.

## Required local contract

Every agent session, daemon, or helper must satisfy this contract:

```text
id: stable runtime id
kind: agent | helper | watcher | conductor | ui
owner: user | hermes | systemd | repo
project_root: absolute path or null
command: exact argv
cwd: exact cwd
state: starting | running | blocked | waiting | done | failed | stopped
control: list/read/send/wait/interrupt/stop URL or CLI tuple
evidence: terminal_capture path, Polylogue id, Agent Mail thread, Git branch/sha, Sinex event ids when available
resources: cgroup/slice, pid, started_at, last_seen
```

If a process cannot expose at least `list`, `read`, `send`, and `stop`, it is not a managed agent runtime. It can still be a one-shot command, but not part of the multi-agent fabric.

## Proposed Sinnix architecture

### Runtime plane

Primary: Herdr.

Sinnix should provide a thin wrapper, not a fork:

```text
sinnix-agent-runtime list
sinnix-agent-runtime spawn --project /realm/project/sinnix --kind codex --label storage-audit --prompt-file /tmp/prompt.md
sinnix-agent-runtime read <id> [--recent]
sinnix-agent-runtime send <id> --text ...
sinnix-agent-runtime wait <id> --state done --timeout 30m
sinnix-agent-runtime stop <id>
```

Implementation target:

- Underneath, call Herdr CLI/socket for persistent terminal panes.
- Register runtime metadata to a small JSONL state file or, later, Sinex event stream.
- Keep terminal capture enabled so Polylogue/Lynchpin can ingest evidence.
- Run the Herdr server under a user systemd service if Herdr supports a clean server mode; otherwise rely on Herdr's own background session server and wrap lifecycle commands.

Do not start with a custom daemon unless Herdr fails the eval.

### Coordination plane

Primary: MCP Agent Mail + optional Beads.

Systemd user service target:

```text
mcp-agent-mail.service
  ExecStart = mcp-agent-mail server --host 127.0.0.1 --port 8765
  StateDirectory or explicit storage root under persisted home/data
  Restart = on-failure
```

Sinnix MCP registry projection:

- expose Agent Mail to Hermes/Claude/Codex when enabled;
- include only identity, messaging, reservation, search, and macro start-session tools initially;
- exclude high-surface admin/export/web extras until earned.

Coordination flow:

1. Orchestrator opens/loads a bead or explicit task.
2. Agent runtime spawns an agent pane/session.
3. Agent registers with Agent Mail using project path, program, model, task description.
4. Agent claims task thread and reserves file globs before editing.
5. Agent reports blockers/handoffs in the thread.
6. Runtime waits for done/blocked; Hermes/user views via Herdr/F5/web projection.
7. On finish, agent releases reservations, updates bead, leaves evidence pointers.

### Protocol plane

MCP:

- Tools/resources into agents.
- Agent Mail as coordination MCP.
- Existing Chrome/GitHub/Lynchpin/Polylogue MCPs stay registry-projected per client.
- Polylogue and Lynchpin are evidence-plane MCPs, not live-control MCPs:
  Polylogue answers agent transcript/session questions, while Lynchpin answers
  cross-source timeline/correlation questions over materialized chats, git,
  ActivityWatch, shell, health, and machine telemetry.
- Sinnix observability remains the raw runtime plane:
  `/etc/sinnix/runtime-inventory.json`, `sinnix-observe`, and capture roots under
  `/realm/data/captures/**`.

ACP:

- Editor-to-agent projection only.
- Use `codex-acp` and `claude-agent-acp` when Zed/editor integration is desired.
- Do not use ACP as the internal orchestration bus.

CLI/stdin:

- Batch one-shot agents still use `codex exec`, `hermes -z`, `claude -p` where available.
- Long-running interactive agents use Herdr runtime.

Sinex/event stream, later:

- Record runtime lifecycle, state changes, messages/reservations, and evidence pointers.
- This is substrate-of-record direction, not required for the first eval.

### Evidence plane

Existing evidence sources stay authoritative:

- terminal-capture for shell sessions;
- Polylogue for AI conversations;
- Lynchpin for cross-source analysis;
- Git for code facts;
- knowledgebase/raw-log only as user-authored or curated evidence, not agent status dumps.

New coordination evidence should become indexable:

- Agent Mail Git trail;
- Beads task graph;
- Herdr runtime metadata/logs;
- future Sinex events.

No process status goes to raw-log.

### Projection plane

Use multiple views over the same runtime:

- F5/Hermes: user-facing Conductor and cognitive mirror surface.
- Herdr TUI: live terminal/pane control.
- Agent Mail web/TUI: coordination/inbox/reservations.
- Beads Viewer: task/dependency graph and ready-work routing.
- ACP editor clients: editor-native agent interaction.
- Agent Deck/AgentsView: optional viewers only if they read from or complement the above without becoming source of truth.

## The no-foreground rule

A foreground terminal is acceptable only as a client view. It is not the owner.

Bad:

```text
Open kitty, run claude, hope it keeps going, maybe screenshot later.
```

Good:

```text
runtime spawn -> returns id
coordination register -> returns agent identity/thread
runtime read/wait/send by id
terminal capture/polylogue record evidence
UI attaches/detaches at will
```

This reframes terminals as projections. The session lives in a runtime plane with a queryable control API.

## Phased adoption

### Phase 0: Ground truth and deployment check

Current observed state while writing this doc:

- Sinnix already has docs/agent-stack.md with Herdr/ACP/Beads/Agent Deck priority map.
- `modules/features/dev/agents/clis.nix` (formerly `agent-tools.nix`) declares packages from `llm-agents.nix`.
- The live PATH in this session did not expose those binaries yet, so package installation is not deployed into the current shell/profile.

Action:

- Deploy or enter the right profile/devshell before runtime eval.
- Do not assume commands are live just because Nix config declares them.

### Phase 1: Herdr runtime eval

Goal: prove `list/spawn/read/send/wait/stop` without custom daemon work.

Acceptance criteria:

- Spawn a Codex/Hermes/Claude session in a project workspace.
- Read recent output programmatically.
- Send text without focusing a desktop window.
- Wait for done/blocked state.
- Detach/reattach from another terminal.
- Terminal capture still sees the session or Herdr logs provide equivalent evidence.

Artifact:

- `/realm/project/sinnix/.agent/scratch/herdr-runtime-eval-YYYY-MM-DD.md`

### Phase 2: Agent Mail daemon eval

Goal: prove identity/message/reservation flow with two local agents.

Acceptance criteria:

- Local service starts at boot/user login.
- Hermes and one coding agent can both use MCP Agent Mail tools.
- Agent A reserves a file glob; Agent B sees conflict.
- Thread history is searchable and persists after restart.
- Git trail path is known and not under raw-log.

### Phase 3: Unified wrapper

Only after Herdr + Agent Mail pass:

- Add `sinnix-agent-runtime` wrapper or package script.
- Add `sinnix-agent-session` high-level CLI if needed.
- Do not duplicate Herdr commands unless the wrapper adds local policy/evidence wiring.

Minimum commands:

```text
spawn/list/read/send/wait/stop/status
```

Nice-to-have commands:

```text
claim/reserve/release/handoff/escalate
```

### Phase 4: Projection wiring

- F5 can show/launch Hermes Conductor, but not own all sessions.
- Optional Herdr scratchpad keybind.
- Optional local dashboard only if backed by runtime/coordination APIs.
- ACP enabled in editor after core runtime works.

### Phase 5: Sinex integration

Emit append-only events:

```text
agent.session.started
agent.session.state_changed
agent.message.sent
agent.file.reserved
agent.file.released
agent.session.finished
agent.evidence.linked
```

Then Lynchpin can derive cross-agent bottlenecks, collision rates, task cycle time, and state transitions.

## Anti-patterns to reject

- A foreground kitty/tmux pane as the only state handle.
- A web dashboard that can display sessions but not control/read/wait through stable IDs.
- A plugin ecosystem that duplicates Sinnix/Hermes skills and MCP registry.
- A task tracker migration justified by vibes instead of one repo needing dependency graph execution.
- Broadcast chat rooms for agents. Use targeted threads tied to tasks/files.
- Hard file locks as default. Use advisory TTL reservations plus pre-commit guard if needed.
- Putting agent status into raw-log.
- Building a custom daemon before Herdr and Agent Mail have failed concrete evals.

## Design pressure: same-tree reservations vs worktrees

Use same-tree + Agent Mail reservations when:

- tasks touch mostly disjoint files;
- merge debt would exceed collision risk;
- fast shared test feedback matters;
- agents are coordinated by explicit claims and file globs.

Use worktrees when:

- tasks require conflicting dependency/build states;
- multiple branches/PRs are expected;
- each agent needs independent long-running dev servers;
- review wants isolated diffs.

The likely steady state is both:

- Herdr for runtime sessions.
- Agent Mail for coordination in either same-tree or worktree mode.
- Workmux/Agent Deck only when a repo specifically benefits from automated worktree/session setup.

## Minimal next implementation move

Do not add a giant module yet.

Next executable move:

1. Deploy or enter environment where Herdr/Agent Mail/Beads binaries are live.
2. Run Herdr eval and record pass/fail.
3. If pass, add one tiny Sinnix wrapper script exposing `list/read/send/wait/spawn/stop` over Herdr.
4. Add one user service for Agent Mail only after MCP tool smoke-test succeeds manually.

If this does not reduce manual session juggling within one week, prune it.
