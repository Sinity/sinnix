# whisper.cpp server (CUDA) — shared STT hub on 127.0.0.1:8090.
#
# The estate's single OpenAI-compatible /v1/audio/transcriptions endpoint
# (sinnix-mke increment 1). whisper.cpp's own HTTP API is repointed at that
# path via --inference-path so any OpenAI Whisper API client (hermes, the
# phone, capture-audio) can hit it unmodified. The ggml model is
# auto-downloaded into model/whisper on first start if missing.
#
# Socket-activated behind the same idle-aware proxy pattern as
# ollama/koboldcpp (modules/services/ai-control.nix): the public port 8090
# is the systemd socket front door, the backend runs on a private loopback
# port and exits after 30s idle. It shares the ollama/koboldcpp
# gpu-inference admission key (mutual systemd Conflicts in all directions)
# so a transcription request cannot deadlock against a resident LLM.
{
  mkAiService,
  lib,
  pkgs,
  ...
}@args:
mkAiService {
  name = "whisper";
  description = "whisper.cpp speech-to-text server (CUDA)";
  unit = "whisper-server.service";
  endpoint = "127.0.0.1:8090";
  requiresCuda = true;
  activation = {
    mode = "socket-proxy";
    backendEndpoint = "127.0.0.1:8091";
    idleTimeout = "30s";
    exclusiveResource = "gpu-inference";
    dependsOn = [ "whisper-proxy" ];
    # No long-running systemd consumer exists yet: hermes calls the public
    # endpoint directly from a short-lived interactive CLI invocation, so
    # there is nothing here today. The contract stays wired (default `[ ]`)
    # for the capture-audio lane and phone ingest this bead adds later.
  };
  extraOptions = {
    model = args.lib.mkOption {
      type = args.lib.types.str;
      default = "base.en";
      description = "whisper.cpp ggml model short-name (e.g. base.en, large-v3-turbo). Auto-downloaded if missing.";
    };
  };
  configFn =
    {
      cfg,
      config,
      lib,
      pkgs,
      ...
    }:
    let
      user = config.sinnix.user.name;
      whisperDir = "${config.sinnix.paths.mediaRoot}/model/whisper";
      modelFile = "${whisperDir}/ggml-${cfg.model}.bin";
    in
    {
      systemd.tmpfiles.rules = [
        "d ${whisperDir} 0755 ${user} users -"
      ];

      systemd.services.whisper-server = {
        description = "whisper.cpp speech-to-text server";
        wantedBy = [ ]; # on-demand, socket-activated via whisper-proxy
        after = [ "network.target" ];
        # Bound to the socket proxy's lifecycle exactly like ollama/koboldcpp:
        # an idle proxy exit tears down this backend's cgroup (VRAM release).
        partOf = [ "whisper-proxy.service" ];
        bindsTo = [ "whisper-proxy.service" ];
        # Shared gpu-inference admission key: never run alongside the other
        # CUDA inference backends, in either direction.
        conflicts = [
          "ollama.service"
          "ollama-proxy.service"
          "koboldcpp.service"
          "koboldcpp-proxy.service"
          "llama-cpp.service"
          "llama-cpp-proxy.service"
        ];
        serviceConfig = lib.mkMerge [
          {
            User = user;
            Group = "users";
            SupplementaryGroups = [
              "video"
              "render"
            ];
            ExecStartPre = pkgs.writeShellScript "whisper-fetch-model" ''
              set -euo pipefail
              if [ ! -f ${lib.escapeShellArg modelFile} ]; then
                ${pkgs.whisper-cpp-cuda}/bin/whisper-cpp-download-ggml-model ${lib.escapeShellArg cfg.model} ${lib.escapeShellArg whisperDir}
              fi
            '';
            # --inference-path makes the native /inference route also answer
            # at the OpenAI Whisper API shape (multipart file/model/
            # response_format in, {"text": "..."} out) so any OpenAI-client
            # STT consumer (hermes, later Parakeet/Voxtral swap-ins) works
            # unmodified against this hub. Bound to the private backend port
            # only -- clients always speak to 8090 via whisper-proxy.
            ExecStart = lib.concatStringsSep " " [
              "${pkgs.whisper-cpp-cuda}/bin/whisper-server"
              "--host 127.0.0.1"
              "--port 8091"
              "--inference-path /v1/audio/transcriptions"
              "-m ${modelFile}"
            ];
          }
          (lib.sinnix.mkRuntimeServiceConfig {
            runtimeInventory = config.sinnix.runtime.inventory;
            unit = "whisper-server.service";
          })
          (lib.sinnix.systemd.mkRestartPolicy {
            strategy = "on-failure";
            delaySec = 10;
          })
        ];
      };
    };
} args
