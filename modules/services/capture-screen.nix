# capture-screen: Hyprland-event + idle-pause + 30s-floor triggered
# per-window screen frame capture
#
# The frame-grab mechanism and idle-pause heuristic are documented in
# pkgs/capture-screen/sinnix_capture_screen/daemon.py's module docstring --
# read that before touching the mechanism. Short version: Noctalia's
# screenshot IPC (`noctalia msg screenshot-*`) is whole-output/region-only
# with no scriptable raw-bytes interface, so this collector drives `grim`
# directly -- the SAME wlr-screencopy protocol Noctalia uses. Black frames
# are a compositor-side problem, cured by
# `render:keep_unmodified_copy`/`render:use_shader_blur_blend` in
# modules/features/desktop/hyprland/default.nix, not by swapping grim out;
# the setting applies to any wlr-screencopy client.
#
# `--daily-ceiling-bytes` (default 1GB) is a runaway-bug backstop, NOT a
# policy cap: it exists only to stop a stuck dedup/trigger loop from writing
# unbounded data, and it trips loudly (stderr, once per UTC day) rather than
# silently dropping writes.
{
  mkServiceModule,
  mkCaptureLane,
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
  capturesRoot = config.sinnix.paths.activityRoot;
  laneDir = "${capturesRoot}/screen-frames";
  cfg = config.sinnix.services.capture-screen;
in
mkServiceModule (mkCaptureLane {
  name = "capture-screen";
  description = "Per-window screen frame capture: Hyprland events + idle-pause + 30s floor, p-hash dedup, WebP q80";
  inherit username laneDir;
  mode = "stream";
  captureName = "screen-frames";
  # Event-driven (Hyprland window/workspace changes + idle-pause), not pure
  # cadence -- but the 30s periodic floor means a frame is attempted at
  # least every 30s regardless, so staleness past a few multiples of that
  # floor is a real signal something's wrong (daemon crashed, socket2
  # dropped) rather than legitimate idle.
  eventDriven = true;
  staleAfterSeconds = 300;
  # A resolved focused window is this lane's whole product: without it a
  # frame cannot be attributed to an application, a workspace, or a
  # terminal session, and the daemon can keep reporting "active (running)"
  # while every record it writes has these fields null. `monitor` is
  # included because a frame with no output identity is equally unusable.
  requiredPayloadFields = [
    "window_class"
    "workspace"
    "geometry.width"
    "monitor"
  ];
  startLimit = {
    intervalSec = 300;
    burst = 5;
  };
  umask = "0077";
  extraOptions = {
    periodicFloorSeconds = lib.mkOption {
      type = lib.types.int;
      default = 30;
      description = "Maximum seconds between captures even with no window/workspace change.";
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
  tmpfilesRules = [ "d ${laneDir} 0700 ${username} users -" ];
  execStart = lib.escapeShellArgs [
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
  unitDescription = "Per-window screen frame capture (Hyprland events + idle-pause + 30s floor)";
}) args
