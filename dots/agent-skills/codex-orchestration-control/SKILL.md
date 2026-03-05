---
name: codex-orchestration-control
description: "Operate Codex agents at scale with deterministic workflows: probe runtime capability, generate batch prompt files from plan JSON, and launch codex exec runs in batch or Kitty-controlled tabs/windows. Use when coordinating many Codex runs across any project."
metadata:
  short-description: Coordinate codex and Spark runs
---

# Codex Orchestration Control

## Overview

Use this skill to run Codex like an operations system, not ad hoc sessions.
It provides:
- capability probing,
- prompt generation from generic plan JSON batches,
- execution in either non-interactive batch mode or Kitty-remote interactive mode.

If you need execution-lane tradeoffs and Hyprland notes, read:
- `references/runtime-modes.md`
- `references/agent-vs-exec-decision.md`
- `references/codex-cli-notes.md`

## When To Use

Use this skill when you need one of:
1. verify whether Spark model and Kitty remote-control are available now,
2. run many codex tasks from prompt files reproducibly,
3. convert plan batches into prompt files and execute them consistently.

## Mode Selection

1. In-session subagents (preferred for local assistant coordination)
- Use when tasks stay inside current Codex thread/tooling.
- Note: if model selection is unavailable in the host tools, do not assume Spark can be forced here.

2. Batch `codex exec` mode
- Use when deterministic logs/artifacts matter most.
- Best for overnight or unattended runs.
- Use this mode when explicit model control is required (for example `--model gpt-5.3-codex-spark`).

3. Kitty-remote mode
- Use when you want live observability/interruption per agent.
- Supports `--launch-type tab` or `--launch-type os-window`.

## Workflow

1. Probe runtime and model access:
```bash
scripts/probe_codex_runtime.sh --probe-spark
```

Optional full host control-plane probe:
```bash
scripts/probe_host_control_plane.sh
```

2. Generate prompts from any plan JSON with a `batches` array:
```bash
python3 scripts/build_plan_batch_prompts.py \
  --plan-json /path/to/plan.json \
  --out-dir /path/to/prompts \
  --project-root /path/to/project \
  --item-label shards
```

3. Launch Codex runs from generated prompts (interactive):
```bash
scripts/launch_codex_from_prompts.sh \
  --workdir /path/to/project \
  --prompt-dir /path/to/prompts \
  --output-dir /path/to/run-logs \
  --mode kitty \
  --launch-type os-window \
  --spark \
  --xhigh \
  --ephemeral \
  --skip-agents-render \
  batch-01 batch-02
```

4. For fully unattended execution, switch to batch mode:
```bash
scripts/launch_codex_from_prompts.sh \
  --workdir /path/to/project \
  --prompt-dir /path/to/prompts \
  --output-dir /path/to/run-logs \
  --mode batch \
  --model gpt-5.3-codex \
  --ephemeral \
  --skip-agents-render \
  batch-01 batch-02
```

## Project Adapter Example (`_analysis`)

Use this when plan source is `/realm/project/_analysis/data/derived/spark_run_plan.json`:
```bash
python3 scripts/build_plan_batch_prompts.py \
  --plan-json /realm/project/_analysis/data/derived/spark_run_plan.json \
  --out-dir /realm/project/_analysis/docs/exploration/spark-batches \
  --project-root /realm/project/_analysis \
  --item-label shards \
  --name-prefix spark-batch
```

## Artifacts

Launch script writes per-agent files:
- `<agent>.log` (full CLI output),
- `<agent>.last.md` (last assistant message),
- optional `<agent>.jsonl` (if `--json` enabled).

Treat these as execution artifacts; summarize conclusions separately.
