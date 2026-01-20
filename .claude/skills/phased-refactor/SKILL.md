---
name: phased-refactor
description: |
  Large refactoring broken into verified phases with commits after each.
  Triggers: "phased refactor", "split into phases", "incremental refactor",
  "refactor in stages", "commit after each phase", "safe refactoring".
---

# Phased Refactoring

Break large refactors into verified phases. Each phase compiles, tests pass, committed.

## Process

### Phase 0: Planning
```
[refactor:plan]
1. Understand current state
2. Define target state
3. Identify dependencies and risks
4. Break into phases (each independently verifiable)

Output:
## Refactor Plan: [name]

Target: [what we're achieving]

Phases:
1. [Phase name] - [what changes] - [risk: low/med/high]
2. [Phase name] - [what changes] - [risk: low/med/high]
...

Dependencies: [what must happen in order]
Rollback: [how to undo if needed]
```

### Phase N: Execute
```
[refactor:phase-N]
1. Make changes for this phase only
2. Compile check
3. Run tests
4. If pass → commit with message "[refactor] Phase N: description"
5. If fail → fix or rollback, report blocker
```

### Completion
```
[refactor:complete]
1. Verify all phases committed
2. Run full test suite
3. Summary of changes made
```

## Phase Design Principles

Good phases:
- Compile independently
- Don't break other code mid-phase
- Have clear rollback (git reset)
- Are small enough to review

Bad phases:
- Leave code in broken state
- Mix unrelated changes
- Are too large to understand

## Commit Discipline

Each phase commit:
```
[refactor] Phase N/M: brief description

- Change 1
- Change 2

Part of: [overall refactor goal]
```

## Scope Confirmation

Before starting:
- What's the refactor goal?
- Acceptable to commit incrementally?
- Any phases that need user review before proceeding?

## Abort Conditions

Stop and report if:
- Phase introduces test failures that can't be fixed quickly
- Scope expands beyond original plan
- Blocking dependency discovered
