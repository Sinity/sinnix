{
  pkgs,
  inputs,
  lib,
  ...
}:
{
  config = {
    stylix = {
      enable = true;
      base16Scheme = "${pkgs.base16-schemes}/share/themes/gruvbox-dark-medium.yaml";
      image = ../../module/asset/forest.jpg;

      fonts = {
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
          package = pkgs.noto-fonts-emoji;
          name = "Noto Color Emoji";
        };
        sizes = {
          applications = 16;
          desktop = 16;
          popups = 16;
          terminal = 16;
        };
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

    programs.hyprland = {
      enable = true;
      withUWSM = true;
      package = inputs.hyprland.packages.${pkgs.system}.hyprland;
    };

    programs.uwsm.enable = true;

    xdg.portal = {
      enable = true;
      wlr.enable = true;
      xdgOpenUsePortal = true;
      extraPortals = lib.mkAfter [ pkgs.xdg-desktop-portal-gtk ];
      config.common = {
        default = [
          "hyprland"
          "gtk"
        ];
        "org.freedesktop.portal.OpenURI" = [
          "hyprland"
          "gtk"
        ];
      };
    };

    services.ratbagd.enable = true;
    services.udev.packages = [ pkgs.solaar ];

    environment.systemPackages = with pkgs; [
      wlr-randr
    ];

    fonts = {
      packages = with pkgs; [
        noto-fonts
        noto-fonts-emoji
        dejavu_fonts
        liberation_ttf
        nerd-fonts.sauce-code-pro
      ];

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
                <family>Liberation Sans</family>
                <family>DejaVu Sans</family>
              </prefer>
            </alias>
            <alias>
              <family>serif</family>
              <prefer>
                <family>Liberation Serif</family>
                <family>DejaVu Serif</family>
              </prefer>
            </alias>
            <alias>
              <family>monospace</family>
              <prefer>
                <family>SauceCodePro Nerd Font Mono</family>
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
