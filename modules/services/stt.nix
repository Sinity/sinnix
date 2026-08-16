# The estate's speech-to-text hub — Parakeet TDT 0.6B v3 on 127.0.0.1:8090.
#
# One OpenAI-compatible /v1/audio/transcriptions endpoint, which is the same
# interface whisper.cpp served on this port before it was retired. Clients
# (hermes, the phone, anything speaking the OpenAI audio API) were not changed
# by the engine swap; only what answers changed.
#
# Two things about this module are deliberately unlike its predecessor.
#
# It does not touch the GPU. whisper.cpp needed CUDA and therefore had to hold
# the shared gpu-inference admission key, so a transcription could not run
# while an LLM was resident and vice versa. Parakeet int8 through sherpa-onnx
# is fast enough on this CPU to make that trade unnecessary -- measured on
# sinnix-prime: RTF 0.113 on dense speech and RTF 0.002 over a VAD-gated
# 300 s ambient chunk. Dropping the key means transcription is always
# available rather than queued behind the model tier, which matters most for
# exactly the always-on lane this exists to serve.
#
# It is still socket-activated. Not for VRAM -- there is none to release --
# but because the encoder is 650 MB of resident RSS that a mostly-idle service
# has no business holding. The proxy front door keeps the port always
# answerable while the backend comes and goes.
{
  mkAiService,
  lib,
  pkgs,
  helpers,
  ...
}@args:
let
  scriptPkgs = helpers.mkSinnixPackagesFor pkgs;
in
mkAiService {
  name = "stt";
  description = "Speech-to-text hub (Parakeet TDT via sherpa-onnx)";
  unit = "sinnix-stt.service";
  endpoint = "127.0.0.1:8090";
  requiresCuda = false;
  activation = {
    mode = "socket-proxy";
    backendEndpoint = "127.0.0.1:8091";
    # Longer than the GPU services' 30s: there is no scarce resource being
    # held, and re-loading a 650 MB encoder for every voice note in a
    # conversation is worse than keeping it warm through the gaps.
    idleTimeout = "300s";
    dependsOn = [ "stt-proxy" ];
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
      modelDir = "${config.sinnix.paths.mediaRoot}/model/sherpa";
    in
    {
      systemd.tmpfiles.rules = [
        "d ${modelDir} 0755 ${user} users -"
        "d ${config.sinnix.paths.capturesRoot}/transcripts 0755 ${user} users -"
      ];

      environment.systemPackages = [ scriptPkgs.sinnix-stt ];

      # The hub's own surface comes from mkAiService; the lake pass is a
      # second unit and needs its own registration, or mkRuntimeServiceConfig
      # throws on an unknown unit (which is the contract working as intended).
      sinnix.runtime.surfaces.stt-lake = {
        unit = "sinnix-stt-lake.service";
        resourceClass = "background-maintenance";
        observe = {
          enable = true;
          restartable = true;
        };
      };

      systemd.services.sinnix-stt = {
        description = "Speech-to-text hub (Parakeet TDT via sherpa-onnx)";
        wantedBy = [ ]; # on-demand, socket-activated via stt-proxy
        after = [ "network.target" ];
        partOf = [ "stt-proxy.service" ];
        serviceConfig = lib.mkMerge [
          {
            User = user;
            Group = "users";
            # Half a gigabyte of weights is not source and does not belong in
            # the store; the estate already keeps model files under
            # /realm/media/model. Fetched once, verified every start.
            ExecStartPre = "${scriptPkgs.sinnix-stt}/bin/sinnix-stt models";
            ExecStart = lib.concatStringsSep " " [
              "${scriptPkgs.sinnix-stt}/bin/sinnix-stt"
              "serve"
              "--listen 127.0.0.1:8091"
            ];
            Environment = [ "SINNIX_STT_MODEL_ROOT=${modelDir}" ];
          }
          (lib.sinnix.mkRuntimeServiceConfig {
            runtimeInventory = config.sinnix.runtime.inventory;
            unit = "sinnix-stt.service";
          })
          (lib.sinnix.systemd.mkRestartPolicy {
            strategy = "on-failure";
            delaySec = 10;
          })
        ];
      };

      # The lake pass. Opportunistic and cheap: the VAD gate means a day of
      # mostly-silent ambient audio costs seconds, so this can run often
      # enough that a transcript is never far behind the recording.
      systemd.services.sinnix-stt-lake = {
        description = "Transcribe newly landed audio in the lake";
        serviceConfig = lib.mkMerge [
          {
            Type = "oneshot";
            User = user;
            Group = "users";
            ExecStart = "${scriptPkgs.sinnix-stt}/bin/sinnix-stt lake";
            Environment = [ "SINNIX_STT_MODEL_ROOT=${modelDir}" ];
          }
          (lib.sinnix.mkRuntimeServiceConfig {
            runtimeInventory = config.sinnix.runtime.inventory;
            unit = "sinnix-stt-lake.service";
          })
        ];
      };

      systemd.timers.sinnix-stt-lake = {
        description = "Periodic transcription of newly landed audio";
        wantedBy = [ "timers.target" ];
        timerConfig = {
          OnBootSec = "10min";
          OnUnitActiveSec = "${toString cfg.lakeIntervalSec}s";
          AccuracySec = "5min";
        };
      };
    };
  extraOptions = {
    lakeIntervalSec = args.lib.mkOption {
      type = args.lib.types.ints.positive;
      default = 1800;
      description = "Seconds between lake transcription passes.";
    };
  };
} args
