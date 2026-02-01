# Sinnix Configuration

> **Compressed understanding of sinnix NixOS configuration structure, patterns, and organizational rules.** Updated with every structural change.

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

@.claude/includes/modules/_index.md

---

## Development

@.claude/includes/development/_index.md

---

## Reference

@.claude/includes/reference/_index.md
