{
  lib,
  config,
  pkgs,
  ...
}:
let
  cfg = config.sinnix.features.desktop.background-services;
  user = config.sinnix.user.name;
in
{
  options.sinnix.features.desktop.background-services = {
    enable = lib.mkEnableOption "Desktop Background Services (Tray, Clipboard, Polkit)";
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
        systemd.user.services = {
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
      };
  };
}
