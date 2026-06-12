---
name: greedy-batching
description: |
  Use when implementing any non-trivial change (multi-file refactor, feature
  implementation, bug fix spanning >1 module). Forces plan-then-batch-implement
  -then-verify-once, instead of detail-by-detail edit-and-test cycles that
  burn compile/test budget.
---

# Greedy Batching

Rigid protocol. Do not negotiate with yourself.

1. **Manifest first.** Before any `Edit` / `Write` / `NotebookEdit` tool call, emit the full **change manifest** as TodoWrite entries: every file, every function, every test, every config touched. One TodoWrite per atomic edit. No exceptions for "small" changes — small changes are how loops start.
2. **Order by dependency.** Types/schemas → implementations → call-sites → tests. Reorder the manifest accordingly before executing.
3. **Apply in batched tool-call blocks.** Parallel `Edit` calls where files are independent. **Do NOT run any `cargo check` / `pytest` / `xtask` / `just` between edits.** Compile output between edits is noise; the manifest is the plan.
4. **Narrow verify once, after the full batch.** A single command that exercises the changed surface: `cargo nextest run -p <crate> <filter>`, `pytest <file>::<test>`, `xtask test <area>`, `just <focused-recipe>`.
5. **On failure: batch the fixes.** Diagnose against the manifest, gather every needed fix, apply them together, re-verify once. Never one-fix-at-a-time. If three rounds of fix-batches don't converge, you misread the problem — stop and re-plan.
6. **Broad gate at commit boundary only.** `xtask check` / full suite runs once, when narrow passes and before commit. Not earlier.
7. **New scope mid-batch → manifest growth.** Add TodoWrite entries and continue executing. Do not branch into a verify-loop just because scope grew.
8. **Tripwire.** If you've run `cargo check` / `pytest` / `xtask` more than **3 times** for one logical change, the approach has already failed. Abort, re-plan, restart.

## Why

Compile and test wall-time dominates agent throughput on Rust/Python projects. Reactive verification after each edit makes cost linear in edits (`O(N·t_verify)`); batched verification keeps it constant (`O(t_verify)`). Manifest-first planning also surfaces dependency order, which catches half the would-have-been compile errors at planning time instead of paying for them in test runs. The user's CLAUDE.md already encodes this in §4 (Batch edits) and §21 (Throughput stewardship) — this skill makes the rule executable rather than aspirational.

## Measurement

Tracked by the `verify_vs_edit_ratio` lynchpin MCP tool, which computes `verify_calls / edit_calls` per session from polylogue work events.

**Targets**:

- Refactors: ratio < 0.3
- New features: ratio < 0.5
- Bug fixes spanning >1 file: ratio < 0.7

Higher ratios mean reactive verification — re-read this skill and try again on the next session.
