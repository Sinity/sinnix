{
  lib,
  pkgs,
  mkFeatureModule,
  ...
}@args:
mkFeatureModule {
  path = [
    "desktop"
    "activitywatch"
  ];
  description = "ActivityWatch time tracker";
  extraOptions = {
    autoStart = lib.mkOption {
      type = lib.types.bool;
      default = true;
      description = "Start ActivityWatch automatically with the graphical session.";
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
    let
      nixosConfig = config;
      graphicalTarget = "graphical-session.target";
      baseGraphicalUnit = {
        After = [ graphicalTarget ];
        PartOf = [ graphicalTarget ];
      };
    in
    {
      sinnix.runtime.surfaces = lib.mkIf cfg.autoStart {
        activitywatch = {
          unit = "activitywatch.service";
          manager = "user";
          resourceClass = "background-maintenance";
          observe = {
            enable = true;
            restartable = true;
          };
          # Points DIRECTLY at AW's own SQLite DB in the persisted home dir,
          # which the standard backup pipeline already covers. Same pattern as
          # atuin's surface (modules/services/sinex/bridge.nix), which points
          # straight at history.db: consumers read the sqlite file, so no
          # conversion or rollup lane is needed.
          captures = [
            {
              name = "activitywatch";
              path = "/home/${config.sinnix.user.name}/.local/share/activitywatch/aw-server-rust/sqlite.db";
              eventDriven = true;
              staleAfterSeconds = 3600;
            }
          ];
        };
        activitywatch-watcher-awatcher = {
          unit = "activitywatch-watcher-awatcher.service";
          manager = "user";
          resourceClass = "background-maintenance";
          observe = {
            enable = true;
            restartable = true;
          };
        };
      };

      home-manager.users.${user} =
        { pkgs, lib, ... }:
        {
          # awatcher (Rust) handles both AFK and window tracking natively on
          # Wayland; aw-watcher-afk is X11-only.
          services.activitywatch = {
            enable = true;
            package = pkgs.aw-server-rust;
            watchers = {
              awatcher = {
                package = pkgs.awatcher;
                settings = {
                  idle-timeout-seconds = 60;
                  poll-time-idle-seconds = 5;
                  poll-time-window-seconds = 2;
                };
              };
            };
          };

          systemd.user.services.activitywatch = {
            Service = lib.sinnix.mkRuntimeServiceConfig {
              runtimeInventory = nixosConfig.sinnix.runtime.inventory;
              resourceClass = "background-maintenance";
              overrides = {
                MemoryHigh = "1G";
                MemoryMax = "2G";
              };
            };
            Install.WantedBy = lib.mkIf (!cfg.autoStart) (lib.mkForce [ ]);
          };

          systemd.user.services.activitywatch-watcher-awatcher = {
            Unit = baseGraphicalUnit // {
              Requisite = [ graphicalTarget ];
              PartOf = [ graphicalTarget ];
            };
            Service = {
              Restart = "on-failure";
              RestartSec = 5;
            };
            Install.WantedBy = lib.mkForce (lib.optionals cfg.autoStart [ graphicalTarget ]);
          };

        };
    };
} args
