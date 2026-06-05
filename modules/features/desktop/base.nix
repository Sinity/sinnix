# Core Desktop Foundation
#
# Provides:
# - Systemd-managed user services (network/bluetooth applets, clipboard)
# - Wayland session environment and auto-start logic
#
# Launcher, notifications, and the polkit agent are owned by Noctalia
# (see noctalia.nix); clipboard stays here (clipse).
{
  mkFeatureModule,
  lib,
  pkgs,
  ...
}@args:
mkFeatureModule {
  path = [
    "desktop"
    "base"
  ];
  description = "Essential desktop background services and session logic";
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
    in
    {
      home-manager.users.${user} = {
        home.packages = with pkgs; [
          clipse
          wl-clipboard
          wtype
        ];

        # Clipboard
        services.clipse = {
          enable = true;
          historySize = 99999;
          allowDuplicates = false;
          systemdTarget = graphicalTarget;
          imageDisplay = {
            type = "kitty";
            scaleX = 9;
            scaleY = 9;
            heightCut = 2;
          };
        };

        # Notifications, launcher, and OSD are provided by Noctalia.

        xdg.userDirs = {
          enable = true;
          createDirectories = true;
          setSessionVariables = true;
          download = "${config.sinnix.paths.realmRoot}/inbox/download";
        };

        # Background Services
        systemd.user.services = {
          wl-clip-persist = lib.sinnix.systemd.mkGraphicalUserService {
            description = "Wayland clipboard persistence";
            execStart = "${pkgs.wl-clip-persist}/bin/wl-clip-persist --clipboard both";
          };
          nm-applet = lib.sinnix.systemd.mkGraphicalUserService {
            description = "NetworkManager applet";
            execStart = "${pkgs.networkmanagerapplet}/bin/nm-applet";
          };
          # Polkit authentication agent is provided by Noctalia's polkit-agent
          # plugin; running a second agent (polkit-gnome) would conflict.
          blueman-applet = lib.sinnix.systemd.mkGraphicalUserService {
            description = "Blueman applet";
            execStart = "${pkgs.blueman}/bin/blueman-applet";
          };
        };

        home.sessionVariables = {
          XDG_SESSION_TYPE = "wayland";
          QT_QPA_PLATFORM = "wayland";
          SDL_VIDEODRIVER = "wayland,x11";
          CLUTTER_BACKEND = "wayland";
        };
      };
    };
} args
