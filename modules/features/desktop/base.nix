# Core desktop foundation: systemd-managed user services (network/bluetooth
# applets, clipboard) and the Wayland session environment.
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

        services.clipse = {
          enable = true;
          systemdTarget = graphicalTarget;
          settings = {
            maxHistory = 99999;
            allowDuplicates = false;
            imageDisplay = {
              type = "kitty";
              scaleX = 9;
              scaleY = 9;
              heightCut = 2;
            };
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
        systemd.user.services =
          let
            # `clipse -listen` forks one `wl-paste --watch` per MIME type and
            # exits, so the Home Manager oneshot tracks nothing and a dead
            # watcher is never restarted. Run each watcher in the foreground.
            clipseWatcher =
              mime:
              lib.sinnix.systemd.mkGraphicalUserService {
                description = "clipse ${mime} clipboard watcher";
                execStart = "${lib.getExe' pkgs.wl-clipboard "wl-paste"} --type ${mime} --watch ${lib.getExe pkgs.clipse} --wl-store";
                target = graphicalTarget;
              };
          in
          {
            clipse = lib.mkForce (clipseWatcher "text");
            clipse-image = clipseWatcher "image/png";
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
