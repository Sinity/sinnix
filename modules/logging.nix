{
  pkgs,
  lib,
  config,
  ...
}:
let
  dataRoot = config.sinnix.paths.dataRoot;
  journaldBaseDir = "${dataRoot}/syslog";
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

      BOOT_ID="$(cat /proc/sys/kernel/random/boot_id)"
      systemctl is-system-running --wait >/dev/null 2>&1 || true

      OUT_DIR="${bootMetricsDir}/''${BOOT_ID}"
      mkdir -p "''${OUT_DIR}"

      systemd-analyze time > "''${OUT_DIR}/time.txt" || true
      systemd-analyze blame > "''${OUT_DIR}/blame.txt" || true
      systemd-analyze critical-chain > "''${OUT_DIR}/critical-chain.txt" || true
      systemd-analyze plot > "''${OUT_DIR}/boot.svg" || true

      journalctl -b -p 0..3 > "''${OUT_DIR}/journal-errors.log" || true
      dmesg > "''${OUT_DIR}/dmesg.log"
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
      SystemMaxUse=50G
      SystemKeepFree=10G
      SystemMaxFileSize=200M
      SystemMaxFiles=0
      RuntimeMaxUse=1G
      SplitMode=uid
    '';

    systemd.services.capture-boot-metrics = {
      description = "Capture boot metrics and logs";
      wantedBy = [ "multi-user.target" ];
      after = [
        "multi-user.target"
        "systemd-journald.service"
      ];
      serviceConfig = {
        Type = "oneshot";
        ExecStart = "${captureBootMetrics}/bin/capture-boot-metrics";
      };
    };
  };
}
