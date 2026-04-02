# Project Bootstrap Checklist

Use this before starting a history-cleanup run on a new repository.

## 1. Scope and Risk

- define the target branch
- define the canonical project-run path under `/realm/inbox/history-rewrite-project-runs/`
- define whether the full branch or a bounded history window is in scope
- decide whether top-of-branch dirty commits should be preserved first
- decide whether commit-message rewrite alone is useful even if structural
  surgery will come later

## 2. Freeze the Surface

- record current `HEAD`
- record upstream divergence
- inspect dirty tree
- cluster dirty work into coherent commits if it should survive the rewrite
- verify a clean working tree, or document explicit exclusions

## 3. Backups

- create a local backup ref
- create an external clone or bundle outside the repo
- record rollback paths in a durable note
- decide where rollback-drill artifacts will be written

## 4. Evidence Inputs

- confirm git history is accessible and complete
- identify session-log sources if intent or authorship matters
- identify plan-file sources if they sharpen scope
- identify generated-noise areas for the repo
  - examples: `.sqlx`, lockfiles, codegen output, vendored snapshots

## 5. Canonical Layout

- create the durable artifact layout from
  [DIRECTORY_SKELETON.md](/realm/project/sinnix/dots/_ai/skills/history-cleanup/templates/DIRECTORY_SKELETON.md)
- create `/realm/inbox/history-rewrite-project-runs/<project>/`
- decide whether the target repo should also keep a pointer note or symlink
- decide where canonical outputs will live
- decide where worker outputs will live
- decide where superseded partials will be archived
- decide whether the launch pack will carry:
  - `run-journal.jsonl`
  - `conflict-ledger.jsonl`
  - `rollback-drills/*.json`

## 6. Wave Strategy

- choose default owned commits per worker
  - recommended: `32`
- choose overlap
  - recommended: `2`
- choose worker count
  - recommended: `6-8`
- choose whether rewrite and structural waves will run concurrently

## 7. Policy Setup

- write the generated-noise policy
- write the date policy
- write the attribution policy if needed
- write repo-local semantic rules that are easy to misread from diffs alone
  - examples:
    - project-specific test attribute policy
    - when a helper is effectively zero-cost if used without an optional context
    - whether certain directories are generated fallout rather than primary signal
  - use these notes to avoid misreading commit intent, not to impose a second
    blanket rewrite policy over history
  - example:
    - if `#[sinex_test]` without `TestContext` is effectively zero-cost, do not
      invent a fake "convert to raw #[test] for performance" rationale
- write the blocker-accounting rule:
  - every residue item must be executable, optional, or an explicit blocker

## 8. Launch-Pack Success Test

Before you start, define what "done" will mean:

- current `HEAD` covered
- message rewrite applied or ready as one explicit map
- atomicity coverage complete
- structural residue determinized for the core pack
- blocker ledger empty
- optional packs separated
- launch pack agrees with reality
- if structural surgery is in scope:
  - disposable replay must prove exact-band execution and final tracked-tree
    equivalence before any landing claim
