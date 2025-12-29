# Host-specific display configuration for sinnix-prime
# Hardware-specific GPU, gaming, and driver configuration
{
  pkgs,
  config,
  lib,
  ...
}:
let
  hyprlandPkg = pkgs.hyprland;
in
{

  programs.hyprland = {
    enable = true;
    withUWSM = true;
    package = hyprlandPkg;
  };

  # X11 stack stays disabled; Hyprland is launched directly via UWSM, but we still
  # declare the desired driver so the NVIDIA kernel modules are available.
  services.xserver = {
    enable = false;
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
        mesa
        libGL
        libglvnd
      ];
    };
  };

  security.pam.services.hyprlock = { };

}
