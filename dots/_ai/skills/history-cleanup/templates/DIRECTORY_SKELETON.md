# Recommended Directory Skeleton

Use this as the durable layout for a project-specific history-cleanup run.

```text
/realm/inbox/history-rewrite-project-runs/
└── <project>/
    ├── canonical/
    │   ├── launch-pack/
    │   │   ├── agent-work/
    │   │   ├── translated-surgery-plans/
    │   │   ├── manifest.json
    │   │   ├── execution-status-current.md
    │   │   ├── structural-execution-progress.json
    │   │   ├── run-journal.jsonl
    │   │   ├── conflict-ledger.jsonl
    │   │   └── rollback-drills/
    │   └── archive/
    ├── notes/
    └── legacy/
```

## Rules

- `/realm/inbox/history-rewrite-project-runs/<project>/canonical/` is the only
  authoritative zone for one concrete run
- `launch-pack/` is the only place allowed to make readiness claims
- `agent-work/` is for worker outputs and intermediate determinization packs
- `archive/` is where superseded partials go once the canonical surface absorbs
  them
- reusable tooling and methodology live in the shared skill toolkit, while the
  durable corpora live in the external inbox root

## Minimal Canonical File Set

At minimum, the canonical area should expose:

- before/after rewrite ledger
- rewrite process metadata
- attribution summary if relevant
- wave corpora
- atomicity coverage audit
- detailed structural plans
- deterministic executable packs
- launch-pack manifest
- execution-status note
- run journal / conflict ledger if structural execution is exercised
- rollback drill artifact
- rollback references

## When to Add More

Add project-specific extras only when they are durable and queryable, for example:

- translated structural plans after a pure reword pass
- optional opportunity packs
- supersession ledgers
- project-specific generated-noise policies
