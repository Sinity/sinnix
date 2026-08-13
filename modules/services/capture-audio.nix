# Always-on PipeWire audio capture: every source plus the sink monitor
#
# Four units backed by the sinnix-audio-capture Python package
# (pkgs/sinnix-audio-capture, whose docstring carries the full design):
# - sinnix-audio-recorder-sources: one supervisor that keeps a recorder
#   alive per live capture source, minus `excludeSourcePatterns`. The set
#   of sources is a runtime fact (USB/Bluetooth devices come and go), so it
#   cannot be a set of statically-declared units; the supervisor's own
#   state lane plus a coverage livenessProbe are what make a source that
#   is present-but-unrecorded visible.
# - sinnix-audio-recorder-sink-monitor: the one channel that legitimately
#   follows a default (the default sink's monitor ports).
#   No VAD gating on either -- Opus DTX/VBR collapses silence at the codec
#   level. `pw-record --target <name>` does not reliably reattach to the
#   intended node on reconnect (segments silently truncate), so targets
#   resolve to a stable `object.serial` via pw-dump; see
#   pipewire_defaults.py's `resolve_node_serial`.
# - sinnix-audio-topology: a `pw-mon` Node/Port/Link event stream providing
#   node/port attribution.
# - sinnix-audio-index: an hourly `index` timer running Silero VAD over
#   recently-closed Opus segments -- index-only, never a gate; the
#   26h-default lookback already covers a missed run. It discovers channel
#   directories rather than taking a fixed list, so per-source channels and
#   the pre-existing `mic/` archive are both indexed.
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
  sinkDir = "${audioDir}/sink-monitor";
  sourcesDir = "${capturesRoot}/audio-sources";
  topologyDir = "${capturesRoot}/audio-topology";
  indexDir = "${capturesRoot}/audio-index";

  cfg = config.sinnix.services.capture-audio;
  excludeArgs = lib.concatMapStringsSep " " (
    pattern: "--exclude ${lib.escapeShellArg pattern}"
  ) cfg.excludeSourcePatterns;

  pwRecordBin = "${pkgs.pipewire}/bin/pw-record";
  pwMetadataBin = "${pkgs.pipewire}/bin/pw-metadata";
  pwDumpBin = "${pkgs.pipewire}/bin/pw-dump";
  pwMonBin = "${pkgs.pipewire}/bin/pw-mon";
  opusencBin = "${pkgs.opus-tools}/bin/opusenc";
  ffmpegBin = lib.getExe pkgs.ffmpeg;

  mkRecorderService =
    {
      name,
      description,
      execArgs,
      dirs,
      runtimeDirectory ? null,
    }:
    {
      Unit = {
        Description = description;
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
        unit = "sinnix-audio-recorder-${name}.service";
        overrides = {
          Type = "simple";
          ExecStart = lib.concatStringsSep " " (
            [
              "${audioPkg}/bin/sinnix-audio-capture"
            ]
            ++ execArgs
            ++ [
              "--capture-root ${capturesRoot}"
              "--pw-record-bin ${pwRecordBin}"
              "--pw-metadata-bin ${pwMetadataBin}"
              "--pw-dump-bin ${pwDumpBin}"
              "--opusenc-bin ${opusencBin}"
            ]
          );
          Restart = "on-failure";
          RestartSec = "5s";
          NoNewPrivileges = true;
          ProtectSystem = "strict";
          ProtectHome = "read-only";
          ReadWritePaths = dirs;
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
  description = "Always-on PipeWire audio capture (every source + sink-monitor) with pw-mon topology + Silero VAD index";
  extraOptions.excludeSourcePatterns = lib.mkOption {
    type = lib.types.listOf lib.types.str;
    default = [ "^alsa_input\\.usb-FiiO_DigiHug_USB_Audio" ];
    description = ''
      Capture sources never to record, as case-insensitive regexes matched
      against a PipeWire node's `node.name` and `node.description`. Matching
      on node.name rather than `object.serial` is deliberate: the serial is
      reassigned on every replug, while node.name is derived from the ALSA
      card id / USB path and survives one.

      The default excludes the line-in on the FiiO DAC, which drives
      speakers and has nothing connected to its input. Everything else
      present is recorded: a source that is not recorded is data that does
      not exist.
    '';
  };
  configFn =
    { ... }:
    {
      systemd.tmpfiles.rules = [
        "d ${audioDir} 0755 ${username} users -"
        "d ${sinkDir} 0755 ${username} users -"
        "d ${sourcesDir} 0755 ${username} users -"
        "d ${topologyDir} 0755 ${username} users -"
        "d ${indexDir} 0755 ${username} users -"
      ];

      sinnix.runtime.surfaces = {
        capture-audio-recorder-sources = {
          unit = "sinnix-audio-recorder-sources.service";
          manager = "user";
          resourceClass = "capture-runtime";
          observe = {
            enable = true;
            restartable = true;
          };
          captures = [
            {
              # The supervisor's own state lane, not the audio directories:
              # per-source channel dirs are dynamic, and pointing a staleness
              # budget at their shared parent would let one healthy source
              # mask every other source's silence.
              name = "audio-sources";
              path = sourcesDir;
              eventDriven = true;
              # The supervisor heartbeats into this lane every 10 minutes
              # (sources.HEARTBEAT_SECONDS) even when nothing changes, so a
              # quiet lane means a dead supervisor, not a quiet desktop.
              staleAfterSeconds = 3600;
              # Staleness cannot see the failure this lane exists to prevent:
              # a source that is present in the graph and recorded by nobody.
              livenessProbe = {
                command = "${audioPkg}/bin/sinnix-audio-capture sources-probe --capture-root ${capturesRoot} --pw-dump-bin ${pwDumpBin} ${excludeArgs}";
                timeoutSeconds = 15;
              };
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
            sinnix-audio-recorder-sources = mkRecorderService {
              name = "sources";
              description = "Sinnix audio capture: every PipeWire source (minus the blacklist) -> hour-aligned Opus";
              execArgs = [
                "record-sources"
                "--tee-socket %t/sinnix/audio/mic.pcm"
              ]
              ++ lib.optional (excludeArgs != "") excludeArgs;
              # The per-source channel directories are created at runtime, so
              # the writable path is the parent, not an enumerable list.
              dirs = [
                audioDir
                sourcesDir
              ];
              # Low-latency raw-PCM mirror of whichever source is the current
              # default; RuntimeDirectory gives the socket a writable %t path
              # under ProtectSystem=strict without widening ReadWritePaths.
              runtimeDirectory = "sinnix/audio";
            };
            sinnix-audio-recorder-sink-monitor = mkRecorderService {
              name = "sink-monitor";
              description = "Sinnix audio capture: sink-monitor channel (default sink's monitor ports -> hour-aligned Opus)";
              execArgs = [
                "record"
                "--channel sink-monitor"
              ];
              dirs = [ sinkDir ];
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
