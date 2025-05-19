{ pkgs, lib, ... }:
{
  programs = {
    hyprland.enable = true;
    steam.enable = true;
    steam.gamescopeSession.enable = true;
    gamemode.enable = true;
  };

  services.xserver = {
    enable = true;
    displayManager.lightdm.enable = false; # Using Hyprland's direct login
    videoDrivers = [ "nvidia" ];
  };

  hardware = {
    nvidia = {
      #package = pkgs.nvidiaPackages.stable;
      modesetting.enable = true;
      powerManagement.enable = true;
      open = true;
      nvidiaSettings = true;
      forceFullCompositionPipeline = true;
    };

    graphics = {
      enable = true;
      extraPackages = with pkgs; [
        edid-decode # For decoding display capabilities metadata
      ];
    };
  };

  environment.systemPackages = with pkgs; [
    wlr-randr # Wayland equivalent to xrandr for setting display modes
  ];

  # XDG Desktop Portal for application integration
  xdg.portal = {
    enable = true;
    wlr.enable = true;
    xdgOpenUsePortal = true;
    extraPortals = [
      pkgs.xdg-desktop-portal
      pkgs.xdg-desktop-portal-hyprland
      pkgs.xdg-desktop-portal-gtk
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

  fonts = {
    fontDir.enable = true;

    packages =
      with pkgs;
      [
        # General purpose fonts
        noto-fonts
        noto-fonts-extra

        # Source family
        source-code-pro
        source-sans-pro
        source-serif-pro

        # CJK fonts
        source-han-code-jp
        source-han-mono
        source-han-sans
        source-han-serif

        # Additional fonts
        hermit
        roboto
        roboto-mono
        roboto-slab
      ]
      # Include all nerd fonts
      ++ builtins.filter lib.attrsets.isDerivation (builtins.attrValues pkgs.nerd-fonts);

    # Font default settings
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
