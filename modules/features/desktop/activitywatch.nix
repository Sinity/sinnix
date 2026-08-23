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
          # Points directly at AW's own SQLite state, which the backup
          # pipeline already covers -- same pattern as atuin's surface.
          #
          # Watches the DB DIRECTORY, not sqlite.db: aw-server runs WAL mode,
          # so live writes land in -wal and leave sqlite.db's mtime stale until
          # an opportunistic checkpoint. Watching the file alone would measure
          # checkpoint cadence and call it capture health. The sentinel takes
          # the newest file under the path, so the directory reads whichever of
          # db/-wal/-shm was touched last.
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
        { pkgs, lib, config, ... }:
        {
          # awatcher (Rust) handles both AFK and window tracking natively on
          # Wayland; aw-watcher-afk is X11-only.
          services.activitywatch = {
            enable = true;
            package = pkgs.aw-server-rust;
            watchers = {
              awatcher = {
                package = pkgs.awatcher;
                # Without --config, awatcher reads ~/.config/awatcher/config.toml
                # (a stale 2024 file), not the file home-manager generates here —
                # pass the generated path explicitly so the declared settings are
                # authoritative. Keys live under the [awatcher] section per the
                # upstream FileConfig schema.
                extraOptions = [
                  "--config"
                  "${config.xdg.configHome}/activitywatch/awatcher/awatcher.toml"
                ];
                settings = {
                  awatcher = {
                    idle-timeout-seconds = 60;
                    poll-time-idle-seconds = 5;
                    poll-time-window-seconds = 2;
                    # Strip CLI-agent spinner glyphs (Claude Code half-disks,
                    # braille frames, ✳) from kitty titles: each animation tick
                    # otherwise defeats heartbeat merging and one agent session
                    # becomes thousands of near-zero-duration window events
                    # (93% of the 2026-08 window bucket was this churn).
                    filters = [
                      {
                        match-app-id = "kitty";
                        match-title = "[◐◑⠂⠐⠏⠸⠦⠴⠇⠧⠋⠼⠹⠙✳] (.*)";
                        replace-title = "$1";
                      }
                    ];
                  };
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
