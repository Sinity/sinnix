# GPU mode option — single toggle controlling the full driver stack.
#
# Set in host config (hosts/sinnix-prime/default.nix):
#   sinnix.gpu.mode = "nvidia";       # Proprietary driver, no power management
#   sinnix.gpu.mode = "nvidia-open";  # NVIDIA open kernel module, no power management
#   sinnix.gpu.mode = "igpu";         # Intel UHD 770, discrete GPU physically absent
#
# Consumed by: hosts/sinnix-prime/display.nix, hosts/sinnix-prime/boot.nix
{
  config,
  lib,
  pkgs,
  ...
}:
let
  cfg = config.sinnix.gpu;
  user = config.sinnix.user.name;
  userUid = toString config.users.users.${user}.uid;
  discrete = cfg.mode != "igpu";
  tuning = cfg.nvidiaTuning;
  powerMizerModeValue = {
    adaptive = 0;
    prefer-max-performance = 1;
    auto = 2;
  };
  hasRuntimeTuning = tuning.powerMizerMode != null || tuning.fanFloorPercent != null;
  runtimeTuningScript = pkgs.writeShellScript "sinnix-nvidia-runtime-tuning" ''
    set -euo pipefail

    export DISPLAY="''${DISPLAY:-:0}"
    export XDG_RUNTIME_DIR="''${XDG_RUNTIME_DIR:-/run/user/${userUid}}"
    export DBUS_SESSION_BUS_ADDRESS="''${DBUS_SESSION_BUS_ADDRESS:-unix:path=$XDG_RUNTIME_DIR/bus}"

    # Wait briefly for Xwayland/NVIDIA controls to become queryable inside the
    # live graphical session before attempting to apply runtime tuning.
    for _ in $(seq 1 50); do
      if nvidia-settings -q '[gpu:0]/NvidiaDriverVersion' >/dev/null 2>&1; then
        break
      fi
      sleep 0.2
    done

    ${lib.optionalString (tuning.powerMizerMode != null) ''
      nvidia-settings -a "[gpu:0]/GPUPowerMizerMode=${
        toString powerMizerModeValue.${tuning.powerMizerMode}
      }"
    ''}

    ${lib.optionalString (tuning.fanFloorPercent != null) ''
      cleanup() {
        ${pkgs.xhost}/bin/xhost -SI:localuser:root >/dev/null || true
      }
      trap cleanup EXIT

      ${pkgs.xhost}/bin/xhost +SI:localuser:root >/dev/null
      /run/wrappers/bin/sudo -n \
        DISPLAY="$DISPLAY" \
        XDG_RUNTIME_DIR="$XDG_RUNTIME_DIR" \
        DBUS_SESSION_BUS_ADDRESS="$DBUS_SESSION_BUS_ADDRESS" \
        nvidia-settings \
          -a '[gpu:0]/GPUFanControlState=1' \
          -a '[fan:0]/GPUTargetFanSpeed=${toString tuning.fanFloorPercent}' \
          -a '[fan:1]/GPUTargetFanSpeed=${toString tuning.fanFloorPercent}' \
          >/dev/null
    ''}
  '';
in
{
  options.sinnix.gpu = {
    mode = lib.mkOption {
      type = lib.types.enum [
        "nvidia"
        "nvidia-open"
        "igpu"
        "dual"
      ];
      default = "nvidia";
      description = ''
        GPU driver mode for sinnix-prime.
          "nvidia"      — proprietary kernel module, power management disabled
          "nvidia-open" — NVIDIA open kernel module, power management disabled
          "igpu"        — Intel UHD 770, used when discrete GPU is physically absent
          "dual"        — Both Intel iGPU (i915) and NVIDIA active; either mobo or dGPU port works
      '';
    };

    nvidiaTuning = {
      enable = lib.mkEnableOption ''
        dormant NVIDIA runtime tuning overrides for the discrete GPU path.
        Keep this disabled until a specific experiment should actually apply.
      '';

      powerMizerMode = lib.mkOption {
        type =
          with lib.types;
          nullOr (enum [
            "adaptive"
            "prefer-max-performance"
            "auto"
          ]);
        default = null;
        description = ''
          Runtime `GPUPowerMizerMode` override applied inside the graphical
          session when `enable = true`.
          `adaptive` follows load, `prefer-max-performance` avoids the deepest
          idle state, and `auto` leaves final policy choice to the driver.
        '';
      };

      fanFloorPercent = lib.mkOption {
        type = with lib.types; nullOr (ints.between 30 100);
        default = null;
        description = ''
          Manual fan floor applied through `nvidia-settings` when `enable = true`.
          The current RTX 3080 accepts targets down to 30%, but empirical
          runtime checks show the fans only begin spinning reliably at 50%.
        '';
      };

      enablePersistenceDaemon = lib.mkOption {
        type = lib.types.bool;
        default = false;
        description = ''
          Enable `hardware.nvidia.nvidiaPersistenced` alongside runtime tuning so
          the driver stays initialized across idle periods.
        '';
      };
    };
  };

  config = lib.mkMerge [
    (lib.mkIf (discrete && tuning.enable && tuning.enablePersistenceDaemon) {
      hardware.nvidia.nvidiaPersistenced = true;
    })

    (lib.mkIf (discrete && tuning.enable && hasRuntimeTuning) {
      # Coolbits unlocks the NVIDIA control surfaces needed for manual fan and
      # Powermizer overrides when running under Xwayland/NVIDIA.
      services.xserver.config = ''
        Section "Device"
          Driver "nvidia"
          Option "Coolbits" "31"
          Identifier "Device-nvidia-runtime-tuning"
        EndSection
      '';

      home-manager.users.${user}.systemd.user.services.sinnix-nvidia-runtime-tuning =
        lib.sinnix.systemd.mkGraphicalUserService
          {
            description = "Apply NVIDIA runtime tuning overrides";
            serviceType = "oneshot";
            restart = "no";
            unitExtra.After = [ "wayland-wm@hyprland\\x2duwsm.desktop.service" ];
            execStart = "${runtimeTuningScript}";
          };
    })
  ];
}
