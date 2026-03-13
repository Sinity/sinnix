# History Cleanup Toolkit

This package is the canonical home for both:

- the reusable history-cleanup toolkit
- the colocated project-specific run corpora produced with it

The workflow was first developed against `sinex` and is now housed directly in
the Codex `history-cleanup` skill.

Use it when a repository needs:

- audit-grade commit-message rewrites
- atomicity analysis over large commit ranges
- deterministic prep for split / merge / reorder history surgery
- one canonical launch pack that states what is really ready

This toolkit sits inside the Codex skill tree, separate from Lynchpin's source,
warehouse, and view layers. Those layers measure or present project state;
this toolkit prepares audit-grade history cleanup work for coding agents.

The finished `sinex` rewrite corpus now also lives here as the canonical worked
example under `project-runs/`, instead of remaining canonically in repo-local
scratch space.

## Contents

- [METHODOLOGY.md](/realm/project/sinnix/dots/codex/skills/history-cleanup/METHODOLOGY.md)
  Reusable end-to-end playbook
- [cli.py](/realm/project/sinnix/dots/codex/skills/history-cleanup/cli.py)
  Mechanical helper CLI for wave carving, normalization, message-wave
  finalization, review bundles, rewrite-map generation, and structural plan execution
- [STRUCTURAL_EXECUTION_SCHEMA.md](/realm/project/sinnix/dots/codex/skills/history-cleanup/STRUCTURAL_EXECUTION_SCHEMA.md)
  Reusable contract for executable split / merge / reorder specs
- [LAUNCH_PACK_CONTRACTS.md](/realm/project/sinnix/dots/codex/skills/history-cleanup/LAUNCH_PACK_CONTRACTS.md)
  Reusable guidance for what belongs in a repo-local launch pack versus the portable toolkit
- [FOLLOWUPS.md](/realm/project/sinnix/dots/codex/skills/history-cleanup/FOLLOWUPS.md)
  Hardening ideas worth doing after the core workflow is already in place
- [templates/PROJECT_BOOTSTRAP_CHECKLIST.md](/realm/project/sinnix/dots/codex/skills/history-cleanup/templates/PROJECT_BOOTSTRAP_CHECKLIST.md)
  First-pass onboarding checklist for a new repo
- [templates/DIRECTORY_SKELETON.md](/realm/project/sinnix/dots/codex/skills/history-cleanup/templates/DIRECTORY_SKELETON.md)
  Recommended durable artifact layout
- [templates/launch-pack-manifest.example.json](/realm/project/sinnix/dots/codex/skills/history-cleanup/templates/launch-pack-manifest.example.json)
  Example machine-readable launch-pack manifest
- [templates/structural-execution-progress.example.json](/realm/project/sinnix/dots/codex/skills/history-cleanup/templates/structural-execution-progress.example.json)
  Example machine-readable structural execution progress record
- [templates/translated-surgery-manifest.example.json](/realm/project/sinnix/dots/codex/skills/history-cleanup/templates/translated-surgery-manifest.example.json)
  Example bridge from rewritten SHA space into translated structural packs
- [templates/structural-operations-summary.example.json](/realm/project/sinnix/dots/codex/skills/history-cleanup/templates/structural-operations-summary.example.json)
  Example compact operations summary for operator dashboards
- [templates/tree-scorecard.example.json](/realm/project/sinnix/dots/codex/skills/history-cleanup/templates/tree-scorecard.example.json)
  Example final tracked-tree equivalence scorecard
- [templates/validation-sweep.example.json](/realm/project/sinnix/dots/codex/skills/history-cleanup/templates/validation-sweep.example.json)
  Example per-op local exactness sweep
- [templates/assignment-manifest.example.json](/realm/project/sinnix/dots/codex/skills/history-cleanup/templates/assignment-manifest.example.json)
  Example worker ownership ledger for a message-strengthening pass
- [templates/message-wave-outcome.example.json](/realm/project/sinnix/dots/codex/skills/history-cleanup/templates/message-wave-outcome.example.json)
  Example consolidated result for a message-only strengthening wave
- [templates/run-journal.example.jsonl](/realm/project/sinnix/dots/codex/skills/history-cleanup/templates/run-journal.example.jsonl)
  Example durable structural-run journal
- [templates/conflict-ledger.example.jsonl](/realm/project/sinnix/dots/codex/skills/history-cleanup/templates/conflict-ledger.example.jsonl)
  Example conflict-class ledger
- [templates/rollback-drill.example.json](/realm/project/sinnix/dots/codex/skills/history-cleanup/templates/rollback-drill.example.json)
  Example rollback-drill artifact
- [templates/execution-status.template.md](/realm/project/sinnix/dots/codex/skills/history-cleanup/templates/execution-status.template.md)
  Minimal human-facing execution-status template
- [project-runs/README.md](/realm/project/sinnix/dots/codex/skills/history-cleanup/project-runs/README.md)
  Index of project-specific worked examples and durable run corpora

## What This Does Not Do

The CLI reduces glue work, but it does not replace:

- full patch reading
- atomicity judgment
- blocker accounting
- launch-pack honesty

Those remain operator responsibilities and are codified in
[METHODOLOGY.md](/realm/project/sinnix/dots/codex/skills/history-cleanup/METHODOLOGY.md).

## CLI Entry Point

```sh
python /realm/project/sinnix/dots/codex/skills/history-cleanup/cli.py --help
```

## Recommended Use

1. Read [METHODOLOGY.md](/realm/project/sinnix/dots/codex/skills/history-cleanup/METHODOLOGY.md).
2. Instantiate the directory skeleton for the target project run.
3. Run the bootstrap checklist.
4. Only then start carving waves and assigning workers.

## Relationship to `sinex`

`sinex` remains the first complete concrete instance of this process.

Current `sinex` state:

- history-wide message rewrite applied
- structural split / merge / reorder rewrite applied after local-op and
  disposable full-replay validation
- targeted second message-only strengthening pass applied on top
- launch-pack corpus now lives canonically at:
  - [project-runs/sinex/README.md](/realm/project/sinnix/dots/codex/skills/history-cleanup/project-runs/sinex/README.md)

That makes `sinex` the reference implementation for this toolkit, not its only
home.
