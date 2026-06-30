# MusicGen text-to-music (+ Bark, Tortoise, …) — on-demand, containerized.
#
# audiocraft is absent from nixpkgs; this uses rsxdalv's TTS-Generation-WebUI,
# a maintained all-in-one audio toolkit (MusicGen / Bark / etc.) with a Gradio
# UI. Digest-pinned default below; override `image` to update.
#
# VRAM note: MusicGen *small* fits the 3080's 10 GB; *medium* wants ~16 GB and
# will offload/slow. Downloaded weights persist under model/musicgen.
{
  mkServiceModule,
  lib,
  pkgs,
  ...
}@args:
mkServiceModule {
  name = "musicgen";
  description = "MusicGen text-to-music (containerized, CDI GPU)";
  surface = {
    unit = "podman-musicgen.service";
    resourceClass = "interactive-agent";
    observe = {
      enable = true;
      restartable = true;
    };
  };
  extraOptions = {
    image = args.lib.mkOption {
      type = args.lib.types.str;
      default = "ghcr.io/rsxdalv/tts-generation-webui@sha256:955ad7ecedd24f1423be5c88ea96b100e683d2d1ff898ca7157b7387f36ded7a";
      description = "Digest-pinned audio toolkit image (MusicGen/Bark). Re-resolve via skopeo inspect to update.";
    };
    port = args.lib.mkOption {
      type = args.lib.types.port;
      default = 8010;
      description = "Host port (bound to 127.0.0.1) for the MusicGen web/API.";
    };
    containerPort = args.lib.mkOption {
      type = args.lib.types.port;
      default = 7860;
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
      dir = "${config.sinnix.paths.librariesRoot}/model/musicgen";
    in
    {
      sinnix.ml.containerRuntime.enable = true;

      systemd.tmpfiles.rules = [ "d ${dir} 0755 ${user} users -" ];

      virtualisation.oci-containers.containers.musicgen = {
        inherit (cfg) image;
        autoStart = false; # on-demand / heavier
        ports = [ "127.0.0.1:${toString cfg.port}:${toString cfg.containerPort}" ];
        volumes = [ "${dir}:/root/.cache/huggingface" ];
        extraOptions = [ "--device=nvidia.com/gpu=all" ];
      };
    };
} args
