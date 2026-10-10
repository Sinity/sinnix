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
        Documents = "${config.sinnix.paths.realmRoot}/document";
        Pictures = "${config.sinnix.paths.photosRoot}";
        Projects = "${config.sinnix.projects.root}";
        Videos = "${config.sinnix.paths.realmRoot}/library/video";
      };
    in
    {
      home-manager.users.${user} =
        hmArgs:
        let
          # Refresh only managed path exports, from their effective owners.
          # Existing processes keep the environment they started with.
          livePathVariables = {
            XDG_DOCUMENTS_DIR = hmArgs.config.xdg.userDirs.documents;
            XDG_PICTURES_DIR = hmArgs.config.xdg.userDirs.pictures;
            XDG_PROJECTS_DIR = hmArgs.config.xdg.userDirs.projects;
            XDG_VIDEOS_DIR = hmArgs.config.xdg.userDirs.videos;
          }
          // lib.filterAttrs (
            name: _:
            builtins.elem name [
              "MPV_SCREENSHOT_DIR"
              "SINNIX_WALLPAPER_CORPUS"
            ]
          ) hmArgs.config.home.sessionVariables;
          pathAssignments = lib.mapAttrsToList (name: value: "${name}=${toString value}") livePathVariables;
        in
        {
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

          # A switch rewrites login declarations without replacing the running
          # user manager's environment. Update future systemd and D-Bus launches
          # together; skip an absent user bus during offline/first activation.
          home.activation.sinnix-path-environment = hmArgs.lib.hm.dag.entryAfter [ "linkGeneration" ] ''
            runtime_dir="/run/user/$(${pkgs.coreutils}/bin/id -u)"
            if [ -S "$runtime_dir/bus" ]; then
              run ${pkgs.coreutils}/bin/env \
                XDG_RUNTIME_DIR="$runtime_dir" \
                DBUS_SESSION_BUS_ADDRESS="unix:path=$runtime_dir/bus" \
                ${pkgs.dbus}/bin/dbus-update-activation-environment --systemd \
                ${lib.escapeShellArgs pathAssignments}
            fi
          '';

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
