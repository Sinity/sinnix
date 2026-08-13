# Periodic kitty terminal scrollback capture
#
# A systemd --user timer drives scripts/kitty-scrollback-capture (full-ANSI
# scrollback dump via `kitty @ get-text`) on a fixed cadence, giving the
# kitty-scrollback lane a real owning unit the health sentinel can track.
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
  capturesRoot = config.sinnix.paths.capturesRoot;
  scrollbackDir = "${capturesRoot}/kitty-scrollback";
in
mkServiceModule {
  name = "capture-kitty-scrollback";
  description = "Periodic full-ANSI kitty terminal scrollback capture";
  extraOptions = {
    intervalMinutes = lib.mkOption {
      type = lib.types.ints.positive;
      default = 30;
      description = "Minutes between scrollback capture runs.";
    };
  };
  surface = {
    unit = "sinnix-capture-kitty-scrollback.service";
    manager = "user";
    resourceClass = "capture-runtime";
    observe = {
      enable = true;
      restartable = false;
    };
    captures = [
      {
        name = "kitty-scrollback";
        path = scrollbackDir;
        eventDriven = true;
        # No kitty windows open for a full day is itself a real signal
        # (host idle/away), not just a quiet capture lane.
        staleAfterSeconds = 86400;
      }
    ];
  };
  configFn =
    { cfg, config, ... }:
    {
      systemd.tmpfiles.rules = [
        "d ${scrollbackDir} 0755 ${username} users -"
      ];

      home-manager.users.${username} = {
        systemd.user.services.sinnix-capture-kitty-scrollback = {
          Unit = {
            Description = "Full-ANSI kitty terminal scrollback capture";
            After = [ "graphical-session.target" ];
          };
          Service = lib.sinnix.mkRuntimeServiceConfig {
            runtimeInventory = config.sinnix.runtime.inventory;
            unit = "sinnix-capture-kitty-scrollback.service";
            overrides = {
              Type = "oneshot";
              Environment = "KITTY_SCROLLBACK_DIR=${scrollbackDir}";
              ExecStart = "${scriptPkgs.kitty-scrollback-capture}/bin/kitty-scrollback-capture";
              NoNewPrivileges = true;
              ProtectSystem = "strict";
              ProtectHome = "read-only";
              ReadWritePaths = [ scrollbackDir ];
            };
          };
        };

        systemd.user.timers.sinnix-capture-kitty-scrollback = {
          Unit.Description = "Periodic trigger for kitty scrollback capture";
          Timer = {
            OnUnitActiveSec = "${toString cfg.intervalMinutes}min";
            OnStartupSec = "2min";
            Persistent = true;
          };
          Install.WantedBy = [ "timers.target" ];
        };
      };
    };
} args
