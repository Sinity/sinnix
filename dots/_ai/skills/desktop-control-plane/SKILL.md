---
name: desktop-control-plane
description: "Control desktop/runtime surfaces for operator workflows: Kitty remote I/O, Hyprland dispatch/inspection, and screenshot diagnostics/workarounds (including HDR washout handling). Use when coding agents need reliable computer-use primitives on Linux Wayland/Hyprland systems."
metadata:
  short-description: Desktop control and automation toolkit
---

# Desktop Control Plane

## Overview

Use this skill when you need repeatable machine-control primitives for desktop workflows.
This skill provides:

1. Kitty remote-control I/O (list windows, send input, capture output),
2. Hyprland control wrapper (status, window inventory, focus, shortcut dispatch, clipboard-backed paste, keyword, batch),
3. Screenshot diagnostics and HDR washout workaround flow.

## Preconditions

- Hyprland session running (`hyprctl` available).
- Kitty running with remote control enabled (`KITTY_LISTEN_ON` preferred).
- Optional: `magick` for screenshot correction sidecars.

## Scripts

The scripts are installed on Sinnix as stable `~/.local/bin/sinnix-*` commands
for ambient use by agents. The source files below remain the maintenance copy.
Run `sinnix-observe` first when you need a correlated runtime inventory. Use
the individual control helpers below to probe browser and desktop availability.
For browser work, use `sinnix-chrome-control` — one browser, the operator's own.
Use the browser MCP profile (`claude-browser`/`codex-browser`) only when the
shell CDP helper is too small for the task.

### 1) Kitty Remote Control

Installed command: `sinnix-kitty-control`

Source: `scripts/kitty-remote-control.sh`

Examples:

```bash
# List windows
sinnix-kitty-control list

# Send command to matching window and press Enter
sinnix-kitty-control send --match 'title:Codex' --text 'git status --short' --enter

# Capture scrollback to file
sinnix-kitty-control capture --match 'title:Codex' --extent all --out /tmp/codex-scrollback.txt

# Wait until terminal output contains a pattern
sinnix-kitty-control await --match 'title:Codex' --pattern 'finished|done' --timeout-sec 90

# Send command and wait for sentinel output
sinnix-kitty-control send-await --match 'title:Codex' --text 'echo TASK_DONE' --enter --pattern 'TASK_DONE'
```

### 2) Hyprland Control

Installed command: `sinnix-hypr-control`

Source: `scripts/hypr-control.sh`

Examples:

```bash
# Current focused monitor/window/workspace + color management
sinnix-hypr-control status

# Find screenshot-related keybinds
sinnix-hypr-control binds --grep 'Print|grimblast|screenshot'

# Enumerate candidate windows before targeting one
sinnix-hypr-control clients --grep 'Steam|obs|kitty'

# Focus a specific window using a Hyprland selector
sinnix-hypr-control focus-window 'class:^(steam)$'

# Send a shortcut to a specific app
sinnix-hypr-control send-shortcut CTRL V 'class:^(steam)$'

# Paste text into a paste-aware GUI app and optionally press Enter
sinnix-hypr-control paste 'class:^(steam)$' --text 'download_depot 427520 427523 3610450483505928345' --enter

# Dispatch any Hyprland action
sinnix-hypr-control dispatch workspace 3
```

### 3) Screenshot Color Lab (HDR)

Installed command: `sinnix-screenshot-control`

Source: `scripts/screenshot-color-lab.sh`

Examples:

```bash
# Probe HDR state and tool availability
sinnix-screenshot-control probe

# Capture focused output with raw files + corrected sidecars
sinnix-screenshot-control capture-output --fix-hdr

# Apply manual correction to a file
sinnix-screenshot-control tone-map --in /path/image.png --brightness 105 --saturation 125 --gamma 0.90
```

### 4) Browser Control

Installed command: `sinnix-chrome-control`

Source: `scripts/chrome-control.sh`

Examples:

```bash
# Probe the browser (the operator's own Chrome; there is no second one)
sinnix-chrome-control status

# Open an agent window on the inactive named agentbrowser workspace. Prints its page id.
# Authenticated exactly where the operator is, because it IS his profile.
# Each request waits for its matching CDP response within a bounded deadline;
# nonmatching protocol messages are retained on stderr for diagnosis.
sinnix-chrome-control agent-window --url https://example.com

# See everything open, the operator's tabs included
sinnix-chrome-control list-tabs

# Wait for an element and read page text
sinnix-chrome-control wait-selector <page_id> --selector 'main'
sinnix-chrome-control get-text <page_id>

# Attach local context without a file-picker dialog
sinnix-chrome-control upload-files <page_id> \
  --selector 'input[type=file]' --file /path/to/context.md
```

### Browser Focus Safety

- Prefer the browser CLI or CDP API over visible UI automation.
- Treat the browser as shared across concurrent agents AND the operator. Own explicit page
  target IDs and keep work on background CDP targets.
- Use `new-tab --background` for new work and `upload-files` for attachments;
  neither requires activating a tab or opening a native file picker.
- Never activate another agent's target. Avoid coordinate clicks; address a
  known page target and selector instead.
- When an operation genuinely depends on OS focus, inspect Hyprland's focused
  window immediately before sending input and verify focus again afterward.
- Use `agent-window` for all agent work; it parks on the hidden workspace, and
  F7 is how the operator looks at it. Operate on his existing pages only when
  he asked for that specific thing — the profile is shared, so a stray
  navigation lands in his session, not a sandbox.
- `agent-window` returns only after the exact new compositor address has stayed
  tiled, unpinned, non-fullscreen, and invisible on `agentbrowser` while the
  focused operator client remains unchanged. CDP command responses use positive
  signed-32-bit request IDs, are matched with a five-second default deadline,
  and a failed transaction closes only its own created target.

## Notes

- On some HDR Hyprland setups, native captures may look washed out due unresolved compositor/tonemapping behavior.
- This skill keeps raw captures intact and generates optional corrected sidecars rather than destructive replacement.
- Prefer `kitty-remote-control` for keyboard/text injection into terminal processes; global keyboard/mouse injection requires separate tools (`wtype`/`ydotool`) not assumed here.
- `hypr-control.sh paste` closes part of that gap for GUI apps by using clipboard plus Hyprland `sendshortcut`; it is reliable for native Wayland clients and best-effort for XWayland clients.
- `hypr-control.sh paste` restores only text clipboard content, and only if a text clipboard existed when the command started.
- For deterministic automation loops, prefer `send-await` over blind sleeps.
- A non-interactive caller without `KITTY_LISTEN_ON` resolves the live `terminal` instance socket before falling back to another live per-user Kitty socket. This keeps remote control working from systemd and MCP processes that have no controlling TTY.
- `send-await` defaults to `--extent last_cmd_output` to avoid false positives from echoed input.
- For window layout/navigation primitives, reuse existing system scripts in `/realm/project/sinnix/scripts`:
  - `kitty-grid` for deterministic grid placement
  - `kitty-hypr-nav` for directional focus/move/resize between Kitty and Hyprland
- For ready-made automation examples, see `references/control-recipes.md`.
