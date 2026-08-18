# Text-to-speech via OpenedAI-Speech — an OpenAI-compatible /v1/audio/speech
# endpoint backed by Piper (fast) and Coqui XTTS (voice cloning). Open WebUI
# consumes it for read-aloud / voice-call (see services/open-webui.nix env).
#
# Digest-pinned OCI container with CDI GPU passthrough (XTTS uses CUDA; Piper is
# CPU). Web/API on 127.0.0.1:8000. Voices + config persist under model/tts.
{
  mkAiService,
  lib,
  pkgs,
  helpers,
  ...
}@args:
mkAiService {
  name = "tts";
  description = "OpenedAI-Speech TTS bridge (Piper + XTTS, containerized)";
  docs = "docs/local-ai-activation.md";
  unit = "podman-openedai-speech.service";
  endpoint = "127.0.0.1:${toString helpers.data.ports.tts.public}";
  backendKind = "container";
  requiresCuda = true;
  activation = {
    mode = "socket-proxy";
    backendEndpoint = "127.0.0.1:${toString helpers.data.ports.tts.backend}";
    idleTimeout = "300s";
    exclusiveResource = "gpu-inference";
    dependsOn = [ "tts-proxy" ];
  };
  extraOptions = {
    autoStart = args.lib.mkOption {
      type = args.lib.types.bool;
      default = true;
      description = "Start the OpenedAI-Speech container automatically at boot.";
    };
    image = args.lib.mkOption {
      type = args.lib.types.str;
      default = "ghcr.io/matatonic/openedai-speech@sha256:3ef4f857d5a757cfe8e9b61185df1bd3c52c45f950716a54e4399c27c3e91396";
      description = "Digest-pinned OpenedAI-Speech image. Use the -min image for Piper-only (no XTTS).";
    };
  };
  configFn =
    {
      cfg,
      config,
      helpers,
      ...
    }:
    let
      user = config.sinnix.user.name;
      ttsDir = "${config.sinnix.paths.modelsRoot}/tts";
    in
    {
      sinnix.ml.containerRuntime.enable = true;

      systemd.tmpfiles.rules = [
        "d ${ttsDir} 0755 ${user} users -"
        "d ${ttsDir}/voices 0755 ${user} users -"
        "d ${ttsDir}/config 0755 ${user} users -"
      ];

      virtualisation.oci-containers.containers.openedai-speech = {
        inherit (cfg) image;
        inherit (cfg) autoStart;
        pull = "never";
        # Published on the PRIVATE backend port only -- clients always speak
        # to the public port via tts-proxy (modules/services/ai-control.nix),
        # never to the container directly. The container-internal port (right
        # side) is not a host allocation -- it just happens to numerically
        # match the public port by coincidence, so it stays a literal.
        ports = [ "127.0.0.1:${toString helpers.data.ports.tts.backend}:8000" ];
        volumes = [
          "${ttsDir}/voices:/app/voices"
          "${ttsDir}/config:/app/config"
        ];
        extraOptions = [ "--device=nvidia.com/gpu=all" ];
      };

      systemd.services.podman-openedai-speech = {
        serviceConfig.TimeoutStartSec = lib.mkForce "2min";
        # Bound to the socket proxy's lifecycle: an idle proxy exit tears
        # down this container's cgroup. Conflicts= against every other
        # GPU-inference backend is computed centrally in ai-control.nix's
        # gpuInferenceConflicts.
        partOf = [ "tts-proxy.service" ];
      };
    };
} args
