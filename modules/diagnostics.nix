# System diagnostics and introspection tools
#
# Provides:
# - Hardware introspection (hwinfo, lshw, smartmontools)
# - Performance analysis (perf-scan, hogkill, asbl-no-moar)
# - Boot metrics capture (systemd-analyze, dmesg)
# - Persistent journald logging with compression
{
  pkgs,
  lib,
  config,
  inputs,
  ...
}:
let
  inherit (config.sinnix.machine) isDesktop;
  inherit (config.sinnix.paths) capturesRoot;
  username = config.sinnix.user.name;

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

  # Explicitly reference local packages from flake outputs to avoid overlays
  localScripts = [
    inputs.self.packages.${pkgs.system}.perf-scan
    inputs.self.packages.${pkgs.system}.hogkill
    inputs.self.packages.${pkgs.system}.asbl-no-moar
  ];

  captureBootMetrics = pkgs.writeShellApplication {
    name = "capture-boot-metrics";
    runtimeInputs = with pkgs; [ coreutils findutils util-linux systemd ];
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
      coreDiagnostics ++ localScripts
    );

    # Logging and metrics (always on)
    systemd.tmpfiles.rules = [
      "d ${journaldBaseDir} 0750 root systemd-journal -"
      "d ${bootMetricsDir} 0750 ${username} users -"
    ];

    services.journald.extraConfig = ''
      # Storage configuration
      Storage=persistent
      Compress=yes

      # Size limits: Large allocation for long-term retention
      # With spam fixed, this should hold 6+ months of logs
      SystemMaxUse=50G
      SystemKeepFree=10G
      SystemMaxFileSize=1G

      # Time-based retention: DISABLED - size is the only limit
      # This ensures maximum log retention
      MaxRetentionSec=0

      # Rotate files weekly to prevent corruption from losing too much
      MaxFileSec=1week

      # Rate limiting: aggressive limits to prevent spam from filling journals
      # 500 messages per 30s = 1000/min max, vs default 10000/30s
      RateLimitIntervalSec=30s
      RateLimitBurst=500

      # Forwarding to syslog disabled (we use journald native)
      ForwardToSyslog=no
    '';

    systemd.services.capture-boot-metrics = {
      description = "Capture boot metrics";
      after = [ "systemd-journald.service" ];
      serviceConfig = {
        Type = "oneshot";
        ExecStart = "${captureBootMetrics}/bin/capture-boot-metrics";
      };
    };

    systemd.timers.capture-boot-metrics = {
      wantedBy = [ "timers.target" ];
      timerConfig = { OnBootSec = "1min"; AccuracySec = "10s"; };
    };
  };
}