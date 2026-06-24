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
  ...
}@args:
mkServiceModule {
  name = "ocr";
  description = "OCR / document understanding (containerized, CDI GPU)";
  surface = {
    unit = "podman-ocr.service";
    resourceClass = "interactive-agent";
    observe = {
      enable = true;
      restartable = true;
    };
  };
  extraOptions = {
    image = (
      args.lib.mkOption {
        type = args.lib.types.str;
        default = "docker.io/savatar101/marker-api@sha256:5c5660cd0c38309630bbb96c15dafdc2a382143c8bfc5dac8ca1760f97ba84de";
        description = "Digest-pinned OCR image (default: marker-api / Surya). Re-resolve via skopeo inspect to update.";
      }
    );
    port = (
      args.lib.mkOption {
        type = args.lib.types.port;
        default = 8020;
        description = "Host port (bound to 127.0.0.1) for the OCR API.";
      }
    );
    containerPort = (
      args.lib.mkOption {
        type = args.lib.types.port;
        default = 8080; # marker-api default
        description = "Port the chosen image listens on inside the container.";
      }
    );
  };
  configFn =
    {
      cfg,
      config,
      ...
    }:
    let
      user = config.sinnix.user.name;
      dir = "${config.sinnix.paths.librariesRoot}/model/ocr";
    in
    {
      sinnix.ml.containerRuntime.enable = true;

      systemd.tmpfiles.rules = [ "d ${dir} 0755 ${user} users -" ];

      virtualisation.oci-containers.containers.ocr = {
        image = cfg.image;
        autoStart = false;
        ports = [ "127.0.0.1:${toString cfg.port}:${toString cfg.containerPort}" ];
        volumes = [ "${dir}:/root/.cache/huggingface" ];
        extraOptions = [ "--device=nvidia.com/gpu=all" ];
      };
    };
} args
