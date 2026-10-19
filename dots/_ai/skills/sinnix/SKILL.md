---
name: sinnix
description: Work on Sinnix NixOS configuration, modules, scripts, dotfiles, agentctl, the agent gateway, rebuilds, activation, or live workstation verification.
---

# Sinnix

The repository's root `AGENTS.md` owns the layout, module factories,
verification and activation rules; read it before editing. `docs/agentctl.md`
and `docs/agent-gateway.md` own those two contracts. Take operation names from
`agentctl project operations sinnix`, not from memory.

## Agent tooling locations

- `flake/data/agent-profiles.nix`: agent launcher profiles.
- `flake/data/mcp-registry.nix`: MCP profiles.
- `modules/features/dev/agents/`: renders the client links to `dots/_ai/`.
- `~/.local/bin/claude` is the Home Manager launcher wrapper; the upstream CLI
  it runs is installed under `~/.local/state/claude-code/npm/`.
- Codex's private configuration is an app-owned overlay on the generated one;
  inspect the installed target to verify delivery.
