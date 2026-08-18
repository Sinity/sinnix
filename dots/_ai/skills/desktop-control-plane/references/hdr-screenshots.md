# HDR Screenshot Notes

## Current Situation (verified 2026-08-05, Hyprland 0.55.4)

Direct `grim` screencopy of the HDR-mode output (DP-3, monitorv2 `cm = hdr`,
10-bit) is intermittent. It can return a nearly black PNG even when the desktop
is rendered normally. One reproduced 3840x2160 frame had mean channel value
0.000006 and only 47 colors. A temporary sRGB monitor switch recovered capture
but visibly dropped the display signal, so it is not an acceptable workflow.

Noctalia v5 provides native region and output capture through Wayland
screencopy. The Print bindings call its IPC directly. Noctalia saves into
`/realm/data/activity/screenshot` and copies the encoded PNG to the clipboard.
Region capture does not freeze the whole output first because frozen full
output capture is one of the reported Hyprland 0.55 HDR failure paths.

Hyprland is configured with `render:keep_unmodified_copy = 1` so an SDR frame
is always retained for screencopy. `render:use_shader_blur_blend = true` keeps
inactive-window background blur on the retained-copy HDR composition path.
Neither setting changes output mode, bit depth, refresh rate, or HDR metadata.

Observed local context:

- Host config explicitly sets monitor HDR mode in `hosts/sinnix-prime/display.nix`.
- Hyprland monitor state reports HDR preset and XBGR2101010 format.
- A native Noctalia output capture produced a 3840x2160, 6.65 MB PNG with
  74,760 colors and copied the same frame to the clipboard.
- Three forced wallpaper replacements produced healthy direct HDR frames while
  preserving the complete monitored output state.

## Upstream Signals

- Hyprland discussion around washed-out screenshots in HDR sessions (ongoing / not fully resolved):
  - https://github.com/hyprwm/Hyprland/discussions/11824
- Hyprland 0.55 empty, stale, and transparent HDR capture reports:
  - https://github.com/hyprwm/Hyprland/discussions/14931
- Hyprland render-variable reference:
  - https://wiki.hypr.land/Configuring/Basics/Variables/

## Practical Workaround Strategy

1. Use Noctalia's native screenshot IPC for ordinary capture.
2. Use `sinnix-screenshot-control capture-output` for diagnostics and raw A/B captures.
3. Generate corrected sidecars only for non-black captures with color errors.

This skill's `screenshot-color-lab.sh` automates this approach.
