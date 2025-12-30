# Host-specific display configuration for sinnix-prime
# Hardware-specific GPU, gaming, and driver configuration
{
  pkgs,
  config,
  lib,
  ...
}:
{
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

  home-manager.users.${config.sinnix.user.name} = {
    home.sessionVariables = {
      LIBVA_DRIVER_NAME = "nvidia";
      GBM_BACKEND = "nvidia-drm";
      __GLX_VENDOR_LIBRARY_NAME = "nvidia";
      WLR_NO_HARDWARE_CURSORS = "1";
      __GL_GSYNC_ALLOWED = "1";
      __GL_VRR_ALLOWED = "1";
    };

    wayland.windowManager.hyprland.settings.monitor = [
      ",3840x2160@120,auto,1,bitdepth,10,cm,hdr,sdrbrightness,1.4,sdrsaturation,1.0"
    ];
  };

  security.pam.services.hyprlock = { };

}
