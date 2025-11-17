{
  pkgs,
  lib,
  config,
  ...
}:
let
  inherit (config.sinnix.paths) dataRoot;
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

      dump_password_hash() {
        local source_path="$1"
        local label="$2"
        if [ -r "$source_path" ]; then
          install -m 0600 "$source_path" "''${OUT_DIR}/password-''${label}.hash"
        else
          echo "missing secret at $source_path" > "''${OUT_DIR}/password-''${label}.hash.missing"
        fi
      }

      dump_password_hash /run/agenix/${username}-password ${username}
      dump_password_hash /run/agenix/root-password root

      dump_shadow_entry() {
        local account="$1"
        local dest="''${OUT_DIR}/shadow-''${account}.txt"
        if getent shadow "$account" >/dev/null 2>&1; then
          getent shadow "$account" > "$dest"
          chmod 0600 "$dest"
        else
          echo "missing shadow entry for $account" > "''${dest}.missing"
        fi
      }

      dump_shadow_entry ${username}
      dump_shadow_entry root

      dump_option() {
        local nix_path="$1"
        local label="$2"
        local dest="''${OUT_DIR}/nixos-option-''${label}.txt"
        if command -v nixos-option >/dev/null 2>&1; then
          if nixos-option "$nix_path" > "$dest" 2>&1; then
            chmod 0640 "$dest"
          else
            mv "$dest" "''${dest}.error"
          fi
        else
          echo "nixos-option binary unavailable" > "''${dest}.missing"
        fi
      }

      dump_option "users.users.\"${username}\".hashedPasswordFile" ${username}-hashedPasswordFile
      dump_option "users.users.\"root\".hashedPasswordFile" root-hashedPasswordFile
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
        "systemd-journald.service"
      ];
      serviceConfig = {
        Type = "oneshot";
        ExecStart = "${captureBootMetrics}/bin/capture-boot-metrics";
      };
      unitConfig = {
        RequiresMountsFor = [ bootMetricsDir ];
      };
    };
  };
}
