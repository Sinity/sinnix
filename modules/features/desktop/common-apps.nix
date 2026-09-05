# Common desktop applications, and the GUI file-navigation surface.
#
# File navigation has two routes: Yazi in a terminal, and one GUI manager
# declared by `fileNavigation`. The manager previews only what gdk-pixbuf
# decodes on its own, so every other content type needs a package that
# registers a `share/thumbnailers/*.thumbnailer` entry -- that is what
# `previewHelpers` is. `places` is the sidebar, rendered once as GTK
# bookmarks and read by every GTK file chooser as well.
#
# docs/desktop-file-navigation.md records the measurements behind the choice.
{
  mkFeatureModule,
  pkgs,
  lib,
  helpers,
  inputs,
  ...
}@args:
mkFeatureModule {
  path = [
    "desktop"
    "common-apps"
  ];
  description = "Common desktop applications and settings";
  docs = "docs/desktop-file-navigation.md";
  extraOptions = {
    fileNavigation = {
      manager = lib.mkOption {
        type = lib.types.package;
        default = pkgs.nautilus;
        description = "GUI file manager that owns folder opening and place navigation.";
      };
      managerDesktopEntry = lib.mkOption {
        type = lib.types.str;
        default = "org.gnome.Nautilus.desktop";
        description = "Desktop entry shipped by `manager`, declared as the inode/directory handler.";
      };
      previewHelpers = lib.mkOption {
        type = lib.types.listOf lib.types.package;
        default = [
          pkgs.ffmpegthumbnailer
          pkgs.evince
        ];
        description = ''
          Packages that register `share/thumbnailers` entries. Each entry must
          cover a content type the manager cannot render itself; dropping one
          removes previews for that type.
        '';
      };
      places = lib.mkOption {
        type = lib.types.listOf (
          lib.types.submodule {
            options = {
              name = lib.mkOption {
                type = lib.types.str;
                description = "Sidebar label.";
              };
              path = lib.mkOption {
                type = lib.types.str;
                description = "Absolute directory the label opens.";
              };
            };
          }
        );
        default = [ ];
        description = ''
          Frequent locations, in sidebar order. Every entry must come from a
          declared root (`sinnix.paths`, `sinnix.projects`, XDG user dirs) so
          the sidebar cannot drift from the filesystem layout.
        '';
      };
    };
  };
  meta.dotfiles.configFile = {
    "yazi/opener.toml" = {
      source = "yazi/opener.toml";
      force = true;
    };
    "yazi/yazi.toml" = {
      source = "yazi/yazi.toml";
      force = true;
    };
    "yazi/keymap.toml" = {
      source = "yazi/keymap.toml";
      force = true;
    };
    "yazi/plugins/sinnix-video-preview.yazi/main.lua" = {
      source = "yazi/plugins/sinnix-video-preview.yazi/main.lua";
      force = true;
    };
    "audacity/audacity.cfg" = "audacity/audacity.cfg";
  };
  configFn =
    {
      config,
      helpers,
      user,
      cfg,
      lib,
      pkgs,
      ...
    }:
    let
      scriptPkgs = helpers.mkSinnixPackagesFor pkgs;
      nav = cfg.fileNavigation;
      paths = config.sinnix.paths;
    in
    {
      sinnix.features.desktop.common-apps.fileNavigation.places = lib.mkDefault [
        {
          name = "Projects";
          path = config.sinnix.projects.root;
        }
        {
          name = "Sinnix";
          path = paths.projectRoot;
        }
        {
          name = "Data lake";
          path = paths.dataRoot;
        }
        {
          name = "State";
          path = paths.stateRoot;
        }
        {
          name = "Media";
          path = paths.mediaRoot;
        }
        {
          name = "Downloads";
          path = config.home-manager.users.${user}.xdg.userDirs.download;
        }
        {
          name = "Torrent inbox";
          path = paths.torrentInbox;
        }
      ];

      home-manager.users.${user} =
        {
          pkgs,
          lib,
          config,
          ...
        }:
        {
          home.packages = [
            nav.manager
          ]
          ++ nav.previewHelpers
          ++ (with pkgs; [
            tremotesf
            transmission-remote-gtk
            pwvucontrol
            blueman
            weechat
            solaar
            imgur-screenshot
            aria2
            lnch
            libnotify
            scriptPkgs.chatgpt-app
            scriptPkgs.media-preview-cache
          ]);

          # One bookmarks file serves the manager's sidebar and every GTK file
          # chooser, including the portal's.
          gtk.gtk3.bookmarks = map (place: "file://${place.path} ${place.name}") nav.places;

          home.file = {
            ".local/bin/imgur-screenshot" = {
              text = ''
                #!/usr/bin/env bash
                set -euo pipefail

                NO_NOTIFY_DIR="$HOME/.local/lib/imgur-screenshot/no-notify"
                if [ -d "$NO_NOTIFY_DIR" ]; then
                  export PATH="$NO_NOTIFY_DIR:$PATH"
                fi

                exec "${lib.getExe pkgs.imgur-screenshot}" "$@"
              '';
              executable = true;
            };
            ".local/lib/imgur-screenshot/no-notify/notify-send" = {
              text = ''
                #!/usr/bin/env bash
                set -euo pipefail

                # Silence notifications for imgur-screenshot to avoid DBus errors.
                exit 0
              '';
              executable = true;
            };
          };

          xdg = {
            configFile = {
              "imgur-screenshot/settings.conf".text = ''
                OPEN="false"
                EDIT="false"
                CHECK_UPDATE="false"
              '';
            };
          };
        };
    };
} args
