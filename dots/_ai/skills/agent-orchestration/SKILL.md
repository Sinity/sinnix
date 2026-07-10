---
name: agent-orchestration
description: >
  Orchestrate AI coding agents through direct local runtimes, native background
  sessions, Codex Cloud, or visible Kitty terminals. Use when coordinating
  multiple agent tasks, preserving task handles and logs, or choosing an
  unattended versus operator-visible execution lane.
metadata:
  short-description: Local, cloud, and terminal agent orchestration
---

# Agent Orchestration

Prefer native non-interactive runtimes for unattended work. Use Kitty only when
an operator needs a visible, interruptible prompt run. Read
[`references/runtime-modes.md`](references/runtime-modes.md) before launching;
it contains the verified commands, auth rules, and mode constraints.

## Workflow

1. Choose direct local exec, a native background agent, Codex Cloud, or Kitty.
2. Set the working directory explicitly and preserve the returned session/task
   handle plus output artifacts.
3. Set model and effort explicitly when the lane supports them.
4. Use bounded concurrency for prompt batches; do not start unbounded workers.
5. Inspect results and diffs before applying or merging agent work.

## Helpers

- `scripts/run_agent_prompt.sh` runs one prompt through Claude, Codex, or
  Gemini and records its output.
- `scripts/launch_agent_tabs.sh` runs prompt batches directly or in Kitty,
  including bounded batch concurrency and optional workspace routing.
- `scripts/agent_instance_control.sh` discovers, captures, interrupts, or sends
  commands to existing Kitty terminals.
- `scripts/build_plan_batch_prompts.py` renders prompt files from plan JSON.
- `scripts/probe_agent_runtime.sh` and `scripts/probe_host_control_plane.sh`
  check runtime and terminal-control availability.

Use `desktop-control-plane` for browser, Hyprland, screenshot, and focus-safe
desktop control.
