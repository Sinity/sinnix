# Periodic agent health check — runs agent-verify every 15 minutes,
# widget reflects fresh health status.
#
# Disabled by default. Enable by setting
#   sinnix.features.desktop.agentVerifyTimer.enable = true;
# in the host config.
{
  mkFeatureModule,
  pkgs,
  lib,
  ...
}@args:
mkFeatureModule {
  path = [
    "desktop"
    "agentVerifyTimer"
  ];
  description = "Periodic agent-verify health check (feeds waybar agent widget)";
  enableDefault = false;
  extraOptions = {
    interval = lib.mkOption {
      type = lib.types.str;
      default = "15min";
      description = "systemd OnCalendar or OnUnitActiveSec interval between verify runs.";
    };
  };
  configFn =
    {
      config,
      pkgs,
      lib,
      user,
      cfg,
      ...
    }:
    {
      home-manager.users.${user} =
        { lib, ... }:
        {
          systemd.user.services.agent-verify = {
            Unit = {
              Description = "Sinnix agent-verify health check";
            };
            Service = {
              Type = "oneshot";
              ExecStart = "${pkgs.writeShellScript "agent-verify-run" ''
                set -euo pipefail
                if [ -x /home/sinity/.local/bin/agent-verify ]; then
                  /home/sinity/.local/bin/agent-verify --quiet >/dev/null 2>&1 || true
                fi
              ''}";
            };
          };

          systemd.user.timers.agent-verify = {
            Unit = {
              Description = "Run agent-verify every ${cfg.interval}";
            };
            Timer = {
              OnBootSec = "2min";
              OnUnitActiveSec = cfg.interval;
              Persistent = true;
              Unit = "agent-verify.service";
            };
            Install.WantedBy = [ "timers.target" ];
          };
        };
    };
} args
