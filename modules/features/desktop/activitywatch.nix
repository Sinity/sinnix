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
          # Points DIRECTLY at AW's own SQLite DB (persisted home dir,
          # already covered by the standard backup pipeline -- confirmed
          # 2026-08-12, .local/share/activitywatch carries no backup
          # exclude) -- same pattern as atuin's surface
          # (modules/services/sinex/bridge.nix), which points straight at
          # atuin's history.db rather than rolling it into a converted
          # copy. An earlier pass here built a separate capture-aw-rollup
          # lane (incremental REST poll -> JSONL) to fix the stale-surface
          # bug; that was over-engineered for what the bug actually
          # needed -- staleness visibility, not a format conversion durability
          # was already covered by the backup pipeline, and lynchpin/any
          # consumer can read AW's sqlite directly the same way it already
          # reads atuin's. Retired per operator correction 2026-08-12.
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
          # awatcher (Rust) handles both AFK and window tracking natively on Wayland
          # Replaces legacy aw-watcher-afk (X11-only) and aw-watcher-window-wayland
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
