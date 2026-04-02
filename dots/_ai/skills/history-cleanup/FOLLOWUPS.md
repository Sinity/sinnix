# History Cleanup Follow-ups

These are worthwhile hardening steps after the core toolkit and a first real
repo rewrite are already working.

Status:

- implemented in the toolkit:
  - durable structural-run journal
  - persistent conflict-class ledger
  - rollback drills as machine-readable artifacts
- still optional:
  - human provenance index
  - PR-oriented review templates

## Implemented

- Durable structural-run journal:
  - `run-structural-plan --journal-jsonl ...`
  - emits run-level and op-level events
- Persistent conflict-class ledger:
  - `run-structural-plan --conflict-ledger-jsonl ...`
  - records auto-resolved and unresolved conflict classes
- Rollback drills as artifacts, not just backup references:
  - `verify-rollback-drill`
  - records recovered `HEAD` and tree hash from a backup ref and/or bundle

## Useful But Secondary

- Generate one post-run provenance index optimized for humans:
  - old SHA/range -> new SHA/range
  - message-only vs structural changes
  - pointers to machine-readable maps
- Add optional PR-oriented templates for teams that prefer review-heavy replay
  rather than in-place rewrite.

## Deliberately Not Core

- `git notes` as primary provenance
- review-bot-specific execution models
- docs-first rewrite sequencing as a default rule
- broad `filter-repo` substitution for semantically curated structural surgery
