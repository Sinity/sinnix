---
name: test-suite-modernization
description: Analyze a Rust test suite holistically, map boundaries, identify flake/perf risks, and produce a modernization plan with gating and harness upgrades.
metadata:
  short-description: Test suite modernization analysis + plan
---

# Test Suite Modernization

Use this skill when the user asks for deep analysis and planning around refactoring or
modernizing a large Rust test suite (especially with pipeline + DB + message bus layers).

## Core workflow

1. Read repo instructions and the current plan docs.
   - `AGENTS.md`
   - `docs/exploration/plan.md`
   - `docs/exploration/harness-design.md`
   - `docs/exploration/test-suite-modernization-table.md`

2. Build or update a **semantic coverage map**.
   - Focus on what the suite proves today (invariants, pipeline correctness, recovery,
     system behavior).
   - Use representative test names; avoid file-name-only summaries.

3. Normalize **boundary labels** by dependency (not directory).
   - L0: pure logic (no DB/NATS/filesystem)
   - L1: DB/repository invariants
   - L2: pipeline ingestion (NATS/JetStream/ingestd)
   - L3: services over pipeline data
   - L4: system lifecycle/chaos/recovery/perf

4. Identify **self-healing patterns** and remove them.
   - Backfill, top-up, reseed, trim, post-hoc deletes.
   - Replace with explicit preconditions + deterministic waits.

5. Identify **sleep/timeout risks** and consolidate wait helpers.
   - Replace fixed sleeps with wait-for conditions aligned with production queries.
   - Centralize waits in test-utils.

6. Decide **profile gating** for heavy suites.
   - Perf, stress/chaos, and external-binary profiles.
   - Keep default `reliable` fast and deterministic.

7. Produce a concrete plan with track ownership and file scopes.
   - Each track edits a disjoint set of files.
   - Require per-agent append-only logs.

## Commands to gather evidence

- List tests: `rg --files -g 'tests/**/*.rs' -g 'crate/**/tests/**/*.rs'`
- Find sleeps/timeouts: `rg -n "sleep|timeout" crate tests`
- Find backfill/repair: `rg -n "backfill|top up|reseed|repair|trim|truncate" crate tests`

## Output artifacts

- Update `docs/exploration/test-suite-modernization-table.md` (dense, semantic rows).
- Update `docs/exploration/harness-design.md` to align with the plan and boundaries.
- Update `docs/exploration/plan.md` with track readiness and gating decisions.

## Guardrails

- Do not add `#[ignore]` or per-test env gating.
- Avoid adding new “diagnostic helper layers” when errors already carry context.
- Keep ASCII-only edits and avoid auto-format commands unless required.
