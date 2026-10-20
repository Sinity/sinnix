# Periodic kitty terminal scrollback capture
#
# A systemd --user timer drives scripts/kitty-scrollback-capture (full-ANSI
# scrollback dump via `kitty @ get-text`) on a fixed cadence, giving the
# kitty-scrollback lane a real owning unit the health sweep can track.
{
  mkServiceModule,
  lib,
  pkgs,
  config,
  helpers,
  ...
}@args:
let
  username = config.sinnix.user.name;
  scriptPkgs = helpers.mkSinnixPackagesFor pkgs;
  scrollbackDir = "${config.sinnix.paths.capturePaths.kitty-scrollback}";
  progressDir = "${config.sinnix.paths.stateRoot}/hub/capture-progress";
  progressPath = "${progressDir}/kitty-scrollback";
  cfg = config.sinnix.services.capture-kitty-scrollback;
in
mkServiceModule {
  name = "capture-kitty-scrollback";
  defaultOnDesktop = true;
  description = "Periodic full-ANSI kitty terminal scrollback capture";
  extraOptions = {
    intervalMinutes = lib.mkOption {
      type = lib.types.ints.positive;
      default = 30;
      description = "Minutes between scrollback capture runs.";
    };
  };
  configFn =
    _:
    lib.mkMerge [
      {
        sinnix.capture.producers.capture-kitty-scrollback = {
          directories = [ scrollbackDir ];
          outputs = [
            {
              path = scrollbackDir;
              name = "kitty-scrollback";
              eventDriven = true;
              # No kitty windows open for a full day is itself a real signal (host
              # idle/away), not just a quiet capture lane.
              staleAfterSeconds = 86400;
              producerProgressPath = progressPath;
              # Not restartable: this is a oneshot triggered by the timer, not a
              # long-running daemon a restart could bring back.
            }
          ];
          operatorRestart = false;
          execStart = "${scriptPkgs.kitty-scrollback-capture}/bin/kitty-scrollback-capture";
          environment = [
            "KITTY_SCROLLBACK_DIR=${scrollbackDir}"
            "KITTY_SCROLLBACK_PROGRESS_MARKER=${progressPath}"
          ];
          poll.after = [ "graphical-session.target" ];
          poll.timer = {
            intervalSec = cfg.intervalMinutes * 60;
            onStartupSec = "2min";
            persistent = true;
          };
          description = "Full-ANSI kitty terminal scrollback capture";
          poll.timer.description = "Periodic trigger for kitty scrollback capture";
        };
      }
      {
        systemd.tmpfiles.rules = [ "d ${progressDir} 0700 ${username} users -" ];
      }
    ];
} args
