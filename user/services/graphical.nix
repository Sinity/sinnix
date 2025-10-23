{ pkgs, lib, ... }:
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
        # Allow a little more than the default 1s to reduce transient timeouts.
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

    wl-clip-persist = {
      Unit = baseGraphicalUnit // {
        Description = "Wayland clipboard persistence";
      };
      Service = {
        Type = "simple";
        ExecStart = "${pkgs.wl-clip-persist}/bin/wl-clip-persist --clipboard both";
        Restart = "on-failure";
        RestartSec = 1;
      };
      Install.WantedBy = [ graphicalTarget ];
    };

    nm-applet = {
      Unit = baseGraphicalUnit // {
        Description = "NetworkManager applet";
      };
      Service = {
        Type = "simple";
        ExecStart = "${pkgs.networkmanagerapplet}/bin/nm-applet";
        Restart = "on-failure";
        RestartSec = 1;
      };
      Install.WantedBy = [ graphicalTarget ];
    };

    polkit-gnome-authentication-agent-1 = {
      Unit = baseGraphicalUnit // {
        Description = "polkit-gnome-authentication-agent-1";
      };
      Service = {
        Type = "simple";
        ExecStart = "${pkgs.polkit_gnome}/libexec/polkit-gnome-authentication-agent-1";
        Restart = "on-failure";
        RestartSec = 1;
      };
      Install.WantedBy = [ graphicalTarget ];
    };

    blueman-applet = {
      Unit = baseGraphicalUnit // {
        Description = "Blueman applet";
      };
      Service = {
        Type = "simple";
        ExecStart = "${pkgs.blueman}/bin/blueman-applet";
        Restart = "on-failure";
        RestartSec = 1;
      };
      Install.WantedBy = [ graphicalTarget ];
    };
  };

  home.packages = lib.mkBefore (
    with pkgs;
    [
      aw-watcher-window-wayland
      aw-watcher-afk
    ]
  );
}
