# Launch Pack Contracts

The `sinex` rewrite established a stronger separation:

- reusable contracts and tooling live in the toolkit
- project-specific durable run corpora currently live under
  `/realm/inbox/history-rewrite-project-runs/<project>/`
- target repos may keep only a symlink or a thin pointer note if that helps
  local discoverability

This note captures the reusable contract layer worth keeping in the Codex
`history-cleanup` skill toolkit.

## Keep Project-Run Local

Do not fuse these as toolkit assets:

- `canonical-proposals-*.json`
- `all-rewrite-map-*.json`
- `strict-rewrite-map-*.json`
- `translated-selection-maps/*.json`
- `translated-surgery-plans/*.json`
- `current-structural-operations-plan.json`
- local validation sweeps, divergence audits, failure notes, and live
  `state-of-world` snapshots

Those are execution artifacts for one repository, not portable methodology.
They should still live canonically under the external project-run root.

## Promote To Toolkit

These are worth fusing as reusable contracts or examples:

- structural execution schema
- launch-pack manifest contract
- translated surgery manifest contract
- structural execution progress contract
- structural operations summary contract
- validation sweep contract
- post-validation scorecard contract
- message-wave ownership/outcome contracts
- run-journal, conflict-ledger, and rollback-drill artifacts

## Recommended Launch-Pack Manifest Shape

A reusable manifest should expose:

- `created`
- `project`
- `head_sha`
- `prepared_commits`
- `remaining_commits`
- `current_branch`
- `working_tree_clean`
- `pure_reword_applied_on_master`
- `canonical_refs`
- `rollback_refs`

`canonical_refs` should point at the project-run state note, readiness note,
execution summaries, and any translated-plan or scorecard artifacts.

## Recommended Translated-Surgery Manifest Shape

A translated-surgery manifest should expose:

- `summary`
- `plans`

`summary` should include:

- rewritten branch name
- prepared current-history mapping rows
- translated plan count
- selection-map file list
- translated-plan file list

Each item in `plans[]` should include:

- `source`
- `translated`
- `resolver_kind`
- `executability`

This is the bridge from prose/spec packs into deterministic execution packs.

## Recommended Structural-Execution Progress Shape

Execution progress should stay machine-readable and compact:

- `schema_ref`
- `global_validation_status`
- `failure_note`
- `tree_scorecard`
- `packs`

Each pack row should include:

- `name`
- `status`
- one or more checkpoint files
- `owned_output`
- `manual_review_residue`
- `note`

This is the right level for an operator status dashboard. It is not a
substitute for project-run prose, but it gives a stable machine surface.

## Recommended Structural-Operations Summary Shape

This should remain compact and dashboard-friendly:

- `head_sha`
- `root_sha`
- `selected_operation_count`
- `primary_spec_count`
- `selected_spec_count`
- `alternate_count`
- `skipped_count`
- `superseded_count`

The summary exists so an operator can answer "how much real structural work is
in play?" without opening the full plan.

## Recommended Validation Artifacts

Promote two machine-readable outputs:

- `tree-scorecard.json`
- `validation-sweep.json`

`tree-scorecard.json` should expose:

- `left_repo`
- `right_repo`
- `left_ref`
- `right_ref`
- `only_left_count`
- `only_right_count`
- `differing_count`
- bounded samples for each mismatch class

`validation-sweep.json` should expose:

- `generated_at`
- `plan_path`
- `op_count`
- `exact_count`
- `fail_count`
- `results[]` with `op_id`, anchor SHA, and embedded tree comparison

This is the hard proof layer for structural readiness.

## Recommended Message-Wave Contracts

The portable layer should include:

- `assignment-manifest.json`
- `message-wave-outcome.json`

`assignment-manifest.json` keeps worker ownership explicit:

- `agent_count`
- `assignments[]` with `{agent, batches[]}`

`message-wave-outcome.json` should consolidate:

- apply/ref metadata
- targeted commit counts
- quality deltas
- identity/date preservation counts

This keeps second-pass message strengthening deterministic and auditable.

## Recommended Operational Artifacts

The toolkit now supports three operational artifacts directly:

- `run-journal.jsonl`
- `conflict-ledger.jsonl`
- `rollback-drill.json`

These are reusable because they describe how the rewrite was executed and
verified, not what one repository happened to contain.

## Practical Rule

When a scratch artifact answers “how should future repos structure this kind of
state?”, fuse it.

When it answers “what happened in this one repo on this one run?”, keep it in a
project run under `/realm/inbox/history-rewrite-project-runs/<project>/`.
