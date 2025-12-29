{
  lib,
  config,
  pkgs,
  ...
}:
let
  cfg = config.sinnix.features.desktop.activitywatch;
  user = config.sinnix.user.name;
in
{
  options.sinnix.features.desktop.activitywatch = {
    enable = lib.mkEnableOption "ActivityWatch Time Tracker";
  };

  config = lib.mkIf cfg.enable {
    home-manager.users.${user} = { pkgs, lib, ... }: 
      let
        graphicalTarget = "graphical-session.target";
        baseGraphicalUnit = {
          After = [ graphicalTarget ];
          PartOf = [ graphicalTarget ];
        };
      in
      {
        services.activitywatch = {
          enable = true;
          package = pkgs.aw-server-rust;
          watchers.awatcher = {
            package = pkgs.awatcher;
            settings = {
              idle-timeout-seconds = 60;
              poll-time-idle-seconds = 5;
              poll-time-window-seconds = 2;
            };
          };
        };

        systemd.user.services = {
          activitywatch-watcher-awatcher = {
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

        home.packages = with pkgs; [
          aw-watcher-window-wayland
          aw-watcher-afk
        ];
      };
  };
}
