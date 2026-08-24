---
name: sinnix
description: Work on Sinnix NixOS configuration, modules, scripts, dotfiles, AgentCTL, Sinnixd, the agent gateway, rebuilds, activation, or live workstation verification.
---

# Sinnix

Sinnix declares the workstation, user environment, fixed services, and the
common local AgentCTL runtime. Read the root `CLAUDE.md` before editing; use
`docs/sinnixd.md` and `docs/agent-gateway.md` for those contracts.

## Map

- `modules/`: infrastructure, default-on features, default-off services,
  profiles, and module factories.
- `flake/`: host construction, data registries, script discovery, packages,
  and checks.
- `pkgs/`: real packages, including Sinnixd and the agent gateway.
- `scripts/`: auto-discovered small tools with required frontmatter.
- `dots/`: live Home Manager out-of-store links, including shared skills and
  agent instructions.

Use the existing factories and registries. Features use `mkFeatureModule`,
services use `mkServiceModule`, scheduled jobs use `mkScheduledJob`, and capture
lanes use `mkCaptureLane`. A bypass needs a structural reason.

## Agent surfaces

`flake/data/agent-lanes.nix` defines CLI lanes;
`flake/data/mcp-registry.nix` defines MCP profiles;
`flake/data/shared-agent-skills.nix` defines the shared skill roster.
`modules/features/dev/agents/` renders them. The bare `claude` wrapper is lean;
the upstream installer owns `~/.local/bin/claude`.

Sinnixd and AgentCTL are in `pkgs/sinnixd/`; the gateway is in
`pkgs/sinnix-agent-gateway/`. Inspect `.agentctl/project.toml` and
`agentctl project operations sinnix` rather than restating operation names.

## Verification and activation

Use the declared operations for checks:

```text
agentctl job start sinnix lint
agentctl job start sinnix check
```

Rebuild only through the devshell `test-vm`, `switch`, or `boot` commands. From
outside the shell use `nix develop --command switch`. Never invoke bare `nh os
switch`, and do not preflight a switch with duplicate evaluation. After
activation, compare `nixos-version --configuration-revision` with the intended
commit and inspect the direct live service or file fact.

Dotfile edits propagate immediately and normally need no rebuild. Structural
agent-environment changes regenerate `docs/agent-environment.md`; generated
gateway references change through their renderer, never by hand.
