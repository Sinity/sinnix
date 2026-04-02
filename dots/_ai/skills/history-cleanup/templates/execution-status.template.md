# Execution Status

- Current branch / ref
- Current canonical `HEAD`
- Message rewrite state
- Structural rewrite prep state
- Local per-op validation state
- Disposable full replay state
- Real apply state
- Latest rollback refs / bundle paths
- Canonical machine-readable pointers:
  - manifest
  - structural execution progress
  - translated surgery manifest
  - structural operations summary
  - tree scorecard
  - validation sweep
  - message-wave outcome

## Current Gate

- What remains before the next irreversible operation
- What exact artifact proves readiness

## Historical Failure Provenance

- Optional short note pointing to the last important failed validation artifact
- Only keep this section while it is still operationally relevant
