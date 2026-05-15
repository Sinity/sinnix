# Host-specific display configuration for sinnix-prime
# GPU mode is controlled by a single toggle in default.nix:
#   sinnix.gpu.mode = "nvidia"       → proprietary NVIDIA kernel module
#   sinnix.gpu.mode = "nvidia-open"  → NVIDIA open kernel module
#   sinnix.gpu.mode = "igpu"         → Intel UHD 770 (discrete GPU absent)
{
  pkgs,
  config,
  lib,
  ...
}:
let
  mode = config.sinnix.gpu.mode;
  discrete = mode != "igpu";
  nvidiaOpen = mode == "nvidia-open";
  user = config.sinnix.user.name;
in
lib.mkMerge [

  # ── Common ──────────────────────────────────────────────────────────────────
  {
    hardware.graphics = {
      enable = true;
      enable32Bit = true; # Steam / Wine 32-bit GL+Vulkan
      extraPackages = with pkgs; [
        edid-decode
        mesa
        libGL
        libglvnd
      ];
    };

    security.pam.services.hyprlock = { };
  }

  # ── NVIDIA (both modes) ──────────────────────────────────────────────────────
  (lib.mkIf discrete {
    services.xserver = {
      enable = false;
      videoDrivers = [ "nvidia" ]; # loads NVIDIA kernel modules even without X11
    };

    hardware.nvidia = {
      package = config.boot.kernelPackages.nvidiaPackages.production;
      modesetting.enable = true;
      # open / powerManagement driven by mode — see below
      nvidiaSettings = true;
    };

    home-manager.users.${user} = {
      home.sessionVariables = {
        LIBVA_DRIVER_NAME = "nvidia";
        GBM_BACKEND = "nvidia-drm";
        __GLX_VENDOR_LIBRARY_NAME = "nvidia";
        WLR_NO_HARDWARE_CURSORS = "1";
        __GL_GSYNC_ALLOWED = "1";
        __GL_VRR_ALLOWED = "1";
      };

      # v1 catch-all — monitorv2 below takes precedence
      wayland.windowManager.hyprland.settings.monitor = [
        ",3840x2160@120,auto,1,bitdepth,10,cm,hdr"
      ];

      # AORUS FO48U OLED HDR — connector names are NVIDIA-assigned (DP-3, HDMI-A-1)
      # Reference: https://github.com/hyprwm/Hyprland/discussions/11677
      wayland.windowManager.hyprland.settings.monitorv2 = [
        {
          output = "DP-3";
          mode = "3840x2160@120";
          position = "0x0";
          scale = 1;
          bitdepth = "10";
          cm = "hdr";
          sdrbrightness = 1.3;
          sdrsaturation = 1.0;
          sdr_min_luminance = 0;
          sdr_max_luminance = 150;
          min_luminance = 0;
          max_luminance = 550;
          max_avg_luminance = 200;
          supports_hdr = 1;
          supports_wide_color = 1;
        }
        {
          # HDMI 2.0 — 60Hz until HDMI 2.1 (48Gbps) cable arrives
          output = "HDMI-A-1";
          mode = "3840x2160@60";
          position = "0x0";
          scale = 1;
          bitdepth = "10";
          cm = "hdr";
          sdrbrightness = 1.3;
          sdrsaturation = 1.0;
          sdr_min_luminance = 0;
          sdr_max_luminance = 150;
          min_luminance = 0;
          max_luminance = 550;
          max_avg_luminance = 200;
          supports_hdr = 1;
          supports_wide_color = 1;
        }
      ];
    };
  })

  # ── NVIDIA proprietary ───────────────────────────────────────────────────────
  # Applies to both pure NVIDIA and dual-GPU mode.
  (lib.mkIf (mode == "nvidia" || mode == "dual") {
    boot.extraModprobeConfig = ''
      options nvidia NVreg_EnableGpuFirmware=0
    '';

    hardware.nvidia = {
      open = false;
      powerManagement.enable = false;
    };
  })

  # ── NVIDIA open kernel module ────────────────────────────────────────────────
  (lib.mkIf nvidiaOpen {
    hardware.nvidia = {
      open = true;
      powerManagement.enable = false;
    };
  })

  # ── Dual (both i915 + NVIDIA active, either port works) ─────────────────────
  # NVIDIA drives dGPU outputs (DP-3); i915 drives mobo outputs (DP-1).
  # Hyprland enumerates both DRM devices. Catch-all monitor rule picks up
  # whichever output is physically connected — run `hyprctl monitors` to confirm.
  # No monitorv2 override: connector names are session-dependent; prefer the
  # catch-all so a cable swap doesn't need a config change.
  (lib.mkIf (mode == "dual") {
    hardware.graphics.extraPackages = with pkgs; [
      intel-media-driver # VA-API iHD driver for iGPU decode
    ];

    home-manager.users.${user} = {
      home.sessionVariables = {
        LIBVA_DRIVER_NAME = "nvidia";
        GBM_BACKEND = "nvidia-drm";
        __GLX_VENDOR_LIBRARY_NAME = "nvidia";
        WLR_NO_HARDWARE_CURSORS = "1";
      };

      # Catch-all: any connected output at preferred mode, auto position.
      # Covers both DP-1 (mobo/iGPU) and DP-3 (dGPU) without hardcoding.
      wayland.windowManager.hyprland.settings.monitor = [
        ",3840x2160@120,auto,1,bitdepth,10,cm,hdr"
      ];
    };
  })

  # ── Intel iGPU (i7-13700K UHD 770, discrete GPU absent) ─────────────────────
  # Connector names differ from NVIDIA — run `hyprctl monitors` on first boot.
  (lib.mkIf (mode == "igpu") {
    hardware.graphics.extraPackages = with pkgs; [
      intel-media-driver # VA-API iHD driver (Gen 8+)
      libva-vdpau-driver # VDPAU → VA-API bridge
      libvdpau-va-gl # VDPAU backend via VA-API/OpenGL
    ];

    home-manager.users.${user} = {
      home.sessionVariables = {
        LIBVA_DRIVER_NAME = "iHD";
      };

      # v1 catch-all — monitorv2 below takes precedence
      wayland.windowManager.hyprland.settings.monitor = [
        ",3840x2160@120,auto,1,bitdepth,10,cm,hdr"
      ];

      # AORUS FO48U OLED HDR via Intel iGPU — connector is DP-1 (Intel-assigned)
      # 4K@120Hz confirmed available via modetest on DP-1
      wayland.windowManager.hyprland.settings.monitorv2 = [
        {
          output = "DP-1";
          mode = "3840x2160@120";
          position = "0x0";
          scale = 1;
          bitdepth = "10";
          cm = "hdr";
          sdrbrightness = 1.3;
          sdrsaturation = 1.0;
          sdr_min_luminance = 0;
          sdr_max_luminance = 150;
          min_luminance = 0;
          max_luminance = 550;
          max_avg_luminance = 200;
          supports_hdr = 1;
          supports_wide_color = 1;
        }
      ];
    };
  })
]
