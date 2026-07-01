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

## Upstream Candidates

These are available from `llm-agents.nix` and should be installed/exposed by
Sinnix only when a Sinnix module gives them a clear role, persistence, and agent
vocabulary:

- `herdr`: terminal-native agent runtime/control layer. Strong fit for persistent multi-agent panes plus runtime API.
- `codex-acp`: NixOS-compatible ACP adapter for Codex, especially useful for Zed/ACP clients.
- `claude-agent-acp`: ACP adapter for Claude Agent SDK.
- `beads-rust` + `beads-viewer`: local-first issue graph and dependency/prioritization viewer.
- `agent-deck` / `agentsview`: evaluate as lightweight dashboards/viewers before building local UI.
- `opencode`: additional terminal agent surface, useful as a cross-agent comparison target.
- `skills`: upstream skill tooling; keep Sinnix/Hermes skills authoritative locally.

The default browser automation surface is `sinnix-chrome-control`, not an
always-on Chrome DevTools MCP. The private browser profile is seeded from the
live Chrome profile before launch, so agents can use authenticated browser state
without opening tabs or navigating in the visible user browser. The MCP trio
remains available through the explicit browser agent profile when the shell CDP
helper is too small.

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

The registry keeps Chrome DevTools MCPs in the explicit browser tier. Current
desktop/browser control exists as stable `sinnix-*` helper commands plus skill
instructions, not a typed desktop MCP server.

Browser-control lanes:

- `sinnix-chrome-control --target private` / `--target private-visible` for
  agent-owned private browser work backed by copied live profile state.
- `sinnix-chrome-control --target live` for real browser/session interaction.
- `claude-browser` / `codex-browser` for the Chrome DevTools MCP superset.
- A future local desktop-control MCP should wrap `hyprctl`, `wtype`, `grim`,
  `wl-copy`, and `wl-paste` when the shell helpers stop being enough.

The desktop-control MCP should be tiny and typed if built: list windows, active window, focus, workspace, type text, keypress, screenshot. Do not expose broad shell execution through it.

Control and evidence stay separate. DevTools/Hyprland/Kitty helpers are for live
action and perception; Polylogue is the transcript/session archive, Lynchpin is
cross-source interpretation over chats/git/ActivityWatch/shell/health/telemetry,
and Sinnix observability is raw runtime truth via `/etc/sinnix/runtime-inventory.json`,
`sinnix-observe`, and `/realm/data/captures/**`. `sinnix-agent-status`
is the compact bridge: it probes live control surfaces plus the evidence
services and capture roots an agent should consult before reconstructing events
from memory.

## Evaluate later / be suspicious

- AgentSys: attractive because it organizes lifecycle plugins across Claude/Codex/OpenCode, but likely overlaps heavily with existing Sinnix skills, Hermes modes, and project conventions. Mine it for commands/evals, do not wholesale install first.
- Agent Flywheel: useful concepts/tools, especially agent mail, CASS-like session search, beads, bug scanner. But it is an ecosystem pitch; import individual tools only when they beat existing Polylogue/Sinnix equivalents.
- Ruflo: high surface area, swarm/memory/federation claims, likely too much jurisdiction. Treat as research material, not a near-term substrate.

## Keep local

- `flake/data/mcp-registry.nix`: canonical per-client/profile MCP projection.
- `modules/services/hermes.nix`: Hermes config and mode wrappers.
- `modules/features/dev/mcp-servers.nix`: registry renderers for Codex/Forge/Gemini/Claude/Hermes MCP client configs.
- `modules/features/dev/agent-tools.nix`: agent CLI wrappers, profile launchers, and installed upstream package set.
- `dots/codex/config.toml`: Codex static defaults only; full/lean/browser MCP
  entries are generated from the registry at activation/build time.
- `dots/_ai/skills/`: shared project skills; Home Manager exposes only the
  curated default set to reduce cognitive overhead.
- `scripts/render-agents`, `normalize-agent-projects`, `verify-agent-topology`: local projection/verification.

## Interactive profiles

Use explicit launchers instead of mutating shared global defaults mid-session:

- Claude Code:
  - `claude`: full non-browser profile with GitHub, Context7, Polylogue, Lynchpin, Serena, and Codebase Memory. This is a shell alias to the `claude-full` wrapper — the bare `~/.local/bin/claude` path is deliberately left unmanaged because Claude Code's native local-installer claims and clobbers it on auto-update.
  - `claude-lean`: GitHub, Context7, and Polylogue only.
  - `claude-browser`: full profile plus Chrome DevTools MCPs.
  - `claude-deepseek`: full profile, but the model runs on DeepSeek via its native Anthropic-compatible endpoint (`api.deepseek.com/anthropic`, key from agenix `deepseek-api-key`).
  - `claude-local`: full profile, model served by the local Ollama hub through the LiteLLM gateway (`127.0.0.1:4000`) that translates Anthropic↔OpenAI.
- Codex:
  - `codex`: full non-browser profile with GitHub, Context7, Polylogue, Lynchpin, Serena, and Codebase Memory.
  - `codex-lean`: GitHub, Context7, and Polylogue only.
  - `codex-browser`: full profile plus Chrome DevTools MCPs.
  - `codex-deepseek`: full MCP profile layered with the DeepSeek OpenAI endpoint (`api.deepseek.com/v1`).
  - `codex-local`: full MCP profile layered with the local model via the LiteLLM OpenAI endpoint (`127.0.0.1:4000/v1`).

These wrappers are projections, not new authorities: MCP capability is still registry-generated; instructions still render from Claude/AGENTS sources; persistence remains under each tool's native home. The DeepSeek/local variants keep the full (default) MCP table — they swap only the inference backend. Local model names are defined once, in `modules/services/litellm.nix` (`model_list`); keep the wrappers' `ANTHROPIC_MODEL` / Codex `model` in sync with an entry there.

## Delete/refactor targets

Only delete after an audit proves duplication:

- local package/version overrides when `llm-agents.nix` has caught up;
- any wrapper that only invokes upstream binary with no Sinnix projection;
- any agent skill that duplicates an upstream command without local policy/context;
- any UI/dashboard experiment superseded by Herdr/agent-deck/agentsview.

The local `claude-code` override in `agent-tools.nix` / `languages.nix` was removed once upstream `llm-agents.nix` caught up to and surpassed the pinned version. If upstream lags again, reintroduce the same `overrideAttrs` pattern (fresh `fetchurl` from `storage.googleapis.com/claude-code-dist-…/claude-code-releases/<version>/linux-x64/claude`) and delete it once upstream catches up.

## Daemonic orchestration direction

See `docs/agent-daemon-orchestration.md` for the researched runtime/control-plane contract: Herdr as the likely runtime plane, MCP Agent Mail + Beads as coordination plane, ACP as editor projection only, and terminals treated as attachable views rather than process owners.

## Priority rule

Choose the next agent-stack task by asking:

1. Does it reduce manual session/context juggling this week?
2. Does it improve evidence capture or replay through Polylogue/Lynchpin/Sinex?
3. Does it use an upstream maintained package instead of local packaging?
4. Does it have a 10-minute eval with observable pass/fail?

If not, defer.
