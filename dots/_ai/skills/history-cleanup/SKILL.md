---
name: history-cleanup
description: Use the Lynchpin history-cleanup toolkit for audit-grade rewrite planning, launch-pack preparation, and durable history-surgery artefacts.
---

# History Cleanup

Canonical references:

- `/realm/project/sinnix/dots/_ai/skills/history-cleanup/README.md`
- `/realm/project/sinnix/dots/_ai/skills/history-cleanup/METHODOLOGY.md`
- `/realm/project/sinnix/dots/_ai/skills/history-cleanup/COMMIT_MESSAGE_CONTRACT.md`

Canonical root is `_ai/skills/history-cleanup`. The `codex/skills/...` and
`claude/skills/...` entries are agent-facing symlink aliases to this shared
toolkit.

Primary toolkit commands:

```bash
python /realm/project/sinnix/dots/_ai/skills/history-cleanup/cli.py --help
python /realm/project/sinnix/dots/_ai/skills/history-cleanup/cli.py derive-history-surface --help
python /realm/project/sinnix/dots/_ai/skills/history-cleanup/cli.py prepare-global-style-pass --help
python /realm/project/sinnix/dots/_ai/skills/history-cleanup/cli.py build-message-packets --help
python /realm/project/sinnix/dots/_ai/skills/history-cleanup/cli.py message-quality-report --help
python /realm/project/sinnix/dots/_ai/skills/history-cleanup/cli.py prepare-packet-exec --help
python /realm/project/sinnix/dots/_ai/skills/history-cleanup/cli.py packet-exec-status --help
python /realm/project/sinnix/dots/_ai/skills/history-cleanup/cli.py run-packet-exec --help

cd /realm/project/sinity-lynchpin
python -m lynchpin.analysis commit-facts --help
python -m lynchpin.analysis commit-shards --help
python -m lynchpin.analysis spark-review-packets --help
python -m lynchpin.analysis spark-review-reduce --help
```

Rules:

1. Read the methodology before structural operations.
2. Current hardcoded corpus root is `/realm/inbox/history-rewrite-project-runs/`.
3. Use this for audit-grade rewrite preparation, not routine git cleanup.
4. For a repo with unknown diff surface, derive raw log/diff transport artefacts and packet-budget statistics before assigning worker ranges.
5. Treat the commit-message contract as part of the methodology, not optional polish.
