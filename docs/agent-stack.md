# Agent stack organization

This machine should not become an agent-package zoo. The scalable split is:

- `llm-agents.nix`: upstream package supply for fast-moving agent CLIs and adjacent tools.
- Sinnix: local projection layer — wrappers, MCP registry, cgroups, persistence, desktop/F-key surfaces, and config rendering.
- Polylogue/Lynchpin/Sinex: evidence, archive, event substrate, and derived analysis.
- Hermes/Claude/Codex/Gemini/Forge/OpenCode: execution surfaces, not sources of truth.

Rule of thumb:

- If it packages or updates an agent CLI, prefer `llm-agents.nix`.
- If it grants authority or shapes context, keep it in Sinnix.
- If it describes past work or self-state, store/query it through Polylogue/Lynchpin/Sinex/knowledgebase.
- If it only adds vocabulary around agents without measurable transfer, reject it.

## Current grounding

Raw-log themes that matter here:

- 2026-04-23 to 2026-05-12 repeatedly asks for better coding-agent affordances, OS/browser/desktop access, private headless browsers, use of Polylogue to mine past sessions, recursive orchestration, groupchat-like agent comms, bidirectional audio, and concrete prompts that move real projects.
- The recurring failure mode is not lack of ideas; it is unprioritized meta-infrastructure becoming another jurisdiction.
- The useful direction is a control plane that reduces hand-shuffling of sessions and preserves evidence, not another grand ontology.

## Adopt now

These are already available from `llm-agents.nix` and should be installed/exposed by Sinnix rather than locally packaged:

- `herdr`: terminal-native agent runtime/control layer. Strong fit for persistent multi-agent panes plus runtime API.
- `codex-acp`: NixOS-compatible ACP adapter for Codex, especially useful for Zed/ACP clients.
- `claude-agent-acp`: ACP adapter for Claude Agent SDK.
- `beads-rust` + `beads-viewer`: local-first issue graph and dependency/prioritization viewer.
- `agent-browser`: ready headless browser automation surface.
- `agent-deck` / `agentsview`: evaluate as lightweight dashboards/viewers before building local UI.
- `opencode`: additional terminal agent surface, useful as a cross-agent comparison target.
- `skills`: upstream skill tooling; keep Sinnix/Hermes skills authoritative locally.

Sinnix now installs these as packages. That is deliberately lower-risk than wiring services or changing session ownership.

## Evaluate next, in order

1. Herdr

Question: can Herdr replace ad-hoc tmux/scratchpad juggling for multi-agent work?

Evaluation:

```bash
herdr --help
herdr workspace create --cwd /realm/project/sinnix --label sinnix-agents
herdr tab create --label eval
herdr pane run 1-1 "codex --help"
herdr pane read 1-1 --source recent-unwrapped
```

Adopt if agents can create/read/wait on panes reliably and this lowers manual session management. Do not adopt if it becomes a second terminal ecosystem to maintain.

2. ACP

Question: does ACP give editor/client interoperability without replacing current CLI-first workflow?

Evaluation:

```bash
codex-acp --help
claude-agent-acp --help
```

Adopt for Zed/editor integration only. Do not redesign the whole agent topology around ACP; ACP is editor/client protocol, not the substrate of record.

3. Beads


Evaluation:

```bash
br --help
bv --help
```

Adopt per-repo only where dependency graph/critical path beats a plain scratch file. Avoid global life/task management migration.

4. Browser/desktop control

Existing registry already exposes Playwright headless, Playwright headed, and Chrome DevTools MCPs to agents. Current desktop control exists as Hyprland/wtype/grim skill instructions, not an MCP server.

Evaluate ready tools in this order:

- `agent-browser` from `llm-agents.nix` for private browser automation.
- existing `mcp-playwright` for headless browser work.
- existing `mcp-playwright-headed` / `mcp-chrome-devtools` for real browser/session interaction.
- only then consider writing a local desktop-control MCP around `hyprctl`, `wtype`, `grim`, `wl-copy`, `wl-paste`.

The desktop-control MCP should be tiny and typed if built: list windows, active window, focus, workspace, type text, keypress, screenshot. Do not expose broad shell execution through it.

## Evaluate later / be suspicious

- AgentSys: attractive because it organizes lifecycle plugins across Claude/Codex/OpenCode, but likely overlaps heavily with existing Sinnix skills, Hermes modes, and project conventions. Mine it for commands/evals, do not wholesale install first.
- Agent Flywheel: useful concepts/tools, especially agent mail, CASS-like session search, beads, bug scanner. But it is an ecosystem pitch; import individual tools only when they beat existing Polylogue/Sinnix equivalents.
- Ruflo: high surface area, swarm/memory/federation claims, likely too much jurisdiction. Treat as research material, not a near-term substrate.

## Keep local

- `modules/lib/mcp-registry.nix`: canonical per-client MCP projection.
- `modules/services/hermes.nix`: Hermes config and mode wrappers.
- `modules/features/dev/mcp-servers.nix`: registry renderers for Codex/Forge/Gemini/Claude/Hermes MCP client configs.
- `modules/features/dev/agent-tools.nix`: agent CLI wrappers, profile launchers, and installed upstream package set.
- `dots/codex/config.toml`: Codex static defaults only; MCP entries are generated from the registry at activation/build time.
- `dots/_ai/skills/`: shared project skills.
- `scripts/render-agents`, `normalize-agent-projects`, `verify-agent-topology`: local projection/verification.

## Interactive profiles

Use explicit launchers instead of mutating shared global defaults mid-session:

- Claude Code:
  - `claude`: default Claude Code with managed MCP config and `/realm/project` access.
  - `claude-opus`: Opus, high effort, same managed MCP surface.
  - `claude-sonnet`: Sonnet, medium effort, same managed MCP surface.
  - `claude-lite`: bare/no-MCP startup for debugging config or isolating provider/tool issues.
  - `deepseek`: Claude Code protocol against DeepSeek v4-pro 1m with max effort.
- Codex:
  - `codex`: default gpt-5.5 medium.
  - `codex-fast`: gpt-5.5 low effort.
  - `codex-deep`: gpt-5.5 high effort.
  - `codex-max`: gpt-5.5 xhigh effort.
  - `codex-spark`: gpt-5.3-codex-spark medium.
  - `codex-spark-xhigh`: gpt-5.3-codex-spark xhigh.

These wrappers are projections, not new authorities: MCP capability is still registry-generated; instructions still render from Claude/AGENTS sources; persistence remains under each tool's native home.

## Delete/refactor targets

Only delete after an audit proves duplication:

- local package/version overrides when `llm-agents.nix` has caught up;
- any wrapper that only invokes upstream binary with no Sinnix projection;
- any agent skill that duplicates an upstream command without local policy/context;
- any UI/dashboard experiment superseded by Herdr/agent-deck/agentsview.

Current obvious cleanup candidate: the local `claude-code` override in `agent-tools.nix` exists only because upstream lagged. Re-check on every `llm-agents.nix` update and delete when upstream version is new enough.

## Daemonic orchestration direction

See `docs/agent-daemon-orchestration.md` for the researched runtime/control-plane contract: Herdr as the likely runtime plane, MCP Agent Mail + Beads as coordination plane, ACP as editor projection only, and terminals treated as attachable views rather than process owners.

## Priority rule

Choose the next agent-stack task by asking:

1. Does it reduce manual session/context juggling this week?
2. Does it improve evidence capture or replay through Polylogue/Lynchpin/Sinex?
3. Does it use an upstream maintained package instead of local packaging?
4. Does it have a 10-minute eval with observable pass/fail?

If not, defer.
