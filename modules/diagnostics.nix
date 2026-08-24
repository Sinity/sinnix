# System diagnostics and introspection tools
#
# Hardware introspection and performance-analysis tooling, boot-metrics
# capture and indexing, and persistent journald logging.
{
  pkgs,
  lib,
  config,
  inputs,
  helpers,
  ...
}:
let
  inherit (config.sinnix.machine) isDesktop;
  telemetryRoot = config.sinnix.paths.machineRoot;
  username = config.sinnix.user.name;
  scriptPkgs = helpers.mkSinnixPackagesFor pkgs;

  journaldBaseDir = "${telemetryRoot}/syslog";
  bootMetricsDir = "${journaldBaseDir}/boot-metrics";

  coreDiagnostics = with pkgs; [
    hwinfo
    inxi
    lshw
    smartmontools
    nvme-cli
    hdparm
  ];

  captureBootMetrics = pkgs.writeShellApplication {
    name = "capture-boot-metrics";
    runtimeInputs = with pkgs; [
      coreutils
      findutils
      util-linux
      systemd
    ];
    text = ''
      set -euo pipefail
      BOOT_ID="$(cat /proc/sys/kernel/random/boot_id)"
      OUT_DIR="${bootMetricsDir}/$BOOT_ID"
      mkdir -p "$OUT_DIR"
      systemd-analyze time > "$OUT_DIR/time.txt"
      systemd-analyze blame > "$OUT_DIR/blame.txt"
      journalctl -b -p 0..3 > "$OUT_DIR/journal-errors.log"
      dmesg > "$OUT_DIR/dmesg.log"
    '';
  };

in
{
  config = lib.mkMerge [
    # syslog-index previously ran with no registered runtime surface at all
    # (no resourceClass resolution, no failure-notify) -- an intended
    # semantic delta of this conversion, not merely a render change: it now
    # carries background-maintenance's Nice/IOScheduling/CPU/IOWeight/Memory
    # governance and the standard OnFailure path, matching every other
    # scheduled oneshot on this host.
    (lib.sinnix.mkScheduledJob
      {
        inherit config;
        unitName = "syslog-index";
        description = "Build no-loss boot-metric capture indexes";
        surface = config.sinnix.runtime.surfaces.syslog-index;
      }
      {
        # manager defaults "system", which always resolves resources via the
        # unit-based mkRuntimeServiceConfig lookup below -- resourceClass here
        # would be a no-op (that key only applies to manager="user" jobs); the
        # class comes from the syslog-index surface's own resourceClass field.
        execStart = "${scriptPkgs.syslog-index}/bin/syslog-index";
        unit = {
          after = [
            "local-fs.target"
            "systemd-journald.service"
          ];
          unitConfig.RequiresMountsFor = [ journaldBaseDir ];
        };
        timer = {
          onBootSec = "4min";
          onUnitActiveSec = "1h";
          accuracySec = "1min";
          description = "Refresh no-loss boot-metric capture indexes";
        };
      }
    )
    # Boot-triggered oneshot, same governance treatment as syslog-index:
    # previously unclassed and without failure reporting.
    (lib.sinnix.mkScheduledJob
      {
        inherit config;
        unitName = "capture-boot-metrics";
        description = "Capture boot metrics";
        surface = config.sinnix.runtime.surfaces.capture-boot-metrics;
      }
      {
        execStart = "${captureBootMetrics}/bin/capture-boot-metrics";
        unit = {
          # systemd-analyze needs FinishTimestampMonotonic != 0, only set
          # once every boot service has finished (2+ min with slow nofail
          # mounts).
          after = [
            "systemd-journald.service"
            "multi-user.target"
          ];
        };
        timer = {
          onBootSec = "3min";
          accuracySec = "10s";
        };
      }
    )
    {
      environment.systemPackages = lib.mkIf isDesktop (
        coreDiagnostics
        ++ [
          scriptPkgs.asbl-no-moar
          scriptPkgs.nuke-builds
          scriptPkgs.sinnix-observe
          scriptPkgs."sinnix-free-headroom"
          scriptPkgs.machine-experiment-run
          scriptPkgs.syslog-index
        ]
      );

      # User-owned: these hold boot-metrics captures, not journald's own store.
      systemd.tmpfiles.rules = [
        "d ${journaldBaseDir} 0750 ${username} users -"
        "d ${bootMetricsDir} 0750 ${username} users -"
        "d ${journaldBaseDir}/index 0750 ${username} users -"
      ];

      sinnix.runtime.surfaces.capture-boot-metrics = {
        unit = "capture-boot-metrics.service";
        resourceClass = "background-maintenance";
        observe.enable = true;
      };

      sinnix.runtime.surfaces.syslog-index = {
        unit = "syslog-index.service";
        resourceClass = "background-maintenance";
        observe.enable = true;
      };
    }
  ];
}
