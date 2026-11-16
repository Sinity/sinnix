# Parakeet TDT serves OpenAI-compatible transcription on 127.0.0.1:8090 using CPU inference, so it does not need the GPU inference key.
# Socket activation keeps the endpoint available while short-lived workers load VAD and speech models as needed.
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
  docs = "docs/speech.md";
  unit = "sinnix-stt.service";
  requiresCuda = false;
  browserRequests = "native-only";
  activation = {
    mode = "socket-proxy";
    publicEndpoint = "127.0.0.1:${toString helpers.data.ports.stt.public}";
    backendEndpoint = "127.0.0.1:${toString helpers.data.ports.stt.backend}";
    # Keep the HTTP frontend through gaps between interactive voice notes.
    idleTimeout = "300s";
    readinessTimeout = 60;
  };
  configFn =
    {
      cfg,
      config,
      lib,
      pkgs,
      helpers,
      ...
    }:
    let
      user = config.sinnix.user.name;
      modelDir = "${config.sinnix.paths.modelsRoot}/sherpa";
    in
    lib.mkMerge [
      # The recordings pass. Opportunistic and cheap: the VAD gate means a day of
      # mostly-silent ambient audio costs seconds, so this can run often
      # enough that a transcript is never far behind the recording. Direct
      # mkScheduledJob call, not mkAiService/mkServiceModule's `job` sugar:
      # the hub's own unit already occupies this module's single-surface
      # slot, and this is a second, independent oneshot+timer pair.
      (lib.sinnix.mkScheduledJob
        {
          inherit config;
          unitName = "sinnix-stt-recordings";
          description = "Transcribe newly captured recordings";
          surface = config.sinnix.runtime.units.stt-recordings;
        }
        {
          execStart = "${scriptPkgs.sinnix-stt}/bin/sinnix-stt recordings";
          user = user;
          serviceConfig = {
            Group = "users";
            UMask = "0077";
            # Resident model weights and decoding buffers vary per recording.
            # Reclaim below the 3G hard ceiling only refaults those pages when
            # swap is disabled, stalling unrelated work through host pressure.
            MemoryHigh = "infinity";
            MemorySwapMax = "0";
            # A recogniser killed at the 3G ceiling must cost one file, not
            # the pass: under the default OOMPolicy=stop the kill stopped the
            # whole unit, so every recording queued behind it waited forever.
            OOMPolicy = "continue";
            IOReadBandwidthMax = [
              "/realm 20M"
              "/nix 20M"
            ];
          };
          environment = {
            SINNIX_STT_MODEL_ROOT = modelDir;
          };
          timer = {
            onBootSec = "10min";
            intervalSec = cfg.recordingsIntervalSec;
            accuracySec = "5min";
            description = "Periodic transcription of newly landed audio";
          };
        }
      )
      {
        systemd.tmpfiles.rules = [
          "d ${modelDir} 0755 ${user} users -"
          "d ${config.sinnix.paths.capturePaths.transcripts} 0700 ${user} users -"
        ];

        environment.systemPackages = [ scriptPkgs.sinnix-stt ];

        # The hub's own surface comes from mkAiService; the recordings pass is a
        # second unit and needs its own registration, or mkRuntimeServiceConfig
        # throws on an unknown unit (which is the contract working as intended).
        sinnix.runtime.units.stt-recordings = {
          unit = "sinnix-stt-recordings.service";
          resourceClass = "background";
          notifyOnFailure = true;
          operatorRestart = true;
          captures = [
            {
              name = "transcripts";
              path = "${config.sinnix.paths.capturePaths.transcripts}";
              # Deliberately unbudgeted. The recordings pass runs on recordingsIntervalSec,
              # but it only writes when the VAD gate found speech in newly
              # landed audio, so a quiet stretch --
              # the operator away, or simply not talking -- produces nothing and
              # is not evidence of anything. A budget here would measure his day.
              # The freshness of the audio it consumes is already covered by
              # audio-devices and audio-index; what this declaration buys is the
              # "has this ever produced" check, which is the only question about
              # this lane that has an unambiguous answer.
              eventDriven = true;
            }
          ];
        };

        systemd.services.sinnix-stt = {
          description = "Speech-to-text hub (Parakeet TDT via sherpa-onnx)";
          wantedBy = [ ]; # on-demand, socket-activated via stt-proxy
          after = [ "network.target" ];
          serviceConfig = lib.mkMerge [
            {
              User = user;
              Group = "users";
              # Half a gigabyte of weights is not source and does not belong in
              # the store; sinnix already keeps model files under
              # /realm/library/model. Fetched once, verified every start.
              ExecStartPre = "${scriptPkgs.sinnix-stt}/bin/sinnix-stt models";
              ExecStart = lib.concatStringsSep " " [
                "${scriptPkgs.sinnix-stt}/bin/sinnix-stt"
                "serve"
                "--listen 127.0.0.1:${toString helpers.data.ports.stt.backend}"
              ];
              Environment = [
                "SINNIX_STT_MODEL_ROOT=${modelDir}"
                "SINNIX_STT_PUBLIC_ENDPOINT=${config.sinnix.runtime.units.stt.activation.publicEndpoint}"
              ];
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
      }
    ];
  extraOptions = {
    recordingsIntervalSec = args.lib.mkOption {
      type = args.lib.types.ints.positive;
      default = 1800;
      description = "Seconds between recordings transcription passes.";
    };
  };
} args
