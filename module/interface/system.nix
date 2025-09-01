# Interface System Configuration
# System-level UI setup: Stylix theming, Hyprland/UWSM system config, XDG portals

{
  pkgs,
  config,
  inputs,
  ...
}:
{
  config = {
    # === STYLIX SYSTEM-WIDE THEMING ===
    stylix = {
      enable = true;

      # Use gruvbox dark theme
      base16Scheme = "${pkgs.base16-schemes}/share/themes/gruvbox-dark-medium.yaml";

      image = ../asset/forest.jpg;

      fonts = {
        monospace = {
          package = pkgs.nerd-fonts.sauce-code-pro;
          name = "SauceCodePro Nerd Font Mono";
        };
        sansSerif = {
          package = pkgs.liberation_ttf; # Arimo is part of liberation fonts
          name = "Arimo";
          # name = "Noto Sans";  # Alternative
        };
        serif = {
          package = pkgs.liberation_ttf; # Tinos is part of liberation fonts
          name = "Tinos";
          # name = "Noto Serif";  # Alternative
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
      
      # Ensure fonts are properly applied system-wide
      autoEnable = true;

    };

    programs.hyprland = {
      enable = true;
      withUWSM = true;
      package = inputs.hyprland.packages.${pkgs.system}.hyprland;
    };

    programs.uwsm = {
      enable = true;
    };

    xdg.portal = {
      enable = true;
      wlr.enable = true;
      xdgOpenUsePortal = true;
      extraPortals = with pkgs; [
        xdg-desktop-portal
        xdg-desktop-portal-gtk
      ];
      config = {
        common = {
          default = [
            "gtk"
            "hyprland"
          ];
          "org.freedesktop.portal.OpenURI" = [
            "gtk"
            "hyprland"
          ];
        };
      };
    };

    environment.systemPackages = with pkgs; [
      wlr-randr # Wayland equivalent to xrandr
    ];
  };
}
