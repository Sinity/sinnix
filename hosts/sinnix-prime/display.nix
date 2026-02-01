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

    # Note: Using monitorv2 block for HDR config (Hyprland 0.53+)
    # The v1 monitor line is kept as fallback but monitorv2 takes precedence
    wayland.windowManager.hyprland.settings.monitor = [
      ",3840x2160@120,auto,1,bitdepth,10,cm,hdr"
    ];

    # AORUS FO48U OLED HDR Configuration
    # Reference: https://github.com/hyprwm/Hyprland/discussions/11677
    # Monitor specs: ~550 nits HDR peak, true black (OLED), ~150-200 nits SDR
    wayland.windowManager.hyprland.settings.monitorv2 = [
      {
        output = "DP-3";
        mode = "3840x2160@120";
        position = "0x0";
        scale = 1;
        bitdepth = "10";
        cm = "hdr";

        # SDR content rendering in HDR mode
        # For dark-mode usage (white text on black), lower values reduce ABL triggering
        sdrbrightness = 1.3; # SDR brightness multiplier (boosted for dark-mode comfort)
        sdrsaturation = 1.0; # SDR saturation (1.0 = native)

        # Luminance values for tone mapping (in nits)
        # OLED-specific: min should be 0 for true blacks
        sdr_min_luminance = 0; # SDR black floor (0 = true black, >0 = raised blacks like LCD)
        sdr_max_luminance = 150; # SDR white point (lowered from 200 for dark-mode comfort)
        min_luminance = 0; # HDR black floor (OLED = 0)
        max_luminance = 550; # HDR peak brightness (FO48U: ~550 nits real-world)
        max_avg_luminance = 200; # Full-screen sustained brightness

        # Capability flags
        supports_hdr = 1;
        supports_wide_color = 1;
      }
    ];
  };

  security.pam.services.hyprlock = { };

}
