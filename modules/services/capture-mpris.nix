# MPRIS media-player capture
#
# Watches org.mpris.MediaPlayer2.* players over the user D-Bus session bus
# via `playerctl --follow` and appends sinnix-capture-v1 envelopes (player
# identity, title, artist, album, position, status) to the `mpris` capture
# lane on every track/status change, plus a periodic heartbeat while a
# player's PlaybackStatus is "Playing" -- long single-track listening
# sessions still carry position markers between track boundaries instead of
# going silent for the whole session. See pkgs/capture-mpris/monitor.py for
# the daemon and its rationale (why the playerctl follow format excludes
# position, why writes shell out to the sinnix-capture CLI).
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
  lakeRoot = config.sinnix.paths.activityRoot;
  mprisDir = "${lakeRoot}/mpris";
  cfg = config.sinnix.services.capture-mpris;

  monitor = pkgs.writeTextFile {
    name = "capture-mpris-monitor";
    destination = "/bin/capture-mpris-monitor";
    executable = true;
    text = ''
      #!${pkgs.python3}/bin/python3
    ''
    + builtins.readFile ../../pkgs/capture-mpris/monitor.py;
  };
in
mkServiceModule (mkCaptureLane {
  name = "capture-mpris";
  description = "MPRIS media-player track/status capture with playback heartbeat";
  extraOptions = {
    heartbeatIntervalSec = lib.mkOption {
      type = lib.types.ints.positive;
      default = 60;
      description = ''
        Seconds between heartbeat writes while a player's PlaybackStatus is
        "Playing". Keeps a position marker flowing during a single long
        track/stream instead of relying solely on track-boundary events.
      '';
    };
  };
  inherit username;
  laneDir = mprisDir;
  mode = "stream";
  captureName = "mpris";
  eventDriven = true;
  # Media listening is optional and intermittent: a fully quiet week is a
  # legitimate "nothing was played" outcome, not a broken daemon.
  staleAfterSeconds = 604800;
  execStart = "${monitor}/bin/capture-mpris-monitor --capture-root ${lakeRoot} --lane mpris --playerctl-bin ${pkgs.playerctl}/bin/playerctl --sinnix-capture-bin ${scriptPkgs.sinnix-capture}/bin/sinnix-capture --heartbeat-interval ${toString cfg.heartbeatIntervalSec}";
  unitDescription = "MPRIS media-player track/status capture with playback heartbeat";
}) args
