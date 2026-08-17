# Periodic kitty terminal scrollback capture
#
# A systemd --user timer drives scripts/kitty-scrollback-capture (full-ANSI
# scrollback dump via `kitty @ get-text`) on a fixed cadence, giving the
# kitty-scrollback lane a real owning unit the health sentinel can track.
{
  mkServiceModule,
  mkCaptureLane,
  lib,
  pkgs,
  config,
  helpers,
  ...
}@args:
let
  username = config.sinnix.user.name;
  scriptPkgs = helpers.mkSinnixPackagesFor pkgs;
  capturesRoot = config.sinnix.paths.activityRoot;
  scrollbackDir = "${capturesRoot}/kitty-scrollback";
  cfg = config.sinnix.services.capture-kitty-scrollback;
in
mkServiceModule (mkCaptureLane {
  name = "capture-kitty-scrollback";
  description = "Periodic full-ANSI kitty terminal scrollback capture";
  extraOptions = {
    intervalMinutes = lib.mkOption {
      type = lib.types.ints.positive;
      default = 30;
      description = "Minutes between scrollback capture runs.";
    };
  };
  inherit username;
  laneDir = scrollbackDir;
  mode = "poll";
  captureName = "kitty-scrollback";
  eventDriven = true;
  # No kitty windows open for a full day is itself a real signal (host
  # idle/away), not just a quiet capture lane.
  staleAfterSeconds = 86400;
  # Not restartable: this is a oneshot triggered by the timer, not a
  # long-running daemon a restart could bring back.
  restartable = false;
  execStart = "${scriptPkgs.kitty-scrollback-capture}/bin/kitty-scrollback-capture";
  environment = [ "KITTY_SCROLLBACK_DIR=${scrollbackDir}" ];
  pollAfter = [ "graphical-session.target" ];
  timer = {
    onUnitActiveSec = "${toString cfg.intervalMinutes}min";
    onStartupSec = "2min";
    persistent = true;
  };
  unitDescription = "Full-ANSI kitty terminal scrollback capture";
  timerDescription = "Periodic trigger for kitty scrollback capture";
}) args
