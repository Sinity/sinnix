# Agent vs Exec Decision

## Summary

Use a hybrid strategy:
1. in-session agents for tight local collaboration,
2. external `codex exec` for explicit model-controlled fanout (Spark and beyond).

## Why

In some host environments, in-session `spawn_agent` APIs do not expose a model selector.
When model is non-negotiable (for example Spark throughput experiments), prefer `codex exec --model ...`.

## Decision Table

1. Need explicit model (`gpt-5.3-codex-spark`)?
- Use `codex exec` workflow.

2. Need strict machine output contracts (`--output-schema`)?
- Prefer `codex exec` workflow.

3. Need fast iterative collaboration in one thread with shared context?
- Use in-session subagents.

4. Need live observability and manual steering per worker window?
- Use Kitty mode (`--mode kitty`, `--launch-type os-window`).

5. Need unattended repeatable run with stable artifacts?
- Use batch mode (`--mode batch`) and capture logs/jsonl.

## Recommended Default

1. Pilot: one batch with `codex exec --model gpt-5.3-codex-spark --xhigh`.
2. Validate deltas and invariants.
3. Scale fanout only after pilot quality gate passes.
