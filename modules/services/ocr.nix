# OCR / document understanding — on-demand, containerized.
#
# Uses marker-api: a FastAPI server wrapping datalab's `marker` (PDF→markdown,
# built on the Surya OCR/layout models), GPU-accelerated. Digest-pinned default
# below; override `image` (e.g. a GOT-OCR2 / PaddleOCR image) as desired.
# Surya/marker weights persist under model/ocr.
{
  mkServiceModule,
  lib,
  pkgs,
  helpers,
  ...
}@args:
mkServiceModule {
  name = "ocr";
  description = "OCR / document understanding (containerized, CDI GPU)";
  surface = {
    unit = "podman-ocr.service";
    resourceClass = "interactive-agent";
    activation = {
      mode = "socket-proxy";
      publicEndpoint = "127.0.0.1:${toString helpers.data.ports.ocr.public}";
      backendEndpoint = "127.0.0.1:${toString helpers.data.ports.ocr.backend}";
      idleTimeout = "300s";
      exclusiveResource = "gpu-inference";
      dependsOn = [ "ocr-proxy" ];
    };
    observe = {
      enable = true;
      restartable = true;
    };
  };
  extraOptions = {
    image = args.lib.mkOption {
      type = args.lib.types.str;
      default = "docker.io/savatar101/marker-api@sha256:5c5660cd0c38309630bbb96c15dafdc2a382143c8bfc5dac8ca1760f97ba84de";
      description = "Digest-pinned OCR image (default: marker-api / Surya). Re-resolve via skopeo inspect to update.";
    };
    port = args.lib.mkOption {
      type = args.lib.types.port;
      default = helpers.data.ports.ocr.public;
      description = "PUBLIC host port (bound to 127.0.0.1) clients use -- the ocr-proxy socket front door.";
    };
    backendPort = args.lib.mkOption {
      type = args.lib.types.port;
      default = helpers.data.ports.ocr.backend;
      description = "PRIVATE host port the container itself publishes to; ocr-proxy forwards here.";
    };
    containerPort = args.lib.mkOption {
      type = args.lib.types.port;
      default = 8080; # marker-api default
      description = "Port the chosen image listens on inside the container.";
    };
  };
  configFn =
    {
      cfg,
      config,
      ...
    }:
    let
      user = config.sinnix.user.name;
      dir = "${config.sinnix.paths.modelsRoot}/ocr";
    in
    {
      sinnix.ml.containerRuntime.enable = true;

      systemd.tmpfiles.rules = [ "d ${dir} 0755 ${user} users -" ];

      virtualisation.oci-containers.containers.ocr = {
        inherit (cfg) image;
        autoStart = false;
        # Published on the PRIVATE backend port only -- clients always speak
        # to cfg.port via ocr-proxy (modules/services/ai-control.nix), never
        # to the container directly.
        ports = [ "127.0.0.1:${toString cfg.backendPort}:${toString cfg.containerPort}" ];
        volumes = [ "${dir}:/root/.cache/huggingface" ];
        extraOptions = [ "--device=nvidia.com/gpu=all" ];
      };

      # Bound to the socket proxy's lifecycle: an idle proxy exit tears down
      # this container's cgroup. Conflicts= against every other GPU-inference
      # backend is computed centrally in ai-control.nix's
      # gpuInferenceConflicts.
      systemd.services.podman-ocr = {
        partOf = [ "ocr-proxy.service" ];
      };
    };
} args
