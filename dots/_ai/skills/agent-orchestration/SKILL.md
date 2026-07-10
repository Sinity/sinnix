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
2. For Codex, use `gpt-5.6-terra` with high reasoning for unattended execution
   lanes. Use `gpt-5.6-sol` with high reasoning for the coordinating interactive
   session unless the operator selects another tier. Never inherit or guess a
   stale model default; inspect the launch receipt.
3. Set the working directory explicitly and preserve the returned session/task
   handle plus output artifacts.
4. Set model and effort explicitly when the lane supports them.
5. Use bounded concurrency for prompt batches; do not start unbounded workers.
6. Make each worker verify its own behavior. Require focused real-route tests,
   exact-path static checks, and a broader affected-area check when the change
   crosses modules or contracts. Resource containment exists to make this
   affordable; do not export all verification cost to the coordinator.
7. Require an anti-vacuity statement in implementation prompts: the worker must
   say what production dependency the test enters and what implementation
   mutation/removal makes it fail. Reject toy replicas, test-only validators,
   self-authored registries, and mocks that merely surround themselves.
8. Inspect results and diffs independently before applying or merging agent
   work. Worker verification is necessary, not sufficient.

## Helpers

- `scripts/run_agent_prompt.sh` runs one prompt through Claude, Codex, or
  Gemini, records its output, and emits an attested manifest for each
  headless job. Use `--job-id`, `--job-role`, `--work-item`, and the narrow
  resource options when an operator needs a stable control handle.
- `scripts/agent_job_control.sh` lists or refreshes a manifest and interrupts
  only by an attested job ID; it deliberately rejects PID, title, and window
  targeting.
- `scripts/launch_agent_tabs.sh` runs prompt batches directly or in Kitty,
  including bounded batch concurrency and optional workspace routing.
- `scripts/agent_instance_control.sh` discovers, captures, interrupts, or sends
  commands to existing Kitty terminals.
- `scripts/build_plan_batch_prompts.py` renders prompt files from plan JSON.
- `scripts/probe_agent_runtime.sh` and `scripts/probe_host_control_plane.sh`
  check runtime and terminal-control availability.

Use `desktop-control-plane` for browser, Hyprland, screenshot, and focus-safe
desktop control.
