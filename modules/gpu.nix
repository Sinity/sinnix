# GPU mode option — the single knob for switching between discrete NVIDIA GPU
# and integrated Intel iGPU (e.g. when the card is physically removed).
#
# Set in host config:
#   sinnix.gpu.discrete = false;   # iGPU mode (GPU absent)
#   sinnix.gpu.discrete = true;    # NVIDIA mode (default)
#
# Consumed by: hosts/sinnix-prime/display.nix, hosts/sinnix-prime/boot.nix
{ lib, ... }:
{
  options.sinnix.gpu.discrete = lib.mkOption {
    type = lib.types.bool;
    default = true;
    description = ''
      Whether the discrete NVIDIA GPU is physically installed.
      false → Intel iGPU mode: i915 loaded, NVIDIA drivers/vars suppressed.
      true  → NVIDIA mode: i915 blacklisted, full NVIDIA driver stack active.
    '';
  };
}
