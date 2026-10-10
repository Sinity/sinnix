# Shared container runtime for ML services.
#
# ComfyUI / OpenedAI-Speech / MusicGen / OCR / Kokoro are absent from nixpkgs
# (fragile Python ML closures), so they run as digest-pinned OCI containers.
# Kokoro is CPU-only and skips GPU passthrough; the rest use CDI GPU
# passthrough. The AI service factory enables the shared Podman runtime for
# container backends. NVIDIA CDI is enabled only when an enabled container
# surface declares that it requires CUDA.
#
# The storage graphroot lives with managed service state on /realm.
{
  config,
  lib,
  ...
}:
let
  cfg = config.sinnix.ml.containerRuntime;
  containersRoot = "${config.sinnix.paths.stateRoot}/containers";
  needsCuda = lib.any (
    surface: surface.ai != null && surface.ai.backendKind == "container" && surface.ai.requiresCuda
  ) (lib.attrValues config.sinnix.runtime.surfaces);
in
{
  options.sinnix.ml.containerRuntime.enable =
    lib.mkEnableOption "shared Podman container runtime for local-AI services";

  config = lib.mkIf cfg.enable {
    virtualisation.podman = {
      enable = true;
      dockerCompat = false;
    };
    virtualisation.oci-containers.backend = "podman";

    # Keep OCI layers under the declared service-state root.
    virtualisation.containers.storage.settings.storage = {
      driver = "overlay";
      graphroot = containersRoot;
      runroot = "/run/containers/storage";
    };

    # GPU containers consume this CDI spec as `--device=nvidia.com/gpu=all`.
    # CPU-only containers have no NVIDIA driver dependency.
    hardware.nvidia-container-toolkit.enable = lib.mkIf needsCuda true;

    systemd.tmpfiles.rules = [
      "d ${containersRoot} 0711 root root -"
    ];
  };
}
