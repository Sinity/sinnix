# capture-screen: Hyprland-event + idle-pause + 30s-floor triggered
# per-window screen frame capture (sinnix-9pd Phase 3a, 3.1-3.3)
#
# Frame-grab mechanism, the live black-frame regression found on
# sinnix-prime during this lane's authorship, and the idle-pause heuristic
# design are all documented in pkgs/capture-screen/sinnix_capture_screen/
# daemon.py's module docstring -- read that before touching the mechanism.
# Short version: Noctalia's own screenshot IPC (`noctalia msg
# screenshot-*`) is whole-output/region-only with no scriptable raw-bytes
# interface, so this collector drives `grim` directly -- the SAME
# wlr-screencopy protocol Noctalia's native path uses. The fix behind the
# closed sinnix-xuk/sinnix-kvc black-frame bugs was the compositor-side
# `render:keep_unmodified_copy`/`render:use_shader_blur_blend` settings in
# modules/features/desktop/hyprland/default.nix, not "use Noctalia's binary
# instead of grim's" -- that setting applies to any wlr-screencopy client.
#
# DAILY-VOLUME THROTTLE GUARD (3.3): `--daily-ceiling-bytes` (default 1GB)
# is a runaway-bug backstop, NOT a policy cap -- the operator's storage
# stance is "keep full fidelity forever, add capacity" (see sinnix-9pd's
# notes). It exists only to stop a stuck dedup/trigger loop from writing
# unbounded data; it trips loudly (stderr, once per UTC day) and never
# silently drops writes without saying so.
{
  mkServiceModule,
  config,
  lib,
  helpers,
  pkgs,
  ...
}@args:
let
  username = config.sinnix.user.name;
  scriptPkgs = helpers.mkSinnixPackagesFor pkgs;
  screenDaemon = scriptPkgs.sinnix-capture-screen;
  inherit (config.sinnix.paths) capturesRoot;
  laneDir = "${capturesRoot}/screen-frames";
in
mkServiceModule {
  name = "capture-screen";
  description = "Per-window screen frame capture: Hyprland events + idle-pause + 30s floor, p-hash dedup, WebP q80";
  surface = {
    unit = "sinnix-capture-screen.service";
    manager = "user";
    # No explicit `kind`: real owned systemd .service unit -> defaults to
    # "service", matching every sibling capture-* daemon (capture-a11y,
    # capture-mpris). `kind = "capture"` is reserved for orphan
    # surfaces with no real backing unit (capture-registry.nix).
    resourceClass = "capture-runtime";
    observe = {
      enable = true;
      restartable = true;
    };
    captures = [
      {
        name = "screen-frames";
        path = laneDir;
        # Event-driven (Hyprland window/workspace changes + idle-pause),
        # not pure cadence -- but the 30s periodic floor means a frame is
        # attempted at least every 30s regardless, so staleness past a few
        # multiples of that floor is a real signal something's wrong
        # (daemon crashed, socket2 dropped) rather than legitimate idle.
        eventDriven = true;
        staleAfterSeconds = 300;
        # A resolved focused window is this lane's whole product: without
        # it a frame cannot be attributed to an application, a workspace,
        # or a terminal session. The grim `-o`/`-g` conflict (sinnix-3w9n)
        # let the lane run "active running" for its entire deployed life
        # while writing only the records that had no window to resolve, so
        # these fields were null in 100% of them. `monitor` is included
        # because a frame with no output identity is equally unusable.
        requiredPayloadFields = [
          "window_class"
          "workspace"
          "geometry.width"
          "monitor"
        ];
      }
    ];
  };
  extraOptions = {
    periodicFloorSeconds = lib.mkOption {
      type = lib.types.int;
      default = 30;
      description = "Maximum seconds between captures even with no window/workspace change (3.1's 30s floor).";
    };
    idlePauseSeconds = lib.mkOption {
      type = lib.types.int;
      default = 3;
      description = "Seconds the cursor must sit still before the idle-pause trigger fires (approximates a typing/attention pause).";
    };
    dedupHammingThreshold = lib.mkOption {
      type = lib.types.int;
      default = 4;
      description = "Max p-hash Hamming distance (out of 64 bits) still treated as a duplicate of the previous frame for the same window.";
    };
    maxWidth = lib.mkOption {
      type = lib.types.int;
      default = 1920;
      description = "Frames wider than this are downscaled before WebP encoding.";
    };
    quality = lib.mkOption {
      type = lib.types.int;
      default = 80;
      description = "WebP encode quality.";
    };
    dailyCeilingBytes = lib.mkOption {
      type = lib.types.int;
      default = 1000000000;
      description = "Runaway-bug backstop on daily write volume (default 1GB), NOT a policy cap -- see module docstring.";
    };
  };
  configFn =
    { cfg, ... }:
    {
      systemd.tmpfiles.rules = [
        "d ${laneDir} 0700 ${username} users -"
      ];

      home-manager.users.${username} = {
        systemd.user.services.sinnix-capture-screen = {
          Unit = {
            Description = "Per-window screen frame capture (Hyprland events + idle-pause + 30s floor)";
            After = [ "graphical-session.target" ];
            PartOf = [ "graphical-session.target" ];
            StartLimitIntervalSec = 300;
            StartLimitBurst = 5;
          };
          Service = lib.sinnix.mkRuntimeServiceConfig {
            runtimeInventory = config.sinnix.runtime.inventory;
            unit = "sinnix-capture-screen.service";
            overrides = {
              Type = "simple";
              ExecStart = lib.escapeShellArgs [
                "${screenDaemon}/bin/sinnix-capture-screen"
                "--capture-root"
                capturesRoot
                "--lane"
                "screen-frames"
                "--grim-bin"
                "${pkgs.grim}/bin/grim"
                "--hyprctl-bin"
                "${pkgs.hyprland}/bin/hyprctl"
                "--sinnix-capture-bin"
                "${scriptPkgs.sinnix-capture}/bin/sinnix-capture"
                "--periodic-floor-seconds"
                (toString cfg.periodicFloorSeconds)
                "--idle-pause-seconds"
                (toString cfg.idlePauseSeconds)
                "--dedup-hamming-threshold"
                (toString cfg.dedupHammingThreshold)
                "--max-width"
                (toString cfg.maxWidth)
                "--quality"
                (toString cfg.quality)
                "--daily-ceiling-bytes"
                (toString cfg.dailyCeilingBytes)
              ];
              Restart = "on-failure";
              RestartSec = "5s";
              NoNewPrivileges = true;
              ProtectSystem = "strict";
              ProtectHome = "read-only";
              ReadWritePaths = [ laneDir ];
              UMask = "0077";
            };
          };
          Install.WantedBy = [ "graphical-session.target" ];
        };
      };
    };
} args
