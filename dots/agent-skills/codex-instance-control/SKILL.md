---
name: codex-instance-control
description: Control running Codex terminal instances through Kitty with high-level commands (list, exec, wait, batch). Use when you need fast interactive steering of active Codex windows.
metadata:
  short-description: High-level Codex window driver
---

# Codex Instance Control

Use this skill when you want to drive active Codex sessions quickly through Kitty remote control.

## Script

`scripts/codex_instance_control.sh`

## Examples

```bash
# Discover likely Codex windows by title
scripts/codex_instance_control.sh list

# Resolve your own terminal target (uses KITTY_WINDOW_ID first)
scripts/codex_instance_control.sh self --json

# Execute a command in a matched Codex terminal and wait for completion sentinel
scripts/codex_instance_control.sh exec --match 'title:Codex' --command 'git status --short'

# Execute in your own terminal without explicit match
scripts/codex_instance_control.sh exec --self --command 'git status --short'

# Wait for an arbitrary regex in last command output
scripts/codex_instance_control.sh wait --match 'title:Codex' --pattern 'Validation OK' --timeout-sec 120

# Run a batch of commands from a file
scripts/codex_instance_control.sh batch --match 'title:Codex' --file /tmp/codex_cmds.txt

# Stop a target: Ctrl+C or close window
scripts/codex_instance_control.sh kill --self --mode interrupt
scripts/codex_instance_control.sh kill --match 'title:Codex' --mode close
```

## Notes

- Requires Kitty remote control (`KITTY_LISTEN_ON` or explicit `--to` socket).
- This is optimized for terminal shells hosting Codex; it does not require Codex-specific APIs.
- For low-level keyboard/screenshot/Hyprland operations, use `desktop-control-plane`.
