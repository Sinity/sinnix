# sentinel: Self-monitoring NixOS health daemon
#
# Reads /etc/sinnix/health-policy.json (auto-derived from NixOS config by
# introspection.nix) and periodically verifies that all declared services,
# captures, mounts, and backups are healthy.
#
# Actions:
# - Writes /run/sinnix/health.json (machine-readable, consumed by waybar)
# - Restarts failed restartable sinnix services (configurable)
# - Sends fnott desktop notifications for state transitions
# - Logs events to /var/log/sinnix-sentinel/events.jsonl (sinex-ready)
#
# The health policy is auto-derived: enabling a sinnix service automatically
# creates its health check. See modules/introspection.nix for the mapping.
{
  mkServiceModule,
  lib,
  pkgs,
  config,
  inputs,
  ...
}@args:
let
  username = config.sinnix.user.name;
  sentinelPkg = inputs.self.packages.${pkgs.stdenv.hostPlatform.system}.sinnix-sentinel;
in
mkServiceModule {
  name = "sentinel";
  description = "System health sentinel with auto-derived checks";
  extraOptions = {
    intervalSec = lib.mkOption {
      type = lib.types.int;
      default = 60;
      description = "Interval between health checks in seconds.";
    };
    enableCorrectiveActions = lib.mkOption {
      type = lib.types.bool;
      default = true;
      description = "Whether sentinel can restart failed services.";
    };
    enableNotifications = lib.mkOption {
      type = lib.types.bool;
      default = true;
      description = "Whether sentinel sends desktop notifications.";
    };
  };
  configFn =
    { cfg, pkgs, ... }:
    let
      hardenedConfig = lib.sinnix.systemd.mkHardenedService {
        level = "moderate";
        readWritePaths = [
          "/run/sinnix"
          "/var/log/sinnix-sentinel"
        ];
        readOnlyPaths = [
          "/etc/sinnix"
          "/proc"
          "/sys"
          "/realm"
          "/outer-realm"
          "/neo-outer-realm"
          "/.snapshots"
          "/var/.snapshots"
        ];
      };
    in
    {
      environment.systemPackages = [ sentinelPkg ];

      systemd.tmpfiles.rules = [
        "d /run/sinnix 0755 root root -"
        "d /var/log/sinnix-sentinel 0750 root root 30d"
      ];

      systemd.services.sinnix-sentinel = {
        description = "sinnix sentinel - System health monitor";
        after = [
          "network.target"
          "local-fs.target"
        ];
        # Sentinel needs access to systemctl for service checks and restarts
        # Plus tools for hardware and backup monitoring
        path = with pkgs; [
          systemd
          borgbackup
          jq
          smartmontools
        ];

        environment = {
          SINNIX_CORRECTIVE_ACTIONS = if cfg.enableCorrectiveActions then "true" else "false";
          SINNIX_NOTIFICATIONS = if cfg.enableNotifications then "true" else "false";
        };

        serviceConfig = hardenedConfig // {
          Type = "oneshot";
          ExecStart = "${sentinelPkg}/bin/sinnix-sentinel";
          # Don't mark timer as failed if health checks find issues
          # (script exits 1 on fail, but that's informational)
          SuccessExitStatus = "0 1";
          Nice = 19;
          IOSchedulingClass = "idle";
        };
      };

      systemd.timers.sinnix-sentinel = {
        description = "sinnix sentinel - Periodic health checks";
        wantedBy = [ "timers.target" ];
        timerConfig = {
          OnBootSec = "30s";
          OnUnitActiveSec = "${toString cfg.intervalSec}s";
          AccuracySec = "5s";
          RandomizedDelaySec = "5s";
        };
      };
    };
} args
