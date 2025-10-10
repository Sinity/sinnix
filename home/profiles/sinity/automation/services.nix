{ pkgs, ... }:
{
  services.activitywatch = {
    enable = true;
    package = pkgs.aw-server-rust;
    watchers.awatcher = {
      package = pkgs.awatcher;
      settings = {
        idle-timeout-seconds = 60;
        poll-time-idle-seconds = 1;
        poll-time-window-seconds = 1;
      };
    };
  };

  systemd.user.services.activitywatch-watcher-awatcher =
    let
      target = "graphical-session.target";
    in
    {
      Unit = {
        After = [ target ];
        Requisite = [ target ];
        PartOf = [ target ];
      };
      Install.WantedBy = [ target ];
    };

  home.packages = with pkgs; [
    aw-watcher-window-wayland
    aw-watcher-afk
  ];
}
