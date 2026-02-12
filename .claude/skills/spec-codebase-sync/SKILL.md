---
name: spec-codebase-sync
description: |
  Systematically compare specification/documentation against codebase implementation.
  Triggers: "sync spec with code", "compare spec to implementation", "what's implemented vs spec",
  "doc-syncer", "specification audit", "track what's done vs to-do".
---

# Spec-Codebase Synchronization

Compare specification documents against actual implementation. Categorize differences, track completion status.

## Process

### Phase 1: Inventory

```
[spec-sync:inventory]
1. Locate spec documents (README, docs/, SPEC.md, etc.)
2. Identify codebase entry points
3. List major spec sections/features
```

### Phase 2: Mapping

```
[spec-sync:mapping]
For each spec item:
- Find corresponding code (or note "not found")
- Assess implementation completeness: DONE / PARTIAL / STUB / MISSING
- Note deviations from spec
```

### Phase 3: Report

```
[spec-sync:report]
Output structured report:

## Implementation Status

| Spec Section | Status | Location | Notes |
|--------------|--------|----------|-------|
| Feature A    | DONE   | src/a.rs | Matches spec |
| Feature B    | PARTIAL| src/b.rs | Missing error handling |
| Feature C    | MISSING| -        | Not started |

## Deviations
- [list differences between spec and implementation]

## Gaps
- [spec items with no code]
- [code with no spec coverage]
```

### Phase 4: Recommendations

```
[spec-sync:recommend]
Prioritized list:
1. Critical gaps (spec promises, code missing)
2. Deviations to reconcile (code differs from spec)
3. Spec updates needed (code is correct, spec outdated)
```

## Scope Confirmation

Before starting, confirm:

- Which spec document(s)?
- Which code directories?
- Focus area or full audit?

## Output Modes

- `--brief`: Status table only
- `--full`: Complete report with code snippets
- `--gaps-only`: Just missing/partial items
