---
name: incident-evidence-freeze
description: Freeze incident evidence before resolving conflicts, restoring files, or changing services. Use when a worktree is conflicted, an artifact disappeared, recovery may mutate Git or Beads state, or the operator says preserve evidence first. Do not use for ordinary status checks.
metadata:
  short-description: Preserve incident evidence before mutation
---

# Incident evidence freeze

Evidence capture is the first operation in an incident. Run the bundled
scripts/freeze.sh against the exact repository and an explicit output
directory. It records the timestamp, repository identity, status, index and
worktree patches, reflog, and hashes of named conflicted files. The output is
private and atomic. It does not resolve conflicts, restore files, delete
anything, stop services, or write to the source repository.

After the freeze, record the recovery boundary in the incident note. Name the
mutation that is authorized, its exact target, and its verification. If the
target or authorization is unclear, stop after the freeze.

Required evidence order:

1. Exact repository path, branch, HEAD, status, and reflog.
2. Index and worktree bytes, including named conflict files.
3. Relevant service state and bounded logs, when a service is implicated.
4. Beads JSONL and Dolt evidence, when task state is implicated.
5. Snapshot or backup candidates, without mutating them.

See references/freeze-checklist.md for the handoff fields and authorization
boundary.
