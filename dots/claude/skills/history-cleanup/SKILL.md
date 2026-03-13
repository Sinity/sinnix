---
name: history-cleanup
description: Use the Lynchpin history-cleanup toolkit for audit-grade rewrite planning, launch-pack preparation, and durable history-surgery artefacts.
triggers:
  - "history cleanup"
  - "rewrite launch pack"
  - "message wave"
allowed-tools:
  - Read
  - Grep
  - Glob
  - Bash
  - Write
  - Edit
argument-hint: "<subcommand> [args]"
---

# History Cleanup

Canonical references:

- `/realm/project/sinnix/dots/codex/skills/history-cleanup/README.md`
- `/realm/project/sinnix/dots/codex/skills/history-cleanup/METHODOLOGY.md`

Primary command:

```bash
python /realm/project/sinnix/dots/codex/skills/history-cleanup/cli.py --help
```

Rules:

1. Read the methodology before structural operations.
2. Keep run artefacts in `/realm/project/sinnix/dots/codex/skills/history-cleanup/project-runs/`.
3. Use this for audit-grade rewrite preparation, not routine git cleanup.
