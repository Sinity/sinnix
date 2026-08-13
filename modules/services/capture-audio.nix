# Always-on dual-channel PipeWire audio capture
#
# Four units backed by the sinnix-audio-capture Python package
# (pkgs/sinnix-audio-capture, whose docstring carries the full design):
# - sinnix-audio-recorder-mic / sinnix-audio-recorder-sink-monitor: two
#   always-on `record` daemons, one per canonical channel
#   (segment.CHANNEL_PROFILES). No VAD gating -- Opus DTX/VBR collapses
#   silence at the codec level. `pw-record --target <name>` does not
#   reliably reattach to the intended node on reconnect (segments silently
#   truncate), so recorder.py resolves targets to a stable `object.serial`
#   via pw-dump; see pipewire_defaults.py's `resolve_node_serial`.
# - sinnix-audio-topology: a `pw-mon` Node/Port/Link event stream providing
#   node/port attribution.
# - sinnix-audio-index: an hourly `index` timer running Silero VAD over
#   recently-closed Opus segments -- index-only, never a gate; the
#   26h-default lookback already covers a missed run.
#
# Two named units rather than a systemd template: there are exactly two
# canonical channels by design, and per-unit `mkRuntimeServiceConfig` lookup
# plus staleness budgets are simplest as two concrete surfaces.
{
  mkServiceModule,
  lib,
  pkgs,
  config,
  helpers,
  ...
}@args:
let
  username = config.sinnix.user.name;
  scriptPkgs = helpers.mkSinnixPackagesFor pkgs;
  audioPkg = scriptPkgs.sinnix-audio-capture;
  capturesRoot = config.sinnix.paths.capturesRoot;
  audioDir = "${capturesRoot}/audio";
  micDir = "${audioDir}/mic";
  sinkDir = "${audioDir}/sink-monitor";
  topologyDir = "${capturesRoot}/audio-topology";
  indexDir = "${capturesRoot}/audio-index";

  pwRecordBin = "${pkgs.pipewire}/bin/pw-record";
  pwMetadataBin = "${pkgs.pipewire}/bin/pw-metadata";
  pwDumpBin = "${pkgs.pipewire}/bin/pw-dump";
  pwMonBin = "${pkgs.pipewire}/bin/pw-mon";
  opusencBin = "${pkgs.opus-tools}/bin/opusenc";
  ffmpegBin = lib.getExe pkgs.ffmpeg;

  mkRecorderService =
    {
      channel,
      dir,
      extraExecArgs ? "",
      runtimeDirectory ? null,
    }:
    {
      Unit = {
        Description = "Sinnix audio capture: ${channel} channel (mic/sink-monitor -> hour-aligned Opus)";
        After = [
          "graphical-session.target"
          "pipewire.service"
        ];
        PartOf = [ "graphical-session.target" ];
        StartLimitIntervalSec = 300;
        StartLimitBurst = 5;
      };
      Service = lib.sinnix.mkRuntimeServiceConfig {
        runtimeInventory = config.sinnix.runtime.inventory;
        unit = "sinnix-audio-recorder-${channel}.service";
        overrides = {
          Type = "simple";
          ExecStart = lib.concatStringsSep " " (
            [
              "${audioPkg}/bin/sinnix-audio-capture"
              "record"
              "--channel ${channel}"
              "--capture-root ${capturesRoot}"
              "--pw-record-bin ${pwRecordBin}"
              "--pw-metadata-bin ${pwMetadataBin}"
              "--pw-dump-bin ${pwDumpBin}"
              "--opusenc-bin ${opusencBin}"
            ]
            ++ lib.optional (extraExecArgs != "") extraExecArgs
          );
          Restart = "on-failure";
          RestartSec = "5s";
          NoNewPrivileges = true;
          ProtectSystem = "strict";
          ProtectHome = "read-only";
          ReadWritePaths = [ dir ];
          UMask = "0077";
        }
        // lib.optionalAttrs (runtimeDirectory != null) {
          RuntimeDirectory = runtimeDirectory;
        };
      };
      Install.WantedBy = [ "graphical-session.target" ];
    };
in
mkServiceModule {
  name = "capture-audio";
  description = "Always-on dual-channel (mic + sink-monitor) PipeWire audio capture with pw-mon topology + Silero VAD index";
  configFn =
    { ... }:
    {
      systemd.tmpfiles.rules = [
        "d ${micDir} 0755 ${username} users -"
        "d ${sinkDir} 0755 ${username} users -"
        "d ${topologyDir} 0755 ${username} users -"
        "d ${indexDir} 0755 ${username} users -"
      ];

      sinnix.runtime.surfaces = {
        capture-audio-recorder-mic = {
          unit = "sinnix-audio-recorder-mic.service";
          manager = "user";
          resourceClass = "capture-runtime";
          observe = {
            enable = true;
            restartable = true;
          };
          captures = [
            {
              name = "audio-mic";
              path = micDir;
              eventDriven = true;
              # Hour-aligned segments (segment.SEGMENT_SECONDS): budget for
              # one missed rotation before flagging stale, not just the
              # rotation period itself.
              staleAfterSeconds = 7200;
            }
          ];
        };
        capture-audio-recorder-sink-monitor = {
          unit = "sinnix-audio-recorder-sink-monitor.service";
          manager = "user";
          resourceClass = "capture-runtime";
          observe = {
            enable = true;
            restartable = true;
          };
          captures = [
            {
              name = "audio-sink-monitor";
              path = sinkDir;
              eventDriven = true;
              staleAfterSeconds = 7200;
            }
          ];
        };
        capture-audio-topology = {
          unit = "sinnix-audio-topology.service";
          manager = "user";
          resourceClass = "capture-runtime";
          observe = {
            enable = true;
            restartable = true;
          };
          captures = [
            {
              name = "audio-topology";
              path = topologyDir;
              eventDriven = true;
              # Node/port/link churn is intermittent (device plug/unplug,
              # default-target switches) -- a quiet day is a legitimate
              # "topology didn't change" outcome, matching capture-a11y's
              # event-driven budget.
              staleAfterSeconds = 86400;
            }
          ];
        };
        capture-audio-index = {
          unit = "sinnix-audio-index.service";
          manager = "user";
          resourceClass = "capture-runtime";
          observe = {
            enable = true;
            restartable = true;
          };
          captures = [
            {
              name = "audio-index";
              path = indexDir;
              eventDriven = true;
              # Timer runs hourly; the package's own 26h default lookback
              # already tolerates one missed run, so double that again here.
              staleAfterSeconds = 172800;
            }
          ];
        };
      };

      home-manager.users.${username} =
        { ... }:
        {
          systemd.user.services = {
            sinnix-audio-recorder-mic = mkRecorderService {
              channel = "mic";
              dir = micDir;
              # Low-latency raw-PCM mirror off the mic channel only
              # (recorder.py gates the tee on channel == "mic"); RuntimeDirectory
              # gives the socket a writable %t path under ProtectSystem=strict
              # without widening ReadWritePaths.
              extraExecArgs = "--tee-socket %t/sinnix/audio/mic.pcm";
              runtimeDirectory = "sinnix/audio";
            };
            sinnix-audio-recorder-sink-monitor = mkRecorderService {
              channel = "sink-monitor";
              dir = sinkDir;
            };

            sinnix-audio-topology = {
              Unit = {
                Description = "Sinnix audio capture: pw-mon Node/Port/Link topology stream";
                After = [
                  "graphical-session.target"
                  "pipewire.service"
                ];
                PartOf = [ "graphical-session.target" ];
                StartLimitIntervalSec = 300;
                StartLimitBurst = 5;
              };
              Service = lib.sinnix.mkRuntimeServiceConfig {
                runtimeInventory = config.sinnix.runtime.inventory;
                unit = "sinnix-audio-topology.service";
                overrides = {
                  Type = "simple";
                  ExecStart = "${audioPkg}/bin/sinnix-audio-capture topology --capture-root ${capturesRoot} --pw-mon-bin ${pwMonBin}";
                  Restart = "on-failure";
                  RestartSec = "5s";
                  NoNewPrivileges = true;
                  ProtectSystem = "strict";
                  ProtectHome = "read-only";
                  ReadWritePaths = [ topologyDir ];
                  UMask = "0077";
                };
              };
              Install.WantedBy = [ "graphical-session.target" ];
            };

            sinnix-audio-index = {
              Unit = {
                Description = "Sinnix audio capture: Silero VAD index pass over recently-closed Opus segments";
              };
              Service = lib.sinnix.mkRuntimeServiceConfig {
                runtimeInventory = config.sinnix.runtime.inventory;
                unit = "sinnix-audio-index.service";
                overrides = {
                  Type = "oneshot";
                  ExecStart = "${audioPkg}/bin/sinnix-audio-capture index --capture-root ${capturesRoot} --ffmpeg-bin ${ffmpegBin}";
                  NoNewPrivileges = true;
                  ProtectSystem = "strict";
                  ProtectHome = "read-only";
                  ReadWritePaths = [
                    audioDir
                    indexDir
                  ];
                  UMask = "0077";
                };
              };
            };
          };

          systemd.user.timers.sinnix-audio-index = {
            Unit.Description = "Hourly trigger for the Sinnix audio capture Silero VAD index pass";
            Timer = {
              OnCalendar = "hourly";
              Persistent = true;
              RandomizedDelaySec = "5m";
            };
            Install.WantedBy = [ "timers.target" ];
          };
        };
    };
} args
