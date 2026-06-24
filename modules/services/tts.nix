# Text-to-speech via OpenedAI-Speech — an OpenAI-compatible /v1/audio/speech
# endpoint backed by Piper (fast) and Coqui XTTS (voice cloning). Open WebUI
# consumes it for read-aloud / voice-call (see services/open-webui.nix env).
#
# Digest-pinned OCI container with CDI GPU passthrough (XTTS uses CUDA; Piper is
# CPU). Web/API on 127.0.0.1:8000. Voices + config persist under model/tts.
{
  mkServiceModule,
  lib,
  pkgs,
  ...
}@args:
mkServiceModule {
  name = "tts";
  description = "OpenedAI-Speech TTS bridge (Piper + XTTS, containerized)";
  surface = {
    unit = "podman-openedai-speech.service";
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
        default = "ghcr.io/matatonic/openedai-speech@sha256:3ef4f857d5a757cfe8e9b61185df1bd3c52c45f950716a54e4399c27c3e91396";
        description = "Digest-pinned OpenedAI-Speech image. Use the -min image for Piper-only (no XTTS).";
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
      ttsDir = "${config.sinnix.paths.librariesRoot}/model/tts";
    in
    {
      sinnix.ml.containerRuntime.enable = true;

      systemd.tmpfiles.rules = [
        "d ${ttsDir} 0755 ${user} users -"
        "d ${ttsDir}/voices 0755 ${user} users -"
        "d ${ttsDir}/config 0755 ${user} users -"
      ];

      virtualisation.oci-containers.containers.openedai-speech = {
        image = cfg.image;
        autoStart = true;
        pull = "never";
        ports = [ "127.0.0.1:8000:8000" ];
        volumes = [
          "${ttsDir}/voices:/app/voices"
          "${ttsDir}/config:/app/config"
        ];
        extraOptions = [ "--device=nvidia.com/gpu=all" ];
      };

      systemd.services.podman-openedai-speech.serviceConfig.TimeoutStartSec =
        lib.mkForce "2min";
    };
} args
