{ pkgs, ... }:
{
  hardware = {
    nvidia = {
      modesetting.enable = true;
      powerManagement.enable = false;
      powerManagement.finegrained = false;
      open = false;
      nvidiaSettings = true;
    };

    graphics = {
      enable = true;
      extraPackages = with pkgs; [
        edid-decode # for decoding EDID (display capabilities metadata, e.g. avaiable modes)
      ];
    };
  };
  
  xdg.portal = {
    enable = true;
    wlr.enable = true;
    xdgOpenUsePortal = true;
    extraPortals = [
      pkgs.xdg-desktop-portal-hyprland
      pkgs.xdg-desktop-portal-gtk
    ];
  };

  environment.systemPackages = with pkgs; [
    wlr-randr # xrandr equivalent, for reading/setting display modes (resolution, refresh rate)
  ];

  fonts = {
    fontDir.enable = true;

    packages = with pkgs; [
      noto-fonts noto-fonts-extra
      source-code-pro source-sans-pro source-serif-pro
      source-han-code-jp source-han-mono source-han-sans source-han-serif
      hermit
      roboto roboto-mono roboto-slab
    ] ++ builtins.filter lib.attrsets.isDerivation (builtins.attrValues pkgs.nerd-fonts);

    fontconfig = {
      defaultFonts = {
        monospace = [ "SauceCodePro Nerd Font Mono" ];
        sansSerif = [ "Arimo" ];
        serif     = [ "Tinos" ];
        emoji     = [ "Noto Color Emoji" ];
      };
    };
  };

  services = {
    xserver = {
      enable = true;
      displayManager.lightdm.enable = false;
      videoDrivers = [ "nvidia" ];
    };
  };
}
