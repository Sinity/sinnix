# Structural Execution Schema

This schema is the canonical target for structural history prep once a
repository moves beyond message rewrite and into executable split / merge /
reorder work.

It was distilled from the `sinex` launch-pack scratch corpus and promoted here
because the contract is reusable even though the `sinex` corpora themselves are
not.

## Goals

- make split execution explicit enough that a later rewrite run can assign
  source material to each child commit without rereading prose
- make merge execution explicit enough that each merged child has an ordered
  source list
- make reorder execution explicit enough that the final order is encoded rather
  than inferred from a strategy string
- preserve rich commit messages and explicit date policy notes

## Required Per-Spec Fields

### Common

- `spec_id`
- `kind`: `split | merge | reorder | redetail`
- `executability`: `executable | needs_manual_review`
- `blocker_reason`: required when `executability = needs_manual_review`
- `source_namespace`
- `source_selection_indices` and/or `source_atoms`
- `resolved_source_commits`
- `target_commits`

### Split

Each `target_commits[]` must include one of:

- `source_group_keys`
- `include_paths`
- `include_path_globs`

Optional but useful:

- `exclude_paths`
- `selection_strategy`

### Merge

Each `target_commits[]` must include:

- `ordered_source_selection_indices` or `ordered_source_atoms`

If merge children partition a band, each child should say which source items
feed it.

### Reorder

Each reorder spec must include:

- `ordered_source_selection_indices` or `ordered_source_atoms`
- `execution_mode`

Allowed `execution_mode` values:

- `reorder_only`
- `reorder_then_fixup`
- `reorder_then_merge`

If the reorder implies collapsing commits, the target commit message must be
present in `target_commits[0].commit_message`.

### Redetail

Redetail specs keep the original topology and only require:

- `source_selection_indices`
- `target_commits[0].commit_message`

## Date Policy

Recommended default:

- preserve author dates
- preserve committer dates unless a minimal monotonic offset is required by a
  reorder
- never restamp rewritten history as “today”

