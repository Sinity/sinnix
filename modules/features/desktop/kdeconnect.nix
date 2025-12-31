{ mkFeatureModule, pkgs, config, ... }@args:
mkFeatureModule {
  path = [ "desktop" "kdeconnect" ];
  description = "KDE Connect integration";
  configFn =
    { config, pkgs, ... }:
    let
      user = config.sinnix.user.name;
      graphicalTarget = "graphical-session.target";
      baseGraphicalUnit = {
        After = [ graphicalTarget ];
        PartOf = [ graphicalTarget ];
      };
    in
    {
      home-manager.users.${user}.systemd.user.services.kdeconnectd = {
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
} args
