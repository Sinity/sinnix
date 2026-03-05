---
name: kitty-codex-exec-tabs
description: Launch multiple codex exec sessions in separate Kitty tabs from prompt files, create per-agent logs, and optionally generate a launcher script.
metadata:
  short-description: Multi-tab codex exec launcher for Kitty
---

# Kitty Codex Exec Tabs

Use this skill when the user wants to split work across multiple Codex agents and run each agent
in its own Kitty tab using `codex exec` and prompt files.

## Preconditions

- Kitty is running and `kitty @` is available.
- `KITTY_LISTEN_ON` is set (Kitty normally sets this in its own environment).
- `codex` is on PATH.
- Prompt files exist (for example, `docs/exploration/AgentA.prompt`).

## Workflow

1. Verify Kitty control is reachable:
   - `command -v kitty`
   - `echo $KITTY_LISTEN_ON`
   - If empty, instruct user to run inside Kitty or set `KITTY_LISTEN_ON`.

2. Ensure prompt and log files exist:
   - Prompt files: `docs/exploration/<Agent>.prompt` (or user-specified dir).
   - Log files: `docs/exploration/<Agent>.md` (append-only).

3. Launch tabs using the script in `scripts/launch_codex_tabs.sh`.

## Script

Use `scripts/launch_codex_tabs.sh` to open one tab per agent.

Example:

```
./scripts/launch_codex_tabs.sh /realm/project/sinex docs/exploration AgentA AgentB AgentC
```

This launches each agent with:

```
codex exec -C /realm/project/sinex "$(cat docs/exploration/AgentX.prompt)"
```

## Notes

- Keep prompts short and reference files by path instead of pasting large content.
- If a prompt needs file context, point the agent to read it from disk.
- Use small delays between tab launches to avoid race conditions.
