# whisper.cpp server (CUDA) — local speech-to-text on 127.0.0.1:8090.
#
# A standalone GPU transcription endpoint (whisper.cpp's own HTTP API). The ggml
# model is auto-downloaded into model/whisper on first start if missing.
# On-demand (wantedBy = [ ]) so it neither blocks boot nor holds VRAM idle.
{
  mkServiceModule,
  lib,
  pkgs,
  ...
}@args:
mkServiceModule {
  name = "whisper";
  description = "whisper.cpp speech-to-text server (CUDA)";
  surface = {
    unit = "whisper-server.service";
    resourceClass = "interactive-agent";
    observe = {
      enable = true;
      restartable = true;
    };
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
        wantedBy = [ ]; # on-demand
        after = [ "network.target" ];
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
            ExecStart = lib.concatStringsSep " " [
              "${pkgs.whisper-cpp-cuda}/bin/whisper-server"
              "--host 127.0.0.1"
              "--port 8090"
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
