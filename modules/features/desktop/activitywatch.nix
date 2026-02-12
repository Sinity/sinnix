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
  configFn =
    {
      config,
      pkgs,
      lib,
      user,
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

          systemd.user.services.activitywatch-watcher-awatcher = {
            Unit = baseGraphicalUnit // {
              Requisite = [ graphicalTarget ];
              PartOf = [ graphicalTarget ];
            };
            Service = {
              Restart = "on-failure";
              RestartSec = 5;
            };
            Install.WantedBy = [ graphicalTarget ];
          };

        };
    };
} args
