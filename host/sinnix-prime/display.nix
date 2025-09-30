# Host-specific display configuration for sinnix-prime
# Hardware-specific GPU, gaming, and driver configuration
{
  pkgs,
  config,
  ...
}:
{
  # Gaming and GPU-accelerated applications
  programs = {
    steam.enable = true;
    steam.gamescopeSession.enable = true;
    gamemode.enable = true;
  };

  # X11 server for compatibility and NVIDIA drivers
  services.xserver = {
    enable = true;
    displayManager.lightdm.enable = false; # Using Hyprland's direct login
    videoDrivers = [ "nvidia" ];
  };

  # NVIDIA hardware configuration
  hardware = {
    nvidia = {
      package = config.boot.kernelPackages.nvidiaPackages.production;
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
}
