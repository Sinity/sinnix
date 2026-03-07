# Sinnix Configuration

> **Compressed understanding of sinnix NixOS configuration structure, patterns, and organizational rules.** Updated with every structural change.

---

## Operational Loop (Silent, Every Reply)

- Reconfirm requested scope and explicit constraints.
- Reconfirm module placement against taxonomy before editing.
- Reconfirm no compatibility aliases/shims are introduced.
- Reconfirm existing scripts/skills were checked before adding new helpers.
- Reconfirm commit boundary is coherent and validated.

## Context Architecture

- Keep `AGENTS.md` as always-on map of module taxonomy, invariants, and architecture decisions.
- Use skills for heavy procedural workflows (for example orchestration, CI repair, desktop control).
- Repo-local skills: `.agents/skills/` (Codex), `.claude/skills/` (Claude). Example: `sinnix-module-placement`.
- Rule: if guidance is needed on most turns, keep it here; if it is specialized or long-form, move it to a skill.

## No-Alias Rule

- Do not preserve deprecated compatibility interfaces for renamed files/modules/options/commands.
- Apply full rename and reference updates in one pass.

---

## Module Taxonomy

Sinnix modules follow a clear hierarchy based on **purpose and abstraction level**:

```
modules/
├── *.nix              # Infrastructure & platform (system-level)
├── features/          # User-facing capabilities (what users interact with)
├── services/          # Long-running systemd daemons
├── bundles/           # Convenience presets (groups of features)
└── lib/               # Helper functions
```

### Decision Tree: Where Does My Config Belong?

```
MATCH config_type:
  | System infrastructure (networking, storage, nix settings)
    → modules/*.nix (top-level)

  | User-facing application or capability
    → modules/features/{cli,desktop,dev}/*.nix

  | Systemd daemon (primary purpose is background service)
    → modules/services/*.nix

  | Convenience preset (enables multiple features)
    → modules/bundles/*.nix

  | Reusable helper function
    → modules/lib/*.nix
```

---

## Philosophy

- **Explicit over implicit**: Document organizational rules, don't rely on intuition
- **Clear boundaries**: Top-level = infrastructure, features = user-facing, services = daemons
- **Consistent granularity**: One file per significant feature, group related small features
- **Maintenance discipline**: Update CLAUDE.md with every structural change
- **Pattern enforcement**: Use decision trees, not ad-hoc placement

---

## Module Details

@.claude/includes/modules/\_index.md

---

## Development

@.claude/includes/development/\_index.md

---

## Reference

@.claude/includes/reference/\_index.md
