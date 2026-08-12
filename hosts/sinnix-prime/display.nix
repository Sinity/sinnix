# Host-specific display configuration for sinnix-prime
# GPU mode is controlled by a single toggle in default.nix:
#   sinnix.gpu.mode = "nvidia"       → proprietary NVIDIA kernel module
#   sinnix.gpu.mode = "nvidia-open"  → NVIDIA open kernel module
#   sinnix.gpu.mode = "igpu"         → Intel UHD 770 (discrete GPU absent)
#   sinnix.gpu.mode = "dual"         → both i915 (mobo) and NVIDIA (dGPU) active
{
  pkgs,
  config,
  lib,
  helpers,
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
    # Lock-screen PAM is declared by the Noctalia module
    # (security.pam.services.noctalia); hyprlock is gone.

    # DDC/CI to the monitor over the display cable. Without i2c-dev there are
    # no /dev/i2c-* nodes and ddcutil cannot see the panel at all (verified
    # 2026-08-13: "No /dev/i2c devices exist"). This is the only route to the
    # FO48U's own controls -- brightness, and the OSD-side settings behind its
    # ASBL dimming -- from software; the shader/brightness pulse in
    # scripts/asbl-no-moar is a workaround for not having it.
    # The i2c group grants the operator access without sudo per call.
    boot.kernelModules = [ "i2c-dev" ];
    hardware.i2c.enable = true;
    users.users.${user}.extraGroups = [ "i2c" ];
    environment.systemPackages = [ pkgs.ddcutil ];

    # Run the ASBL pulse continuously instead of leaving it on F3. The script
    # has existed since the panel arrived but was only ever bound to a key
    # (bindings.nix F3 / system-submap M), so the dimming it exists to defeat
    # came back whenever the operator did not think to press it -- which is
    # exactly the complaint. `start` is the script's own daemon mode; its
    # default 120s interval is tuned to the FO48U's dimming timer.
    home-manager.users.${user}.systemd.user.services.asbl-no-moar = {
      Unit = {
        Description = "Keep the FO48U's auto static brightness limiter from dimming the screen";
        After = [ "graphical-session.target" ];
        PartOf = [ "graphical-session.target" ];
      };
      Service = {
        Type = "simple";
        # `loop`, not `start`: start forks the loop and disowns, which a
        # Type=simple unit would read as immediate exit. `loop` is the
        # foreground daemon, and the flag parser runs before the subcommand
        # dispatch so options still apply.
        ExecStart = "${(helpers.mkSinnixPackagesFor pkgs).asbl-no-moar}/bin/asbl-no-moar loop --mode invert";
        Restart = "on-failure";
        RestartSec = "10s";
      };
      Install.WantedBy = [ "graphical-session.target" ];
    };
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
        __GL_GSYNC_ALLOWED = "0";
        __GL_VRR_ALLOWED = "0";
      };

      # v1 catch-all — monitorv2 below takes precedence for the primary DP-3
      # path. Keep the catch-all SDR so unknown/cable-swapped outputs do not
      # inherit unverified HDR settings.
      wayland.windowManager.hyprland.settings.monitor = [
        ",3840x2160@120,auto,1"
      ];

      # AORUS FO48U OLED on DP-3. 4K120 HDR/10-bit was verified live via
      # hyprctl on 2026-06-11 after the Noctalia ext-workspace crash path was
      # disabled.
      wayland.windowManager.hyprland.settings.monitorv2 = [
        {
          output = "DP-3";
          mode = "3840x2160@120";
          position = "0x0";
          scale = 1;
          bitdepth = "10";
          cm = "hdr";
          sdrbrightness = 1.4;
          sdrsaturation = 1.0;
          # 0.2 (Hyprland's default) lifts the OLED black floor just enough
          # that inactive-window opacity blends are actually visible —
          # operator-preferred look (2026-07-13). With 0, dark regions crush
          # to pure black and the configured inactive_opacity reads as
          # opaque. 0.2 also matches what a lossy runtime `keyword monitor`
          # reset produces, so screenshot flows can no longer flip the look.
          sdr_min_luminance = 0.2;
          sdr_max_luminance = 80;
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
        ",3840x2160@120,auto,1"
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

      # v1 catch-all — monitorv2 below takes precedence. Keep this SDR unless
      # the iGPU path is live-tested separately.
      wayland.windowManager.hyprland.settings.monitor = [
        ",3840x2160@120,auto,1"
      ];

      # AORUS FO48U OLED via Intel iGPU — connector is DP-1 (Intel-assigned)
      # 4K@120Hz confirmed available via modetest on DP-1
      wayland.windowManager.hyprland.settings.monitorv2 = [
        {
          output = "DP-1";
          mode = "3840x2160@120";
          position = "0x0";
          scale = 1;
        }
      ];
    };
  })
]
