# Shared GPU container runtime for ML services.
#
# ComfyUI / OpenedAI-Speech / MusicGen / OCR are absent from nixpkgs (fragile
# Python ML closures), so they run as digest-pinned OCI containers with CDI GPU
# passthrough. Each of those service modules turns on
# `sinnix.ml.containerRuntime.enable`, and this module configures podman + the
# NVIDIA container toolkit exactly once.
#
# Storage graphroot lives on /realm (NVMe data lake), not the wear-limited root
# SSD — container images are multi-GB.
{
  config,
  lib,
  ...
}:
let
  cfg = config.sinnix.ml.containerRuntime;
  containersRoot = "${config.sinnix.paths.stateRoot}/containers";
in
{
  options.sinnix.ml.containerRuntime.enable =
    lib.mkEnableOption "shared GPU container runtime (podman + NVIDIA CDI) for local-AI services";

  config = lib.mkIf cfg.enable {
    virtualisation.podman = {
      enable = true;
      dockerCompat = false;
    };
    virtualisation.oci-containers.backend = "podman";

    # Keep multi-GB ML images off the root SSD wear budget.
    virtualisation.containers.storage.settings.storage = {
      driver = "overlay";
      graphroot = containersRoot;
      runroot = "/run/containers/storage";
    };

    # Generates the CDI spec consumed as `--device=nvidia.com/gpu=all`. Requires
    # the proprietary NVIDIA driver, which sinnix-prime already loads.
    hardware.nvidia-container-toolkit.enable = true;

    systemd.tmpfiles.rules = [
      "d ${containersRoot} 0711 root root -"
    ];
  };
}
