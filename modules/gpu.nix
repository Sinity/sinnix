# GPU mode option — single toggle controlling the full driver stack.
#
# Set in host config (hosts/sinnix-prime/default.nix):
#   sinnix.gpu.mode = "nvidia";       # Proprietary driver
#   sinnix.gpu.mode = "nvidia-open";  # NVIDIA open kernel module
#   sinnix.gpu.mode = "igpu";         # Intel UHD 770, discrete GPU physically absent
#
# Consumed by: hosts/sinnix-prime/display.nix, hosts/sinnix-prime/boot.nix
{
  lib,
  ...
}:
{
  options.sinnix.gpu = {
    mode = lib.mkOption {
      type = lib.types.enum [
        "nvidia"
        "nvidia-open"
        "igpu"
        "dual"
      ];
      default = "nvidia";
      description = ''
        GPU driver mode for sinnix-prime.
          "nvidia"      — proprietary kernel module
          "nvidia-open" — NVIDIA open kernel module
          "igpu"        — Intel UHD 770, used when discrete GPU is physically absent
          "dual"        — Both Intel iGPU (i915) and NVIDIA active; either mobo or dGPU port works
      '';
    };
  };
}
