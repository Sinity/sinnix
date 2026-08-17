# System diagnostics and introspection tools
#
# Hardware introspection and performance-analysis tooling, boot-metrics
# capture, journal indexing, and persistent journald logging.
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
  capturesRoot = config.sinnix.paths.machineRoot;
  username = config.sinnix.user.name;
  scriptPkgs = helpers.mkSinnixPackagesFor pkgs;

  journaldBaseDir = "${capturesRoot}/syslog";
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
  config = {
    environment.systemPackages = lib.mkIf isDesktop (
      coreDiagnostics
      ++ [
        scriptPkgs.hogkill
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

    systemd.services.capture-boot-metrics = {
      description = "Capture boot metrics";
      # systemd-analyze needs FinishTimestampMonotonic != 0, only set once
      # every boot service has finished (2+ min with slow nofail mounts).
      after = [
        "systemd-journald.service"
        "multi-user.target"
      ];
      serviceConfig = {
        Type = "oneshot";
        ExecStart = "${captureBootMetrics}/bin/capture-boot-metrics";
      };
    };

    systemd.timers.capture-boot-metrics = {
      wantedBy = [ "timers.target" ];
      timerConfig = {
        OnBootSec = "3min";
        AccuracySec = "10s";
      };
    };

    systemd.services.syslog-index = {
      description = "Build no-loss syslog/journal capture indexes";
      after = [
        "local-fs.target"
        "systemd-journald.service"
      ];
      unitConfig.RequiresMountsFor = [ journaldBaseDir ];
      serviceConfig = {
        Type = "oneshot";
        ExecStart = "${scriptPkgs.syslog-index}/bin/syslog-index --no-edge-inspect";
      };
    };

    systemd.timers.syslog-index = {
      description = "Refresh no-loss syslog/journal capture indexes";
      wantedBy = [ "timers.target" ];
      timerConfig = {
        OnBootSec = "4min";
        OnUnitActiveSec = "1h";
        AccuracySec = "1min";
      };
    };
  };
}
