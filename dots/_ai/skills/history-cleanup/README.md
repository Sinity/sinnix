# History Cleanup Toolkit

This package is the canonical home for both:

- the reusable history-cleanup toolkit
- the playbooks and contracts that govern external project run corpora

The workflow was first developed against `sinex` and is now housed directly in
the shared `_ai` `history-cleanup` skill, with agent-facing `codex` and
`claude` aliases pointing at the same toolkit root.

Use it when a repository needs:

- audit-grade commit-message rewrites
- atomicity analysis over large commit ranges
- deterministic prep for split / merge / reorder history surgery
- one canonical launch pack that states what is really ready
- repo-specific packet sizing for 128k-class review workers based on actual diff volume

This toolkit sits inside the shared skill tree, separate from Lynchpin's
source, warehouse, and view layers. Those layers measure or present project
state; this toolkit prepares audit-grade history cleanup work for coding
agents.

The durable run corpora no longer live inside this repo. The current hardcoded
corpus root is:

- `/realm/inbox/history-rewrite-project-runs/`

## Contents

- [METHODOLOGY.md](/realm/project/sinnix/dots/_ai/skills/history-cleanup/METHODOLOGY.md)
  Reusable end-to-end playbook
- [COMMIT_MESSAGE_CONTRACT.md](/realm/project/sinnix/dots/_ai/skills/history-cleanup/COMMIT_MESSAGE_CONTRACT.md)
  Quality bar, anti-patterns, and worker output contract for rewritten commit messages
- [cli.py](/realm/project/sinnix/dots/_ai/skills/history-cleanup/cli.py)
  Mechanical helper CLI for wave carving, normalization, message-wave
  finalization, review bundles, rewrite-map generation, and structural plan execution
- [STRUCTURAL_EXECUTION_SCHEMA.md](/realm/project/sinnix/dots/_ai/skills/history-cleanup/STRUCTURAL_EXECUTION_SCHEMA.md)
  Reusable contract for executable split / merge / reorder specs
- [LAUNCH_PACK_CONTRACTS.md](/realm/project/sinnix/dots/_ai/skills/history-cleanup/LAUNCH_PACK_CONTRACTS.md)
  Reusable guidance for what belongs in a repo-local launch pack versus the portable toolkit
- [FOLLOWUPS.md](/realm/project/sinnix/dots/_ai/skills/history-cleanup/FOLLOWUPS.md)
  Hardening ideas worth doing after the core workflow is already in place
- [templates/PROJECT_BOOTSTRAP_CHECKLIST.md](/realm/project/sinnix/dots/_ai/skills/history-cleanup/templates/PROJECT_BOOTSTRAP_CHECKLIST.md)
  First-pass onboarding checklist for a new repo
- [templates/DIRECTORY_SKELETON.md](/realm/project/sinnix/dots/_ai/skills/history-cleanup/templates/DIRECTORY_SKELETON.md)
  Recommended durable artifact layout
- [templates/launch-pack-manifest.example.json](/realm/project/sinnix/dots/_ai/skills/history-cleanup/templates/launch-pack-manifest.example.json)
  Example machine-readable launch-pack manifest
- [templates/structural-execution-progress.example.json](/realm/project/sinnix/dots/_ai/skills/history-cleanup/templates/structural-execution-progress.example.json)
  Example machine-readable structural execution progress record
- [templates/translated-surgery-manifest.example.json](/realm/project/sinnix/dots/_ai/skills/history-cleanup/templates/translated-surgery-manifest.example.json)
  Example bridge from rewritten SHA space into translated structural packs
- [templates/structural-operations-summary.example.json](/realm/project/sinnix/dots/_ai/skills/history-cleanup/templates/structural-operations-summary.example.json)
  Example compact operations summary for operator dashboards
- [templates/tree-scorecard.example.json](/realm/project/sinnix/dots/_ai/skills/history-cleanup/templates/tree-scorecard.example.json)
  Example final tracked-tree equivalence scorecard
- [templates/validation-sweep.example.json](/realm/project/sinnix/dots/_ai/skills/history-cleanup/templates/validation-sweep.example.json)
  Example per-op local exactness sweep
- [templates/assignment-manifest.example.json](/realm/project/sinnix/dots/_ai/skills/history-cleanup/templates/assignment-manifest.example.json)
  Example worker ownership ledger for a message-strengthening pass
- [templates/message-wave-outcome.example.json](/realm/project/sinnix/dots/_ai/skills/history-cleanup/templates/message-wave-outcome.example.json)
  Example consolidated result for a message-only strengthening wave
- [templates/run-journal.example.jsonl](/realm/project/sinnix/dots/_ai/skills/history-cleanup/templates/run-journal.example.jsonl)
  Example durable structural-run journal
- [templates/conflict-ledger.example.jsonl](/realm/project/sinnix/dots/_ai/skills/history-cleanup/templates/conflict-ledger.example.jsonl)
  Example conflict-class ledger
- [templates/rollback-drill.example.json](/realm/project/sinnix/dots/_ai/skills/history-cleanup/templates/rollback-drill.example.json)
  Example rollback-drill artifact
- [templates/execution-status.template.md](/realm/project/sinnix/dots/_ai/skills/history-cleanup/templates/execution-status.template.md)
  Minimal human-facing execution-status template
- `/realm/inbox/history-rewrite-project-runs/README.md`
  External index of project-specific worked examples and durable run corpora

## What This Does Not Do

The CLI reduces glue work, but it does not replace:

- full patch reading
- atomicity judgment
- blocker accounting
- launch-pack honesty

Those remain operator responsibilities and are codified in
[METHODOLOGY.md](/realm/project/sinnix/dots/_ai/skills/history-cleanup/METHODOLOGY.md).

## CLI Entry Point

```sh
python /realm/project/sinnix/dots/_ai/skills/history-cleanup/cli.py --help
```

## Recommended Use

1. Read [METHODOLOGY.md](/realm/project/sinnix/dots/_ai/skills/history-cleanup/METHODOLOGY.md).
2. Instantiate the directory skeleton for the target project run.
3. Materialize repo history derivatives before carving waves:
   - full log
   - full diff log
   - numstat log
   - per-commit diff-size summary
   - packet-budget simulation for the worker model you intend to use
4. Define the commit-message quality bar from [COMMIT_MESSAGE_CONTRACT.md](/realm/project/sinnix/dots/_ai/skills/history-cleanup/COMMIT_MESSAGE_CONTRACT.md).
5. Build token-budgeted message packets with message-only edge context.
6. Materialize packet-exec prompts/schemas/manifests for the worker model you will actually run.
7. Run the bootstrap checklist.
8. Only then start carving waves and assigning workers.

Recommended CLI sequence:

```sh
python /realm/project/sinnix/dots/_ai/skills/history-cleanup/cli.py derive-history-surface --repo <repo> --out-dir <run>/canonical/history-derivatives
python /realm/project/sinnix/dots/_ai/skills/history-cleanup/cli.py prepare-global-style-pass --repo <repo> --commit-surface-json <run>/canonical/history-derivatives/commit-surface.json --out-dir <run>/canonical/global-style
python /realm/project/sinnix/dots/_ai/skills/history-cleanup/cli.py build-message-packets --repo <repo> --commit-surface-json <run>/canonical/history-derivatives/commit-surface.json --out-dir <run>/canonical/message-packets
python /realm/project/sinnix/dots/_ai/skills/history-cleanup/cli.py prepare-packet-exec --packet-index <run>/canonical/message-packets/index.json --out-dir <run>/canonical/message-exec --style-guide-file <run>/canonical/global-style/response.json
python /realm/project/sinnix/dots/_ai/skills/history-cleanup/cli.py packet-exec-status --manifest <run>/canonical/message-exec/manifest.json
python /realm/project/sinnix/dots/_ai/skills/history-cleanup/cli.py run-packet-exec --manifest <run>/canonical/message-exec/manifest.json --jobs 4
python /realm/project/sinnix/dots/_ai/skills/history-cleanup/cli.py message-quality-report --input-json <candidate-json> --message-source proposed
```

For a wide-context worker, switch the packet geometry explicitly:

```sh
python /realm/project/sinnix/dots/_ai/skills/history-cleanup/cli.py prepare-global-style-pass --repo <repo> --commit-surface-json <run>/canonical/history-derivatives/commit-surface.json --out-dir <run>/canonical/global-style --window-profile wide-1m-750k
python /realm/project/sinnix/dots/_ai/skills/history-cleanup/cli.py build-message-packets --repo <repo> --commit-surface-json <run>/canonical/history-derivatives/commit-surface.json --out-dir <run>/canonical/message-packets-1m --window-profile wide-1m-750k
python /realm/project/sinnix/dots/_ai/skills/history-cleanup/cli.py prepare-packet-exec --packet-index <run>/canonical/message-packets-1m/index.json --out-dir <run>/canonical/message-exec-1m --style-guide-file <run>/canonical/global-style/response.json
```

The packet-exec flow exists because the useful operator interface is not a pile
of ad hoc prompts. It is:

- one generated `prompt.md` per packet
- one one-line request per packet that `@`-mentions that prompt file
- one JSON schema per packet passed to `codex exec --output-schema`
- one durable status file per packet
- one proposal JSON per packet ready for downstream normalization/finalization

Do not assume the default worker range geometry applies to every repository.
`polylogue` is now a concrete counterexample: its diff surface is large enough
that fixed `24-48` full-patch commits per 128k-context worker is not viable.

The wide-window profile does not mean "dump the whole repo into one call". It
means:

- derive one repo-wide style guide first
- increase owned diff budget per packet
- increase edge context depth
- keep a hard commit-count cap so packets still reflect coherent feature arcs

## Relationship to `sinex`

`sinex` remains the first complete concrete instance of this process.

Current `sinex` state:

- history-wide message rewrite applied
- structural split / merge / reorder rewrite applied after local-op and
  disposable full-replay validation
- targeted second message-only strengthening pass applied on top
- launch-pack corpus now lives canonically at:
  - `/realm/inbox/history-rewrite-project-runs/sinex/README.md`

That makes `sinex` the reference implementation for this toolkit, not its only
home.
