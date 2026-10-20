---
name: desktop-control
description: "Control the operator's desktop: shared Chrome through CDP, Kitty remote input and capture, Hyprland windows and shortcuts, and HDR-safe screenshots."
---

# Desktop control

Use the installed `sinnix-*` shell helpers below. Their maintenance sources
live in `scripts/` beside this file; each command's `--help` lists its syntax.
Run `sinnix-observe` when you need a correlated host inventory. Hyprland
operations require a running compositor; Kitty needs remote control enabled.

## Shared Chrome

The browser is the operator's Chrome with the same signed-in profile. Start
with `status`; retry and inspect `list-tabs` before declaring it unavailable.
Prefer the shell CDP helper; use browser tools when it cannot express the task.

```bash
sinnix-chrome-control status
sinnix-chrome-control list-tabs
sinnix-chrome-control agent-window --url https://example.com
sinnix-chrome-control page-snapshot <page-id>
sinnix-chrome-control wait-selector <page-id> --selector 'main'
sinnix-chrome-control get-text <page-id>
```

Use `agent-window` for new agent work. It returns a page ID after the exact
new compositor window stays tiled, unpinned, non-fullscreen and invisible on
the named `agentbrowser` workspace, while the operator's focused client stays
unchanged. F7 lets the operator view that workspace.

- Own explicit page IDs. Other agents and the operator share the browser;
  leave their targets alone. Operate on an existing operator page only when
  the request concerns it.
- Keep work on background targets in your agent window. `new-tab --background`
  opens a tab without activating it. Use selectors rather than coordinates.
- Use `upload-files` for attachments; it needs no focus or native file picker.
- If an action depends on OS focus, inspect the focused Hyprland window
  immediately before sending input and verify focus afterward.
- CDP exchanges match request IDs within a bounded deadline (five seconds by
  default). A failed `agent-window` transaction closes only its created target.

```bash
sinnix-chrome-control inject-text <page-id> \
  --selector '[role="textbox"][contenteditable="true"]' \
  --text-file /path/to/prompt.txt
sinnix-chrome-control upload-files <page-id> \
  --selector 'input[type=file]' --file /path/to/context.md
```

For ChatGPT prompts, model selection, uploads and Deep Research, read
[ChatGPT browser work](references/chatgpt.md). Complete conversation reads
belong to [chatgpt-conversations](../chatgpt-conversations/SKILL.md).

## Kitty

Prefer Kitty remote input for terminal targets. `KITTY_LISTEN_ON` chooses a
socket; a non-interactive caller without it resolves the live `terminal`
instance before falling back to another live per-user Kitty socket.

```bash
sinnix-kitty-control list
sinnix-kitty-control send --match 'title:Codex' --text 'git status --short' --enter
sinnix-kitty-control capture --match 'title:Codex' --extent all \
  --out /realm/tmp/work/desktop-task/scrollback.txt
sinnix-kitty-control send-await --match 'title:Codex' \
  --text 'printf "TASK_DONE\\n"' --enter --pattern '^TASK_DONE$'
```

Create the task scratch directory before capturing. `send-await` defaults to
`--extent last_cmd_output`, so echoed input cannot satisfy its pattern. Match
a command's completion marker rather than waiting a fixed time.

## Hyprland

Inspect clients before choosing a selector. Targeted shortcuts avoid global
keyboard input; clipboard paste works best with native Wayland apps and is
best-effort with XWayland.

```bash
sinnix-hypr-control status
sinnix-hypr-control clients --grep 'Steam|obs|kitty'
sinnix-hypr-control binds --grep 'Print|grimblast|screenshot'
sinnix-hypr-control focus-window 'class:^(steam)$'
sinnix-hypr-control send-shortcut CTRL V 'class:^(steam)$'
sinnix-hypr-control paste 'class:^(steam)$' --text 'example text'
sinnix-hypr-control dispatch 'hl.dsp.focus({ workspace = 3 })'
```

`paste` restores text clipboard content only when a text clipboard existed
at command start. For Kitty and Hyprland directional focus, movement and
resize, reuse the installed `kitty-hypr-nav` helper.

## Screenshots

Probe color management before diagnosing washed-out HDR captures. Capture
commands preserve raw files and optionally create corrected sidecars.

```bash
sinnix-screenshot-control probe
sinnix-screenshot-control capture-output --fix-hdr
sinnix-screenshot-control capture-region --output DP-1 --fix-hdr
sinnix-screenshot-control tone-map --in /path/image.png \
  --brightness 105 --saturation 125 --gamma 0.90
```

`capture-region` selects a named output or supplied geometry without a
picker. `capture-area` opens an interactive picker. Corrections require
ImageMagick. See [HDR diagnostics](references/hdr-screenshots.md) for color
probes and [control recipes](references/control-recipes.md) for longer
terminal, paste and capture examples.
