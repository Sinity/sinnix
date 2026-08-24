# Always-on NVENC screen replay ring
#
# A systemd --user service tied to graphical-session.target, the same
# lifecycle every other capture-* daemon uses: gpu-screen-recorder keeps the
# last `ringSeconds` of screen+audio in memory and touches disk only when
# told to save ("clip that"). Unlike every other capture-* lane this one is
# expected to sit silent for long stretches; that is a working idle state.
#
# CAPABILITY WIRING: `programs.gpu-screen-recorder.enable` installs a setcap
# (cap_sys_admin) wrapper for `gsr-kms-server`, letting gpu-screen-recorder
# grab the screen via KMS instead of the xdg-desktop-portal ScreenCast API.
# That is why the NixOS `programs.*` option is needed: portal-backed capture
# blocks on an interactive permission dialog, fatal for a service meant to
# start unattended at login, and it would add a portal round-trip per save.
# The setcap wrapper lands in `/run/wrappers/bin`, which is why ExecStart's
# PATH below includes it -- gpu-screen-recorder resolves `gsr-kms-server` by
# name, not by store path.
{
  mkServiceModule,
  lib,
  pkgs,
  config,
  ...
}@args:
let
  username = config.sinnix.user.name;
  lakeRoot = config.sinnix.paths.activityRoot;
  replayDir = "${lakeRoot}/replay";
  unit = "sinnix-capture-replay.service";

  replaySave = pkgs.writeShellApplication {
    name = "sinnix-replay-save";
    runtimeInputs = [
      pkgs.systemd
      pkgs.libnotify
    ];
    text = ''
      set -euo pipefail
      systemctl --user kill --signal=SIGUSR1 ${unit}
      notify-send -t 3000 "Replay saved" "${replayDir}"
    '';
  };

  replayStop = pkgs.writeShellApplication {
    name = "sinnix-replay-stop";
    runtimeInputs = [
      pkgs.systemd
      pkgs.libnotify
    ];
    text = ''
      set -euo pipefail
      systemctl --user stop ${unit}
      notify-send -t 2000 "Replay buffer stopped"
    '';
  };
in
mkServiceModule {
  name = "capture-replay";
  description = "Always-on NVENC screen replay ring (last N minutes), save-on-hotkey";
  extraOptions = {
    ringSeconds = lib.mkOption {
      type = lib.types.ints.positive;
      default = 1800;
      description = "Ring buffer depth in seconds (default 30 minutes).";
    };
    fps = lib.mkOption {
      type = lib.types.ints.positive;
      default = 60;
      description = "Capture framerate for the replay ring.";
    };
    target = lib.mkOption {
      type = lib.types.str;
      example = "DP-3";
      description = "gpu-screen-recorder -w capture target. Use the monitor connector name; \"focused\" means focused WINDOW in gsr 5.13.9 and hard-requires -s WxH, so it cannot be a working default for a whole-screen ring.";
    };
  };
  surface = {
    unit = unit;
    manager = "user";
    resourceClass = "capture-runtime";
    observe = {
      enable = true;
      restartable = true;
    };
    captures = [
      {
        name = "replay";
        path = replayDir;
        # Save-on-hotkey only -- a fully quiet week with nothing clipped is a
        # legitimate outcome.
        eventDriven = true;
        staleAfterSeconds = 604800;
      }
    ];
  };
  configFn =
    { cfg, config, ... }:
    {
      programs.gpu-screen-recorder.enable = true;

      systemd.tmpfiles.rules = [
        "d ${replayDir} 0700 ${username} users -"
      ];

      home-manager.users.${username} = {
        home.packages = [
          replaySave
          replayStop
        ];

        systemd.user.services.sinnix-capture-replay = {
          Unit = {
            Description = "Always-on NVENC screen replay ring (last N minutes)";
            After = [ "graphical-session.target" ];
            PartOf = [ "graphical-session.target" ];
            # A permanently-failing recorder must not churn indefinitely:
            # ten tries in five minutes, then stay down until a switch or
            # manual restart.
            StartLimitIntervalSec = 300;
            StartLimitBurst = 10;
          };
          Service = lib.sinnix.mkRuntimeServiceConfig {
            runtimeInventory = config.sinnix.runtime.inventory;
            unit = unit;
            overrides = {
              Type = "simple";
              Environment = "PATH=${config.security.wrapperDir}:/run/current-system/sw/bin";
              ExecStart = lib.escapeShellArgs [
                "${pkgs.gpu-screen-recorder}/bin/gpu-screen-recorder"
                "-w"
                cfg.target
                "-f"
                (toString cfg.fps)
                "-r"
                (toString cfg.ringSeconds)
                "-a"
                "default_output"
                "-c"
                "mp4"
                "-o"
                replayDir
              ];
              Restart = "on-failure";
              RestartSec = "5s";
              # This recorder can ignore SIGTERM and stall a whole reboot
              # behind its stop timeout (observed once, not reproducible on a
              # healthy host). Cause unknown, so bound the blast radius: 15s
              # is well clear of the ~0.5s healthy path.
              TimeoutStopSec = "15s";
              # NO mount-namespace sandboxing, and NoNewPrivileges stays off.
              # A user manager is unprivileged, so any such directive forces a
              # child user namespace, demoting gsr-kms-server's cap_sys_admin
              # to namespace-relative -- while DRM_IOCTL_MODE_GETFB2 checks it
              # against the initial namespace. The recorder then captures
              # nothing. Sandboxing this unit and capturing the screen are
              # mutually exclusive; PrivateUsers=false does not opt out.
              UMask = "0077";
            };
          };
          Install.WantedBy = [ "graphical-session.target" ];
        };
      };
    };
} args
