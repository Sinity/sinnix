{ lib, pkgs, mkFeatureModule, ... }@args:
mkFeatureModule {
  path = [ "desktop" "activitywatch" ];
  description = "ActivityWatch time tracker";
  configFn =
    { config, pkgs, lib, ... }:
    let
      user = config.sinnix.user.name;
      graphicalTarget = "graphical-session.target";
      baseGraphicalUnit = {
        After = [ graphicalTarget ];
        PartOf = [ graphicalTarget ];
      };
    in
    {
      home-manager.users.${user} = { pkgs, lib, ... }: {
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

            "aw-watcher-window-wayland" = {
              package = pkgs.aw-watcher-window-wayland;
              settings = {
                poll-time-window-seconds = 1;
              };
            };

            "aw-watcher-afk" = {
              package = pkgs.aw-watcher-afk;
              settings = {
                timeout-seconds = 300;
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
