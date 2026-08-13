# Kokoro-82M text-to-speech — a CPU-only, ~80ms-latency OpenAI-compatible
# /v1/audio/speech endpoint (remsky/Kokoro-FastAPI). This is hermes's
# replacement for the edge-tts cloud dependency (Microsoft's voice API):
# hermes already ships a built-in "openai" TTS provider speaking this exact
# wire shape, so pointing hermes's tts.openai.base_url at this hub
# (modules/features/dev/agents/clis.nix) is a config repoint, not a patch.
#
# CPU-only (the image bakes DEVICE=cpu/USE_GPU=false): Kokoro-82M is fast
# enough on CPU that the gpu-inference admission key would only buy queueing
# behind ollama/koboldcpp/whisper, and TTS must stay answerable while a CUDA
# backend is resident. It never requires or conflicts with that key.
#
# Socket-activated behind the same idle-aware proxy pattern as
# ollama/koboldcpp/whisper (modules/services/ai-control.nix): the public port
# 8890 is the systemd socket front door (8880 belongs to sinnix-hub); the
# backend container runs on a private loopback port and exits after 30s idle.
#
# Digest-pinned OCI container; weights (~330MB) are baked into the image at
# build time (no runtime download), and the image itself is stored under the
# shared ml-containers.nix graphroot on /realm, not the wear-limited root SSD.
{
  mkAiService,
  lib,
  pkgs,
  ...
}@args:
mkAiService {
  name = "kokoro";
  description = "Kokoro-82M TTS (CPU, OpenAI-compatible /v1/audio/speech, containerized)";
  unit = "podman-kokoro.service";
  endpoint = "127.0.0.1:8890";
  backendKind = "container";
  requiresCuda = false;
  activation = {
    mode = "socket-proxy";
    backendEndpoint = "127.0.0.1:8891";
    idleTimeout = "30s";
    dependsOn = [ "kokoro-proxy" ];
  };
  extraOptions = {
    autoStart = args.lib.mkOption {
      type = args.lib.types.bool;
      default = false;
      description = "Start the Kokoro container at boot instead of purely on-demand via kokoro-proxy.";
    };
    image = args.lib.mkOption {
      type = args.lib.types.str;
      default = "ghcr.io/remsky/kokoro-fastapi-cpu@sha256:fa52dce920c3610c78fccde4f6fa064fb092ae95018cf42b42d84d876655e8d9";
      description = "Digest-pinned Kokoro-FastAPI CPU image. Re-resolve via skopeo inspect (or the ghcr token-manifest API) to update.";
    };
  };
  configFn =
    { cfg, ... }:
    {
      sinnix.ml.containerRuntime.enable = true;

      virtualisation.oci-containers.containers.kokoro = {
        inherit (cfg) image autoStart;
        pull = "never";
        # Container listens on 8880 internally; mapped to the private
        # backend port the kokoro-proxy socket forwards to (public 8890 is
        # the proxy's own listener, not this container's).
        ports = [ "127.0.0.1:8891:8880" ];
        environment = {
          # Weights are already baked into the pinned image; skip the
          # runtime re-download check on every start.
          DOWNLOAD_MODEL = "false";
        };
      };

      # Bind the container to the proxy's lifecycle: a clean idle exit of
      # kokoro-proxy tears this container down too, releasing its cgroup
      # instead of idling resident.
      systemd.services.podman-kokoro = {
        partOf = [ "kokoro-proxy.service" ];
        bindsTo = [ "kokoro-proxy.service" ];
      };
    };
} args
