---
name: sinnix-module-placement
description: Choose correct file placement for new sinnix changes (top-level modules vs features vs services vs bundles) and enforce no-cross-layer drift.
---

# Sinnix Module Placement

Use this skill when adding or moving configuration in `sinnix`.

## Decision Rules

- `modules/*.nix`: system/platform infrastructure.
- `modules/features/*`: user-facing capabilities.
- `modules/services/*`: long-running systemd daemons.
- `modules/bundles/*`: presets that only enable other modules.

## Placement Guardrails

- Do not put daemon-only logic into `features/`.
- Do not put user-interaction UX into top-level infrastructure modules.
- Bundle modules must not own unique config; they only compose features.
- Prefer one coherent module per capability; avoid scattered partial modules.

## Validation Commands

```bash
nix eval --json .#checks.x86_64-linux --apply builtins.attrNames
nix eval --raw .#checks.x86_64-linux.nixos-dev-shell.name
```

For broad changes, run a full check flow before final commit.
