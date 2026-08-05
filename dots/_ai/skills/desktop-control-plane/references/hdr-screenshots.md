# HDR Screenshot Notes

## Current Situation (verified 2026-08-05, Hyprland 0.55.4)

Direct `grim` screencopy of the HDR-mode output (DP-3, monitorv2 `cm = hdr`,
10-bit) is not reliable. It briefly produced correct sRGB frames on 2026-08-02,
then regressed in the same compositor session on 2026-08-05 to almost entirely
black PNGs. A reproduced 3840x2160 frame had mean channel value 0.000006 and
only 47 colors. Setting `render:cm_enabled = false` at runtime did not recover
the existing output's screencopy state.

`hdr-screenshot` therefore switches the focused HDR output to 8-bit sRGB for
the capture and reloads the configured monitorv2 rule afterward. Area
selection happens before the modeset, and a lock prevents concurrent captures
from racing over the shared monitor state. The modeset can blank the display
briefly, but it produced a correct frame in the reproduced failure state and
restored HDR, 10-bit format, brightness, and luminance values exactly.

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
2. Use the temporary sRGB output switch when a usable screenshot is required.
3. Generate corrected sidecars only for non-black HDR captures with color errors.

This skill's `screenshot-color-lab.sh` automates this approach.
