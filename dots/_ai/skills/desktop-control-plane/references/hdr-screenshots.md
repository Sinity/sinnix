# HDR Screenshot Notes

## Current Situation (verified 2026-08-02, Hyprland 0.55.4)

With `render:cm_enabled = false` (the current sinnix-prime state), direct
`grim` screencopy of the HDR-mode output (DP-3, monitorv2 `cm = hdr`,
10-bit) yields correct sRGB frames — no washout, no black frames. The
`hdr-screenshot` script therefore captures directly with no monitor
reconfiguration. Its earlier SDR-switch workaround (`hyprctl keyword
monitor ...cm,srgb` + `hyprctl reload` restore) caused visible output
blanking on every capture and raced when two captures overlapped
(double selection prompt, one washed-out frame); it was removed.

Washout/black-frame breakage returns when Hyprland's CM pipeline is
active during screencopy (upstream: discussions 11824, 14931 — 0.55
regressions). If `render:cm_enabled` is ever turned on, re-test
`hdr-screenshot output` before trusting captures.

Observed local context:

- Host config explicitly sets monitor HDR mode in `hosts/sinnix-prime/display.nix`.
- Hyprland monitor state reports HDR preset.

## Upstream Signals

- Hyprland discussion around washed-out screenshots in HDR sessions (ongoing / not fully resolved):
  - https://github.com/hyprwm/Hyprland/discussions/11824
- Related tone-mapping issue reference from that discussion:
  - https://github.com/hyprwm/Hyprland/issues/11341

## Practical Workaround Strategy

1. Always keep raw captures.
2. Generate corrected sidecar images with deterministic transforms (brightness/saturation/gamma).
3. Tune correction values incrementally for your display/workflow.

This skill's `screenshot-color-lab.sh` automates this approach.
