# System-wide UI theme configuration
#
# STYLIX MANAGES:
#   - Color scheme (base16)
#   - Wallpaper (via hyprpaper service)
#   - System fonts
#   - Cursor theme
#   - GTK theme
#   - QT theme
#   - Application colors (vscode, kitty, etc - see targets)
#
# DO NOT manually configure:
#   - hyprpaper service/config (stylix provides it)
#   - Application color schemes (use stylix.targets.<app>.enable)
#
# To disable stylix for specific apps:
#   stylix.targets.<app>.enable = false;
{
  pkgs,
  inputs,
  lib,
  config,
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

  cfg = config.sinnix.ui;
in
{
  options.sinnix.ui = {
    enable = lib.mkEnableOption "Sinity's Graphical User Interface Stack";
  };

  config = lib.mkIf cfg.enable {
    stylix = {
      enable = true;
      base16Scheme = "${pkgs.base16-schemes}/share/themes/gruvbox-dark-medium.yaml";
      image = "${inputs.self}/assets/forest.jpg";

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
      wlr.enable = lib.mkForce false;
      xdgOpenUsePortal = true;
      extraPortals = lib.mkAfter [
        pkgs.xdg-desktop-portal-hyprland
        pkgs.xdg-desktop-portal-gtk
      ];
      config = {
        common = {
          default = ["hyprland" "gtk"];
        };
        hyprland = {
          default = ["hyprland" "gtk"];
          "org.freedesktop.impl.portal.Secret" = ["gnome-keyring"];
        };
      };
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
}
