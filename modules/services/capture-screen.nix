# Event-driven focused-window capture with a periodic attempt floor.
# The daemon owns capture mechanics; its CLI arguments below set policy.
# The daily byte ceiling stops runaway writes until the next UTC day.
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
  lakeRoot = config.sinnix.paths.activityRoot;
  laneDir = "${config.sinnix.paths.capturePaths.screen-frames}";
  cfg = config.sinnix.services.capture-screen;
in
mkServiceModule (mkCaptureLane {
  name = "capture-screen";
  defaultOnDesktop = true;
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
      default = 10000000000;
      description = "Daily write ceiling that suspends capture until the next UTC day (default 10GB).";
    };
  };
  tmpfilesRules = [ "d ${laneDir} 0700 ${username} users -" ];
  execStart = lib.escapeShellArgs [
    "${screenDaemon}/bin/sinnix-capture-screen"
    "--capture-root"
    lakeRoot
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
