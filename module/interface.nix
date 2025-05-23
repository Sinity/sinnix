# Interface Domain Module
# Complete UI experience (system + desktop)
# Consolidates: desktop environment, themes, terminal, compositor

{
  config,
  lib,
  pkgs,
  username,
  ...
}:
with lib;
{
  # Note: Home-manager imports moved to user config section

  # Interface configuration will be consolidated here incrementally
  config = mkMerge [
    # System-level interface configuration
    {
      # Phase 3 marker - interface domain active
      system.nixos.tags = [ "interface-domain-v0.3" ];

      # Display and desktop infrastructure
      programs.hyprland.enable = true;

      # XDG Desktop Portal for application integration
      xdg.portal = {
        enable = true;
        wlr.enable = true;
        xdgOpenUsePortal = true;
        extraPortals = with pkgs; [
          xdg-desktop-portal
          xdg-desktop-portal-hyprland
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

      # Display utilities
      environment.systemPackages = with pkgs; [
        wlr-randr # Wayland equivalent to xrandr
      ];

      # Comprehensive font configuration
      fonts = {
        fontDir.enable = true;
        packages =
          with pkgs;
          [
            # Core fonts
            noto-fonts
            noto-fonts-extra
            noto-fonts-emoji

            # Source family
            source-code-pro
            source-sans-pro
            source-serif-pro

            # CJK fonts
            source-han-code-jp
            source-han-mono
            source-han-sans
            source-han-serif

            # Development fonts
            fira-code-nerdfont
            font-awesome

            # Additional fonts
            hermit
            roboto
            roboto-mono
            roboto-slab
          ]
          ++ builtins.filter lib.attrsets.isDerivation (builtins.attrValues pkgs.nerd-fonts);

        fontconfig = {
          enable = true;
          defaultFonts = {
            monospace = [ "SauceCodePro Nerd Font Mono" ];
            sansSerif = [ "Arimo" ];
            serif = [ "Tinos" ];
            emoji = [ "Noto Color Emoji" ];
          };
        };
      };
    }

    # User-level interface configuration via sinity alias
    {
      home-manager.users.${username} = {
        imports = [
          # Desktop environment components
          ./home/desktop
          ./home/kitty.nix
          ./home/xdg-mimes.nix
        ];

        # Interface domain marker for user config
        home.sessionVariables.INTERFACE_DOMAIN = "v0.3";
      };
    }
  ];
}
