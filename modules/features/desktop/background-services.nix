{ mkFeatureModule, lib, pkgs, ... }@args:
mkFeatureModule {
  path = [ "desktop" "background-services" ];
  description = "Desktop background services (tray, clipboard, polkit)";
  configFn =
    { config, pkgs, lib, ... }:
    let
      user = config.sinnix.user.name;
      graphicalTarget = "graphical-session.target";
      baseGraphicalUnit = {
        After = [ graphicalTarget ];
        PartOf = [ graphicalTarget ];
      };
      mkService =
        exec: desc: {
          Unit = baseGraphicalUnit // { Description = desc; };
          Service = {
            Type = "simple";
            ExecStart = exec;
            Restart = "on-failure";
            RestartSec = 1;
          };
          Install.WantedBy = [ graphicalTarget ];
        };
    in
    {
      home-manager.users.${user}.systemd.user.services = {
        wl-clip-persist = mkService "${pkgs.wl-clip-persist}/bin/wl-clip-persist --clipboard both" "Wayland clipboard persistence";
        nm-applet = mkService "${pkgs.networkmanagerapplet}/bin/nm-applet" "NetworkManager applet";
        polkit-gnome-authentication-agent-1 =
          mkService "${pkgs.polkit_gnome}/libexec/polkit-gnome-authentication-agent-1" "polkit-gnome-authentication-agent-1";
        blueman-applet = mkService "${pkgs.blueman}/bin/blueman-applet" "Blueman applet";
      };
    };
} args
