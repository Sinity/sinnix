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

### 1) Kitty Remote Control

`scripts/kitty-remote-control.sh`

Examples:

```bash
# List windows
scripts/kitty-remote-control.sh list

# Send command to matching window and press Enter
scripts/kitty-remote-control.sh send --match 'title:Codex' --text 'git status --short' --enter

# Capture scrollback to file
scripts/kitty-remote-control.sh capture --match 'title:Codex' --extent all --out /tmp/codex-scrollback.txt

# Wait until terminal output contains a pattern
scripts/kitty-remote-control.sh await --match 'title:Codex' --pattern 'finished|done' --timeout-sec 90

# Send command and wait for sentinel output
scripts/kitty-remote-control.sh send-await --match 'title:Codex' --text 'echo TASK_DONE' --enter --pattern 'TASK_DONE'
```

### 2) Hyprland Control

`scripts/hypr-control.sh`

Examples:

```bash
# Current focused monitor/window/workspace + color management
scripts/hypr-control.sh status

# Find screenshot-related keybinds
scripts/hypr-control.sh binds --grep 'Print|grimblast|screenshot'

# Enumerate candidate windows before targeting one
scripts/hypr-control.sh clients --grep 'Steam|obs|kitty'

# Focus a specific window using a Hyprland selector
scripts/hypr-control.sh focus-window 'class:^(steam)$'

# Send a shortcut to a specific app
scripts/hypr-control.sh send-shortcut CTRL V 'class:^(steam)$'

# Paste text into a paste-aware GUI app and optionally press Enter
scripts/hypr-control.sh paste 'class:^(steam)$' --text 'download_depot 427520 427523 3610450483505928345' --enter

# Dispatch any Hyprland action
scripts/hypr-control.sh dispatch workspace 3
```

### 3) Screenshot Color Lab (HDR)

`scripts/screenshot-color-lab.sh`

Examples:

```bash
# Probe HDR state and tool availability
scripts/screenshot-color-lab.sh probe

# Capture focused output with raw files + corrected sidecars
scripts/screenshot-color-lab.sh capture-output --fix-hdr

# Apply manual correction to a file
scripts/screenshot-color-lab.sh tone-map --in /path/image.png --brightness 105 --saturation 125 --gamma 0.90
```

## Notes

- On some HDR Hyprland setups, native captures may look washed out due unresolved compositor/tonemapping behavior.
- This skill keeps raw captures intact and generates optional corrected sidecars rather than destructive replacement.
- Prefer `kitty-remote-control` for keyboard/text injection into terminal processes; global keyboard/mouse injection requires separate tools (`wtype`/`ydotool`) not assumed here.
- `hypr-control.sh paste` closes part of that gap for GUI apps by using clipboard plus Hyprland `sendshortcut`; it is reliable for native Wayland clients and best-effort for XWayland clients.
- `hypr-control.sh paste` restores only text clipboard content, and only if a text clipboard existed when the command started.
- For deterministic automation loops, prefer `send-await` over blind sleeps.
- `send-await` defaults to `--extent last_cmd_output` to avoid false positives from echoed input.
- For window layout/navigation primitives, reuse existing system scripts in `/realm/project/sinnix/scripts`:
  - `kitty-grid` for deterministic grid placement
  - `kitty-hypr-nav` for directional focus/move/resize fallback between Kitty and Hyprland
- For ready-made automation examples, see `references/control-recipes.md`.
