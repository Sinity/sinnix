---
name: test-audit
description: |
  Comprehensive test coverage analysis with gap identification and remediation.
  Triggers: "audit tests", "test coverage", "find test gaps", "plug test holes",
  "ensure tests compile", "red-team testing", "adversarial test review".
---

# Comprehensive Test Audit

Analyze test suite, identify gaps, implement missing coverage. Autonomous until complete.

## Process

### Phase 1: Compile Check

```
[test-audit:compile]
1. Run test compilation (cargo test --no-run, pytest --collect-only, etc.)
2. Fix any compilation errors
3. Report: "Tests compile. N test files, M test cases."
```

### Phase 2: Coverage Analysis

```
[test-audit:coverage]
1. Run tests with coverage if available
2. Map: code paths → test coverage
3. Identify:
   - Untested public APIs
   - Untested error paths
   - Edge cases without tests
   - Integration gaps
```

### Phase 3: Gap Assessment

```
[test-audit:gaps]
Categorize gaps by severity:

CRITICAL - Public API without any test
HIGH     - Error handling path untested
MEDIUM   - Edge case missing
LOW      - Internal helper untested

Output gap list with locations.
```

### Phase 4: Remediation

```
[test-audit:fix]
For each gap (highest severity first):
1. Write test
2. Verify it compiles
3. Verify it passes (or document expected failure)
4. Commit incrementally if requested

Report progress: "Fixed N/M gaps. Remaining: [list]"
```

### Phase 5: Verification

```
[test-audit:verify]
1. Run full test suite
2. Confirm all pass
3. Report final coverage metrics
```

## Red-Team Mode

When triggered with "red-team" or "adversarial":

- Think like an attacker
- Focus on: input validation, auth boundaries, resource limits
- Try to break assumptions
- Document vulnerabilities as test cases

## Scope Confirmation

Before starting:

- Which test directory/module?
- Fix gaps or report only?
- Commit after each fix?

## Completion Criteria

Done when:

- All tests compile
- All tests pass
- No CRITICAL/HIGH gaps remain (or explicitly deferred)
