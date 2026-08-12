# Always-on NVENC screen replay ring (sinnix-9pd Phase 3a, 3.4)
#
# Promotes the manual, Steam-gated "F10 replay buffer" toggle out of
# modules/features/desktop/gaming.nix into a real capture surface: it now
# runs continuously via a systemd --user service tied to
# graphical-session.target, the same lifecycle every other capture-*
# daemon uses, instead of only existing while a game session manually
# started it. This is the operator's REPLAY RING design (sinnix-9pd,
# 2026-08-11g): gpu-screen-recorder keeps the last `ringSeconds` of
# screen+audio in memory and touches disk only when told to save
# ("clip that") -- so unlike every other capture-* lane this one is
# expected to sit silent for long stretches; that's a working idle
# state, not a stall.
#
# CAPABILITY WIRING: `programs.gpu-screen-recorder.enable` installs a
# setcap (cap_sys_admin) wrapper for `gsr-kms-server`, letting
# gpu-screen-recorder grab the screen directly via KMS instead of going
# through the xdg-desktop-portal ScreenCast API. That distinction is why
# this module needs the NixOS `programs.*` option at all: a portal-backed
# capture blocks on an interactive permission dialog the first time it
# runs, which is tolerable for the old manual F10 keybind (a human is
# right there to click Allow) but fatal for a service that's meant to
# start unattended at login and just sit there ready. KMS capture also
# needs no portal round-trip per save, so SIGUSR1-triggered saves stay
# fast. The setcap wrapper lands in `/run/wrappers/bin`, which is why
# ExecStart's PATH below is widened to include it -- gpu-screen-recorder
# resolves `gsr-kms-server` by name, not by a hardcoded store path.
{
  mkServiceModule,
  lib,
  pkgs,
  config,
  ...
}@args:
let
  username = config.sinnix.user.name;
  capturesRoot = config.sinnix.paths.capturesRoot;
  replayDir = "${capturesRoot}/replay";
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
      description = "Ring buffer depth in seconds (default 30 minutes, per the operator's REPLAY RING design note in sinnix-9pd).";
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
        # Save-on-hotkey only -- a fully quiet week with nothing clipped
        # is a legitimate outcome, same reasoning as the screenshot lane
        # in capture-registry.nix, so it gets the same 7-day budget.
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
              # NoNewPrivileges must stay OFF for this unit specifically:
              # gpu-screen-recorder's KMS capture path execs
              # gsr-kms-server through NixOS's setcap wrapper
              # (config.security.wrapperDir), which grants cap_sys_admin
              # via file capabilities at exec time -- exactly the kind of
              # privilege-gain no_new_privs exists to block.
              ProtectSystem = "strict";
              ProtectHome = "read-only";
              # gsr-kms-server binds its IPC socket hardcoded under /tmp
              # (".gsr-kms-socket-<random>", confirmed live via a
              # systemd-run transient unit with no sandboxing --
              # `/tmp/.gsr-kms-socket-c1C9qFmFq4`), NOT $XDG_RUNTIME_DIR
              # as an earlier fix attempt assumed (that attempt added "%t"
              # to ReadWritePaths, which changed nothing -- same EROFS
              # error persisted, corrected here rather than left wrong).
              # PrivateTmp gives this unit its own writable tmpfs /tmp
              # satisfying that hardcoded path without exposing or
              # requiring write access to the real host /tmp.
              PrivateTmp = true;
              ReadWritePaths = [ replayDir ];
              UMask = "0077";
            };
          };
          Install.WantedBy = [ "graphical-session.target" ];
        };
      };
    };
} args
