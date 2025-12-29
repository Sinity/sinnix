{
  lib,
  config,
  pkgs,
  ...
}:
let
  cfg = config.sinnix.features.desktop.kdeconnect;
  user = config.sinnix.user.name;
in
{
  options.sinnix.features.desktop.kdeconnect = {
    enable = lib.mkEnableOption "KDE Connect";
  };

  config = lib.mkIf cfg.enable {
    home-manager.users.${user} = { pkgs, ... }: 
      let
        graphicalTarget = "graphical-session.target";
        baseGraphicalUnit = {
          After = [ graphicalTarget ];
          PartOf = [ graphicalTarget ];
        };
      in
      {
        systemd.user.services.kdeconnectd = {
          Unit = baseGraphicalUnit // {
            Description = "KDE Connect daemon";
          };
          Service = {
            Type = "dbus";
            BusName = "org.kde.kdeconnect";
            ExecStart = "${pkgs.kdePackages.kdeconnect-kde}/bin/kdeconnectd";
            Restart = "on-failure";
            RestartSec = 5;
          };
          Install.WantedBy = [ graphicalTarget ];
        };
      };
  };
}
