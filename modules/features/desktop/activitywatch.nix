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
      graphicalTarget = "graphical-session.target";
      baseGraphicalUnit = {
        After = [ graphicalTarget ];
        PartOf = [ graphicalTarget ];
      };
    in
    {
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
            Service = {
              Nice = 10;
              IOSchedulingClass = "idle";
              IOWeight = 10;
              MemoryHigh = "1G";
              MemoryMax = "2G";
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
