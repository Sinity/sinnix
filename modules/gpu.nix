# GPU mode option — single toggle controlling the full driver stack.
#
# Set in host config; consumed by hosts/sinnix-prime/{display,boot}.nix.
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
