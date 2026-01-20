# System logging and boot metrics capture
#
# Configures journald for persistent logging with compression, and captures
# boot performance metrics (systemd-analyze, dmesg, journal errors) on each boot.
#
# Outputs:
# - Journald logs → ${capturesRoot}/syslog/journal/
# - Boot metrics → ${capturesRoot}/syslog/boot-metrics/{boot_id}/
{
  pkgs,
  lib,
  config,
  ...
}:
let
  inherit (config.sinnix.paths) capturesRoot;
  journaldBaseDir = "${capturesRoot}/syslog";
  bootMetricsDir = "${journaldBaseDir}/boot-metrics";
  username = config.sinnix.user.name;
  captureBootMetrics = pkgs.writeShellApplication {
    name = "capture-boot-metrics";
    runtimeInputs = [
      pkgs.coreutils
      pkgs.findutils
      pkgs.util-linux
      pkgs.systemd
    ];
    text = ''
      set -euo pipefail

      wait_for_boot_completion() {
        local state
        for _ in $(seq 1 12); do
          state="$(systemctl is-system-running 2>/dev/null || true)"
          case "''${state}" in
            running|degraded)
              return 0
              ;;
          esac
          echo "capture-boot-metrics: system state ''${state:-unknown}, waiting..."
          sleep 5
        done
        echo "capture-boot-metrics: system state still ''${state:-unknown}; continuing anyway"
      }

      if [ "''${CAPTURE_BOOT_METRICS_SKIP_WAIT:-0}" = "1" ]; then
        echo "capture-boot-metrics: skipping wait for system state"
      else
        wait_for_boot_completion
      fi

      BOOT_ID="$(cat /proc/sys/kernel/random/boot_id)"

      run_timeout() {
        local limit="$1"
        shift
        timeout "$limit" "$@" || true
      }

      OUT_DIR="${bootMetricsDir}/''${BOOT_ID}"
      mkdir -p "''${OUT_DIR}"

      run_timeout 10s systemd-analyze time > "''${OUT_DIR}/time.txt"
      run_timeout 15s systemd-analyze blame > "''${OUT_DIR}/blame.txt"
      run_timeout 15s systemd-analyze critical-chain > "''${OUT_DIR}/critical-chain.txt"
      run_timeout 20s systemd-analyze plot > "''${OUT_DIR}/boot.svg"

      run_timeout 20s journalctl -b -p 0..3 > "''${OUT_DIR}/journal-errors.log"
      run_timeout 15s dmesg > "''${OUT_DIR}/dmesg.log"

    '';
  };
in
{
  config = {
    systemd.tmpfiles.rules = lib.mkAfter [
      "d ${journaldBaseDir} 0750 root systemd-journal -"
      "d ${journaldBaseDir}/journal 2750 root systemd-journal -"
      "d ${bootMetricsDir} 0750 ${username} users -"
    ];

    services.journald.extraConfig = ''
      Compress=yes
      Storage=persistent
      SystemMaxUse=250G
      SystemKeepFree=10G
      SystemMaxFileSize=200M
      SystemMaxFiles=0
      RuntimeMaxUse=1G
      SplitMode=uid
    '';

    systemd.services.capture-boot-metrics = {
      description = "Capture boot metrics and logs";
      after = [
        "systemd-journald.service"
      ];
      environment = {
        CAPTURE_BOOT_METRICS_SKIP_WAIT = "1";
      };
      serviceConfig = {
        Type = "oneshot";
        ExecStart = "${captureBootMetrics}/bin/capture-boot-metrics";
        TimeoutStartSec = "2min";
      };
      unitConfig = {
        RequiresMountsFor = [ bootMetricsDir ];
      };
    };

    systemd.timers.capture-boot-metrics = {
      description = "Schedule boot metrics capture";
      wantedBy = [ "timers.target" ];
      timerConfig = {
        OnBootSec = "1min";
        AccuracySec = "10s";
        Unit = "capture-boot-metrics.service";
      };
    };
  };
}
