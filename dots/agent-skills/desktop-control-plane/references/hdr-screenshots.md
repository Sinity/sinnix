# HDR Screenshot Notes

## Current Situation

On Hyprland HDR setups (`colorManagementPreset = hdr`, often 10-bit format like `XBGR2101010`), screenshots can appear washed out compared to on-screen output.

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
