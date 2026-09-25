# Core desktop foundation: systemd-managed user services (network/bluetooth
# applets, clipboard persistence) and the Wayland session environment.
#
# Launcher, notifications, clipboard history, and the polkit agent are owned
# by Noctalia (see noctalia.nix).
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
      # One declaration serves both XDG defaults and conventional home paths.
      # Compatibility links never become a second copy of the personal corpus.
      corpusEntrances = {
        Documents = "${config.sinnix.paths.realmRoot}/documents";
        Pictures = "${config.sinnix.paths.realmRoot}/photos";
        Projects = "${config.sinnix.paths.realmRoot}/project";
        Videos = "${config.sinnix.paths.realmRoot}/library/videos";
      };
    in
    {
      home-manager.users.${user} = hmArgs: {
        home.packages = with pkgs; [
          wl-clipboard
          wtype
        ];

        # Notifications, launcher, and OSD are provided by Noctalia.

        xdg.userDirs = {
          enable = true;
          createDirectories = true;
          setSessionVariables = true;
          download = "${config.sinnix.paths.realmRoot}/inbox/download";
          documents = corpusEntrances.Documents;
          pictures = corpusEntrances.Pictures;
          projects = corpusEntrances.Projects;
          videos = corpusEntrances.Videos;
        };

        # Home Manager refuses conflicting populated paths: no force flag,
        # recursive move, or implicit migration belongs to this declaration.
        home.file = lib.mapAttrs (_: target: {
          source = hmArgs.config.lib.file.mkOutOfStoreSymlink target;
        }) corpusEntrances;

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
