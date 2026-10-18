---
name: sinnix
description: Work on Sinnix NixOS configuration, modules, scripts, dotfiles, agentctl, the agent gateway, rebuilds, activation, or live workstation verification.
---

# Sinnix

Sinnix declares the workstation, user environment, fixed services, and
`agentctl`. Read the root `AGENTS.md` before editing; use `docs/agentctl.md`
and `docs/agent-gateway.md` for those contracts.

## Map

- `modules/`: infrastructure, default-on features, default-off services,
  profiles, and module factories.
- `flake/`: host construction, data registries, script discovery, packages,
  and checks.
- `pkgs/`: packages, including agentctl and the agent gateway; a directory
  holding only `tests/` is the suite for the script of the same name.
- `scripts/`: auto-discovered small tools with required frontmatter.
- `dots/`: managed configuration sources, including live links for shared
  skills and agent instructions.

Use the existing factories and registries. Features use `mkFeatureModule`,
services use `mkServiceModule`, scheduled jobs use `mkScheduledJob`, and capture
lanes use `mkCaptureLane`. A bypass needs a structural reason.

## Agent surfaces

`flake/data/agent-lanes.nix` defines CLI lanes;
`flake/data/mcp-registry.nix` defines MCP profiles; `dots/_ai/skills/` is the
source for shared skills and `modules/features/dev/agents/` renders client
links. `~/.local/bin/claude` is the Home Manager launcher wrapper; the
upstream CLI it runs is installed under `~/.local/state/claude-code/npm/`.

agentctl is in `pkgs/agentctl/`; the gateway is in
`pkgs/sinnix-agent-gateway/`. Inspect `.agentctl/project.toml` and
`agentctl project operations sinnix` rather than restating operation names.

## Verification and activation

Run the narrowest check that proves the change (`AGENTS.md`, "Workflow and
verification"): an evaluated option or unit, one package's tests, one named
check. The full declared operations are for integration milestones and
concrete risks, not every commit:

```text
agentctl job start sinnix lint
agentctl job start sinnix check
```

Rebuild only through the devshell `switch`, `boot`, `test-system`, or
`test-vm` commands. From
outside the shell use `nix develop --command switch`. Never invoke bare `nh os
switch`, and do not preflight a switch with duplicate evaluation. After
activation, compare `nixos-version --configuration-revision` with the intended
commit and inspect the direct live service or file fact.

Live dots links update on the next read, though a running client can retain
loaded instructions. Generated profiles and link layouts need activation;
Codex's private configuration remains an app-owned overlay. Inspect installed
targets to verify delivery. Structural agent changes regenerate
`docs/agent-environment.md`; gateway references change through their renderer.
