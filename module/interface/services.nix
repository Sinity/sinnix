# Desktop User Services Configuration
# Systemd user services for desktop functionality

{ pkgs, ... }:
{
  config = {
    home-manager.users.sinity = {
      # UWSM systemd services for autostart applications
      systemd.user.services = {
        wl-clip-persist = {
          Unit = {
            Description = "Wayland clipboard persistence";
            After = [ "graphical-session.target" ];
            PartOf = [ "graphical-session.target" ];
          };
          Service = {
            Type = "simple";
            ExecStart = "${pkgs.wl-clip-persist}/bin/wl-clip-persist --clipboard both";
            Restart = "on-failure";
            RestartSec = 1;
          };
          Install = {
            WantedBy = [ "graphical-session.target" ];
          };
        };

        nm-applet = {
          Unit = {
            Description = "NetworkManager applet";
            After = [ "graphical-session.target" ];
            PartOf = [ "graphical-session.target" ];
          };
          Service = {
            Type = "simple";
            ExecStart = "${pkgs.networkmanagerapplet}/bin/nm-applet";
            Restart = "on-failure";
            RestartSec = 1;
          };
          Install = {
            WantedBy = [ "graphical-session.target" ];
          };
        };

        polkit-gnome-authentication-agent-1 = {
          Unit = {
            Description = "polkit-gnome-authentication-agent-1";
            After = [ "graphical-session.target" ];
            PartOf = [ "graphical-session.target" ];
          };
          Service = {
            Type = "simple";
            ExecStart = "${pkgs.polkit_gnome}/libexec/polkit-gnome-authentication-agent-1";
            Restart = "on-failure";
            RestartSec = 1;
          };
          Install = {
            WantedBy = [ "graphical-session.target" ];
          };
        };

        blueman-applet = {
          Unit = {
            Description = "Blueman applet";
            After = [ "graphical-session.target" ];
            PartOf = [ "graphical-session.target" ];
          };
          Service = {
            Type = "simple";
            ExecStart = "${pkgs.blueman}/bin/blueman-applet";
            Restart = "on-failure";
            RestartSec = 1;
          };
          Install = {
            WantedBy = [ "graphical-session.target" ];
          };
        };
      };
    };
  };
}
