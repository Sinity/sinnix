# Always-on PipeWire audio capture: every source and every sink
#
# Three units backed by the sinnix-audio-capture Python package
# (pkgs/sinnix-audio-capture, whose docstring carries the full design):
# - sinnix-audio-recorder-devices: one supervisor that keeps a recorder
#   alive per live device -- capture sources directly, playback sinks
#   through their monitor ports -- minus `exclude{Source,Sink}Patterns`.
#   The set of devices is a runtime fact (USB and Bluetooth devices come
#   and go), so it cannot be a set of statically-declared units; the
#   supervisor's own state lane plus a coverage livenessProbe are what
#   make a device that is present-but-unrecorded visible. No VAD gating --
#   Opus DTX/VBR collapses silence at the codec level. `pw-record --target
#   <name>` does not reliably attach to the intended node (segments
#   silently truncate), so targets resolve to a stable `object.serial` via
#   pw-dump; see devices.py's `resolve_node_serial`.
# - sinnix-audio-topology: a `pw-mon` Node/Port/Link event stream providing
#   node/port attribution.
# - sinnix-audio-index: an hourly `index` timer running Silero VAD over
#   recently-closed Opus segments -- index-only, never a gate; the
#   26h-default lookback already covers a missed run. It discovers channel
#   directories rather than taking a fixed list, so per-device channels and
#   the pre-existing mic/ and sink-monitor/ archives are all indexed.
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
  devicesDir = "${capturesRoot}/audio-devices";
  topologyDir = "${capturesRoot}/audio-topology";
  indexDir = "${capturesRoot}/audio-index";

  cfg = config.sinnix.services.capture-audio;
  mkExcludeArgs =
    flag: patterns: lib.concatMapStringsSep " " (p: "${flag} ${lib.escapeShellArg p}") patterns;
  excludeArgs = lib.concatStringsSep " " (
    lib.filter (s: s != "") [
      (mkExcludeArgs "--exclude-source" cfg.excludeSourcePatterns)
      (mkExcludeArgs "--exclude-sink" cfg.excludeSinkPatterns)
    ]
  );

  pwRecordBin = "${pkgs.pipewire}/bin/pw-record";
  pwDumpBin = "${pkgs.pipewire}/bin/pw-dump";
  pwMonBin = "${pkgs.pipewire}/bin/pw-mon";
  opusencBin = "${pkgs.opus-tools}/bin/opusenc";
  ffmpegBin = lib.getExe pkgs.ffmpeg;

  hardening = {
    NoNewPrivileges = true;
    ProtectSystem = "strict";
    ProtectHome = "read-only";
    UMask = "0077";
  };
in
mkServiceModule {
  name = "capture-audio";
  description = "Always-on PipeWire audio capture (every source and sink) with pw-mon topology + Silero VAD index";
  extraOptions = {
    excludeSourcePatterns = lib.mkOption {
      type = lib.types.listOf lib.types.str;
      default = [ "^alsa_input\\.usb-FiiO_DigiHug_USB_Audio" ];
      description = ''
        Capture sources never to record, as case-insensitive regexes matched
        against a PipeWire node's `node.name` and `node.description`. Matching
        on node.name rather than `object.serial` is deliberate: the serial is
        reassigned on every replug, while node.name is derived from the ALSA
        card id / USB path and survives one.

        The default excludes the line-in on the FiiO DAC, which has nothing
        connected to its input. It does not touch that same DAC's playback
        side, which drives the speakers and is recorded through its monitor:
        node.name encodes direction (`alsa_input.` vs `alsa_output.`).
      '';
    };
    excludeSinkPatterns = lib.mkOption {
      type = lib.types.listOf lib.types.str;
      default = [ ];
      description = ''
        Playback sinks whose monitor is never recorded, matched the same way.

        Empty by design: several sinks carrying the same stream produce
        duplicate audio, which is accepted -- each sink is a distinct
        rendering, silence costs almost nothing under Opus DTX, and choosing
        which sink "really" played something would reintroduce exactly the
        role-over-device guess this lane exists to remove.
      '';
    };
    asrSourcePattern = lib.mkOption {
      type = lib.types.nullOr lib.types.str;
      default = "^alsa_input\\.usb-Blue_Microphones_Yeti";
      description = ''
        Which capture source feeds the low-latency ASR tee socket, as a
        regex matched like the exclusion patterns.

        This nominates a device for transcription only. It privileges no
        lane in the archive: every source and sink is recorded identically
        whether or not it feeds this socket, and changing this option
        changes nothing about what is captured. Keeping the two concerns
        apart is deliberate -- a "primary" capture channel is the
        role-not-device mistake that produced the original single-mic bug.
        Null disables the tee.
      '';
    };
  };
  configFn =
    { ... }:
    {
      systemd.tmpfiles.rules = [
        "d ${audioDir} 0755 ${username} users -"
        "d ${devicesDir} 0755 ${username} users -"
        "d ${topologyDir} 0755 ${username} users -"
        "d ${indexDir} 0755 ${username} users -"
      ];

      sinnix.runtime.surfaces = {
        capture-audio-recorder-devices = {
          unit = "sinnix-audio-recorder-devices.service";
          manager = "user";
          resourceClass = "capture-runtime";
          observe = {
            enable = true;
            restartable = true;
          };
          captures = [
            {
              # The supervisor's own state lane, not the audio directories:
              # per-device channel dirs are dynamic, and pointing a staleness
              # budget at their shared parent would let one healthy device
              # mask every other device's silence.
              name = "audio-devices";
              path = devicesDir;
              eventDriven = true;
              # The supervisor heartbeats into this lane every 10 minutes
              # (devices.HEARTBEAT_SECONDS) even when nothing changes, so a
              # quiet lane means a dead supervisor, not a quiet desktop.
              staleAfterSeconds = 3600;
              # Staleness cannot see the failure this lane exists to prevent:
              # a device that is present in the graph and recorded by nobody.
              livenessProbe = {
                command = "${audioPkg}/bin/sinnix-audio-capture devices-probe --capture-root ${capturesRoot} --pw-dump-bin ${pwDumpBin} ${excludeArgs}";
                timeoutSeconds = 15;
              };
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
              # profile switches) -- a quiet day is a legitimate "topology
              # didn't change" outcome, matching capture-a11y's event-driven
              # budget.
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
            sinnix-audio-recorder-devices = {
              Unit = {
                Description = "Sinnix audio capture: every PipeWire source and sink (minus the blacklists) -> hour-aligned Opus";
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
                unit = "sinnix-audio-recorder-devices.service";
                overrides = {
                  Type = "simple";
                  ExecStart = lib.concatStringsSep " " (
                    [
                      "${audioPkg}/bin/sinnix-audio-capture"
                      "record-devices"
                      "--capture-root ${capturesRoot}"
                      "--pw-record-bin ${pwRecordBin}"
                      "--pw-dump-bin ${pwDumpBin}"
                      "--opusenc-bin ${opusencBin}"
                    ]
                    ++ lib.optional (excludeArgs != "") excludeArgs
                    ++ lib.optionals (cfg.asrSourcePattern != null) [
                      "--asr-source ${lib.escapeShellArg cfg.asrSourcePattern}"
                      # RuntimeDirectory gives the socket a writable %t path
                      # under ProtectSystem=strict without widening
                      # ReadWritePaths.
                      "--tee-socket %t/sinnix/audio/asr.pcm"
                    ]
                  );
                  Restart = "on-failure";
                  RestartSec = "5s";
                  # The per-device channel directories are created at runtime,
                  # so the writable path is the parent, not an enumerable list.
                  ReadWritePaths = [
                    audioDir
                    devicesDir
                  ];
                  RuntimeDirectory = "sinnix/audio";
                }
                // hardening;
              };
              Install.WantedBy = [ "graphical-session.target" ];
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
                  ReadWritePaths = [ topologyDir ];
                }
                // hardening;
              };
              Install.WantedBy = [ "graphical-session.target" ];
            };

            sinnix-audio-index = {
              Unit = {
                Description = "Sinnix audio capture: Silero VAD index pass over recently-closed Opus segments";
                # Timer-driven batch oneshot: sd-switch waits for a changed
                # unit's job, and a full VAD sweep outlives the 5-minute
                # activation timeout, failing the whole activation. No daemon
                # to keep current -- the next trigger picks up the new binary.
                X-SwitchMethod = "keep-old";
              };
              Service = lib.sinnix.mkRuntimeServiceConfig {
                runtimeInventory = config.sinnix.runtime.inventory;
                unit = "sinnix-audio-index.service";
                overrides = {
                  Type = "oneshot";
                  ExecStart = "${audioPkg}/bin/sinnix-audio-capture index --capture-root ${capturesRoot} --ffmpeg-bin ${ffmpegBin}";
                  ReadWritePaths = [
                    audioDir
                    indexDir
                  ];
                }
                // hardening;
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
