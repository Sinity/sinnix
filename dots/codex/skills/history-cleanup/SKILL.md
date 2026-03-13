---
name: history-cleanup
description: >
  Run the Lynchpin history-cleanup toolkit for audit-grade commit-message
  rewrites and structural history surgery prep. Use when a repository needs
  deterministic rewrite planning, launch-pack preparation, or reusable
  archaeology over large commit ranges.
metadata:
  short-description: Audit-grade history cleanup workflow
---

# History Cleanup

This skill owns the canonical toolkit at:

- `/realm/project/sinnix/dots/codex/skills/history-cleanup/README.md`
- `/realm/project/sinnix/dots/codex/skills/history-cleanup/METHODOLOGY.md`

## Command

```bash
python /realm/project/sinnix/dots/codex/skills/history-cleanup/cli.py --help
```

## Workflow

1. Read `README.md` and `METHODOLOGY.md` before running any structural operation.
2. Treat the toolkit as preparation and accounting, not as a substitute for patch judgment.
3. Keep durable run artefacts under `/realm/project/sinnix/dots/codex/skills/history-cleanup/project-runs/`; do not bury them in scratch notes.
4. Use the toolkit for history surgery prep, message-wave prep, review-bundle generation, and launch-pack honesty checks.

## Do Not Use This For

- ordinary interactive rebases
- small local commit cleanups
- speculative rewrite plans with no artifact trail
