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
          # Points DIRECTLY at AW's own SQLite state in the persisted home dir,
          # which the standard backup pipeline already covers. Same pattern as
          # atuin's surface (modules/services/sinex/bridge.nix), which points
          # straight at history.db: consumers read the sqlite file, so no
          # conversion or rollup lane is needed.
          #
          # The lane watches the DB DIRECTORY, not sqlite.db itself. aw-server
          # runs the database in WAL mode, so a live write lands in
          # sqlite.db-wal and leaves sqlite.db's mtime untouched until the next
          # checkpoint -- which is opportunistic, not scheduled. Watching the
          # file alone therefore measures checkpoint cadence and calls it
          # capture health (observed 2026-08-14: "quiet for over an hour" paged
          # while aw-server was serving events seconds old, sqlite.db 5 min
          # behind sqlite.db-wal). The sentinel takes the NEWEST file under the
          # path, so the directory reads whichever of db/-wal/-shm the server
          # touched last -- the honest witness that AW is still writing.
          captures = [
            {
              name = "activitywatch";
              path = "/home/${config.sinnix.user.name}/.local/share/activitywatch/aw-server-rust";
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
