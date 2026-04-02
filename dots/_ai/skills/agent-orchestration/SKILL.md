---
name: agent-orchestration
description: >
  Orchestrate AI coding agents (Claude, Codex, Gemini) at scale through Kitty
  terminal control. List instances, exec commands, batch prompts, launch tabs.
  Use when coordinating multiple agent sessions across projects.
metadata:
  short-description: Multi-agent terminal orchestration via Kitty
---

# Agent Orchestration

## Overview

Use this skill to run AI coding agents like an operations system, not ad hoc sessions.
It provides:

- instance discovery and control through Kitty remote,
- capability probing for agent runtimes,
- prompt generation from generic plan JSON batches,
- execution in either non-interactive batch mode or Kitty-remote interactive mode.

Supported agents: `claude` (via `claude --print`/exec), `codex` (exec mode), `gemini` (non-interactive).

If you need execution-lane tradeoffs and notes, read:

- `references/runtime-modes.md`
- `references/2026-03-19-local-first-coding-agent-sessions-in-sinnix.md`
- `references/2026-03-19-vocal-interface-possibilities-for-sinnix.md`

## When To Use

1. Verify agent runtime and Kitty remote-control availability.
2. Discover and control running agent terminal sessions.
3. Run many agent tasks from prompt files reproducibly.
4. Convert plan batches into prompt files and execute them consistently.

## Mode Selection

1. **In-session subagents** (preferred for local assistant coordination)
   - Use when tasks stay inside current thread/tooling.

2. **Batch exec mode**
   - Use when deterministic logs/artifacts matter most.
   - Best for overnight or unattended runs.
   - Use for explicit model control (e.g. `--model gpt-5.3-codex-spark`).

3. **Kitty-remote mode**
   - Use when you want live observability/interruption per agent.
   - Supports `--launch-type tab` or `--launch-type os-window`.

## Scripts

### 1) Instance Control

`scripts/agent_instance_control.sh`

Control running agent terminal instances through Kitty with high-level commands.

```bash
# Discover agent windows by title pattern
scripts/agent_instance_control.sh list
scripts/agent_instance_control.sh list --regex '[Cc]laude|[Cc]odex|[Gg]emini'

# Resolve your own terminal target
scripts/agent_instance_control.sh self --json

# Execute a command in a matched terminal and wait for completion sentinel
scripts/agent_instance_control.sh exec --match 'title:Codex' --command 'git status --short'

# Wait for a pattern in last command output
scripts/agent_instance_control.sh wait --match 'title:Claude' --pattern 'Done' --timeout-sec 120

# Run a batch of commands from a file
scripts/agent_instance_control.sh batch --match 'title:Codex' --file /tmp/cmds.txt

# Interrupt or close a target
scripts/agent_instance_control.sh kill --self --mode interrupt
```

### 2) Runtime Probing

`scripts/probe_agent_runtime.sh`

Probe agent binary availability, Kitty remote control, and optional model probe.

```bash
# Quick probe
scripts/probe_agent_runtime.sh

# Probe with Codex Spark model test
scripts/probe_agent_runtime.sh --agent codex --probe-model --model gpt-5.3-codex-spark
```

`scripts/probe_host_control_plane.sh`

Full host control-plane probe (Kitty, Hyprland, tool availability).

```bash
scripts/probe_host_control_plane.sh
```

### 3) Batch Prompt Generation

`scripts/build_plan_batch_prompts.py`

Generate prompt files from a generic batch plan JSON.

```bash
python3 scripts/build_plan_batch_prompts.py \
  --plan-json /path/to/plan.json \
  --out-dir /path/to/prompts \
  --project-root /path/to/project \
  --item-label shards
```

### 4) Tab Launcher

`scripts/launch_agent_tabs.sh`

Launch multiple agent exec sessions in separate Kitty tabs from prompt files.

```bash
# Launch Codex agents
scripts/launch_agent_tabs.sh --agent codex --workdir /project --prompt-dir prompts --output-dir logs batch-01 batch-02

# Launch Claude agents with Kitty windows
scripts/launch_agent_tabs.sh --agent claude --workdir /project --prompt-dir prompts --output-dir logs --launch-type os-window task-a task-b

# Batch mode (no Kitty, direct exec)
scripts/launch_agent_tabs.sh --agent codex --mode batch --workdir /project --prompt-dir prompts --output-dir logs batch-01
```

## Notes

- Requires Kitty remote control for interactive modes (`KITTY_LISTEN_ON`).
- Instance control is agent-agnostic — it drives terminal windows, not agent APIs.
- For desktop/Hyprland/screenshot primitives, use `desktop-control-plane`.
