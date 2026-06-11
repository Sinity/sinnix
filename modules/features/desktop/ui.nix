# System-wide UI theme configuration
#
# NOCTALIA MANAGES:
#   - Shell, wallpaper, lock/OSD/launcher/notifications
#   - Live wallpaper-derived app templates for Kitty, GTK, Qt, Hyprland,
#     Zed, Neovim, and Yazi where native templates are available
#
# STYLIX MANAGES:
#   - Fonts, cursor, and static base16 fallback colors for apps that do not yet
#     have a safe Noctalia template path.
#
# Wallpaper display and the live shell palette are Noctalia's (noctalia.nix);
# stylix does NOT run hyprpaper (disabled below) so the two do not fight over
# wallpaper ownership.
#
# To disable stylix for specific apps:
#   stylix.targets.<app>.enable = false;
{
  mkFeatureModule,
  pkgs,
  inputs,
  lib,
  ...
}@args:
mkFeatureModule {
  path = [
    "desktop"
    "ui"
  ];
  description = "Graphical User Interface Stack";
  configFn =
    {
      config,
      pkgs,
      lib,
      inputs,
      ...
    }:
    let
      stylixFontSpec = {
        monospace = {
          package = pkgs.nerd-fonts.sauce-code-pro;
          name = "SauceCodePro Nerd Font Mono";
        };
        sansSerif = {
          package = pkgs.liberation_ttf;
          name = "Liberation Sans";
        };
        serif = {
          package = pkgs.liberation_ttf;
          name = "Liberation Serif";
        };
        emoji = {
          package = pkgs.noto-fonts-color-emoji;
          name = "Noto Color Emoji";
        };
      };

      fontSizes = {
        applications = 16;
        desktop = 16;
        popups = 16;
        terminal = 16;
      };

      primaryFontPackages = lib.filter (pkg: pkg != null) (
        map (name: (lib.getAttr name stylixFontSpec).package) [
          "monospace"
          "sansSerif"
          "serif"
          "emoji"
        ]
      );
      fallbackFontPackages = [
        pkgs.noto-fonts
        pkgs.dejavu_fonts
      ];
      allFontPackages = lib.unique (primaryFontPackages ++ fallbackFontPackages);

      monospaceName = stylixFontSpec.monospace.name;
      sansName = stylixFontSpec.sansSerif.name;
      serifName = stylixFontSpec.serif.name;
    in
    {
      home-manager.sharedModules = lib.singleton {
        disabledModules = [ "${inputs.stylix}/modules/opencode/hm.nix" ];
      };

      home-manager.users.${config.sinnix.user.name} = {
        gtk.gtk4.theme = lib.mkDefault null;

        # Noctalia owns the displayed wallpaper and live palette, so Stylix's
        # wallpaper setter and generated app color surfaces must stay off.
        stylix.targets = {
          gtk.enable = lib.mkForce false;
          hyprpaper.enable = lib.mkForce false;
        };

        # Force unset portal env var in all shells (prevents stale session vars)
        programs.zsh.initContent = lib.mkBefore ''
          unset NIXOS_XDG_OPEN_USE_PORTAL
        '';

        # Keep portal DBus activation files in the system profile only.
        # Hyprland's Home Manager module enables xdg.portal by default, which
        # duplicates the same service names under /etc/profiles/per-user and
        # makes dbus-broker emit duplicate-name warnings on every reload.
        xdg.portal.enable = lib.mkForce false;
      };

      stylix = {
        enable = true;
        # Static fallback only. Noctalia owns live wallpaper-derived coloring;
        # app-specific colors should use Noctalia-generated templates where
        # possible instead of adding new Stylix targets.
        base16Scheme = "${pkgs.base16-schemes}/share/themes/gruvbox-dark-medium.yaml";
        image = pkgs.writeText "stylix-fallback.svg" ''
          <svg xmlns="http://www.w3.org/2000/svg" width="1" height="1">
            <rect width="1" height="1" fill="#282828" />
          </svg>
        '';

        fonts = stylixFontSpec // {
          sizes = fontSizes;
        };

        cursor = {
          package = pkgs.bibata-cursors;
          name = "Bibata-Modern-Ice";
          size = 24;
        };

        opacity = {
          applications = 1.0;
          desktop = 1.0;
          popups = 1.0;
          terminal = 0.9;
        };

        polarity = "dark";
      };

      xdg.portal = {
        enable = true;
        # mkForce: Disable wlr portal in favor of hyprland-specific portal (better screenshare)
        wlr.enable = lib.mkForce false;
        # xdgOpenUsePortal forces portal dialogs even with default apps - disabled for better UX
        # NOTE: Must use mkForce because something else sets it to true
        xdgOpenUsePortal = lib.mkForce false;
        extraPortals = lib.mkForce [
          pkgs.xdg-desktop-portal-hyprland
          pkgs.xdg-desktop-portal-gtk
        ];
        config = {
          common = {
            default = [
              "gtk"
              "hyprland"
            ];
          };
          hyprland = {
            default = [
              "gtk"
              "hyprland"
            ];
            "org.freedesktop.impl.portal.ScreenCast" = [ "hyprland" ];
            "org.freedesktop.impl.portal.Screenshot" = [ "hyprland" ];
            "org.freedesktop.impl.portal.Secret" = [ "gnome-keyring" ];
          };
        };
      };

      systemd.user.services."xdg-desktop-portal".environment = {
        XDG_DESKTOP_PORTAL_DIR = "/run/current-system/sw/share/xdg-desktop-portal/portals";
      };

      fonts = {
        packages = allFontPackages;

        fontconfig = {
          enable = true;
          localConf = ''
            <?xml version="1.0"?>
            <!DOCTYPE fontconfig SYSTEM "fonts.dtd">
            <fontconfig>
              <selectfont>
                <rejectfont><glob>*.woff</glob></rejectfont>
                <rejectfont><glob>*.woff2</glob></rejectfont>
              </selectfont>

              <alias>
                <family>sans-serif</family>
                <prefer>
                  <family>${sansName}</family>
                  <family>DejaVu Sans</family>
                </prefer>
              </alias>
              <alias>
                <family>serif</family>
                <prefer>
                  <family>${serifName}</family>
                  <family>DejaVu Serif</family>
                </prefer>
              </alias>
              <alias>
                <family>monospace</family>
                <prefer>
                  <family>${monospaceName}</family>
                  <family>DejaVu Sans Mono</family>
                  <family>Liberation Mono</family>
                </prefer>
              </alias>
            </fontconfig>
          '';
        };
      };
    };
} args
