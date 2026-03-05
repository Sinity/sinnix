---
name: workspace-recon-scan
description: Scan many local repositories quickly and summarize branch/dirty-state/recency in table or JSON form. Use when you need high-throughput workspace visibility before planning or batching work.
metadata:
  short-description: High-throughput repo scanner
---

# Workspace Recon Scan

Use this skill when you need a fast "what is happening across repos" snapshot.

## Script

`scripts/workspace_recon_scan.py`

## Examples

```bash
# Human table over /realm/project
python3 scripts/workspace_recon_scan.py --root /realm/project

# JSON output, only dirty repos, include approximate size
python3 scripts/workspace_recon_scan.py --root /realm/project --changed-only --with-size --json

# Scan deeper and limit output
python3 scripts/workspace_recon_scan.py --root /realm/project --max-depth 4 --limit 20
```

## Notes

- Default root is `/realm/project`.
- Scanner discovers git repos by locating `.git` directories.
- Use `--json` when feeding output into automation or other agents.
