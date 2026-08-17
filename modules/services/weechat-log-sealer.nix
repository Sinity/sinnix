# WeeChat IRC log sealer
#
# Daily user timer that hashes "old enough" per-day IRC logs in the
# captures archive and renames them to ``YYYY-MM-DD.b2-<12hex>.log``.
# The script lives next to the rest of the IRC pipeline at
# ``${capturesRoot}/comms/irc/scripts/seal_logs.py`` so the user can
# edit it inplace; this module just schedules it.
#
# See the seal_logs.py header for the 2-day buffer rationale (avoids
# racing weechat fds across midnight on dormant channels).
{
  mkServiceModule,
  lib,
  pkgs,
  ...
}@args:
mkServiceModule {
  name = "weechat-log-sealer";
  description = "Daily content-hash sealing of WeeChat IRC logs";
  extraOptions = {
    onCalendar = lib.mkOption {
      type = lib.types.str;
      default = "*-*-* 00:10:00";
      description = ''
        systemd ``OnCalendar`` expression for the seal pass. Defaults to
        00:10 local time daily — late enough that midnight buffer
        rollovers have flushed but well before any morning concat run.
      '';
    };
  };
  surface =
    { config, ... }:
    {
      unit = "weechat-log-sealer.timer";
      manager = "user";
      kind = "timer";
      resourceClass = "background-maintenance";
      observe = {
        enable = true;
        restartable = false;
      };
      # The IRC capture lane is written continuously by weechat, outside this
      # repo's process management; it rides the timer's surface because that
      # is the unit this module owns.
      captures = [
        {
          name = "comms-irc";
          path = "${config.sinnix.paths.commsRoot}/irc";
          eventDriven = true;
          staleAfterSeconds = 3600;
        }
      ];
    };
  job =
    { cfg, config, ... }:
    let
      ircRoot = "${config.sinnix.paths.commsRoot}/irc";
    in
    {
      # Unit predates the sinnix- prefix; keep its name.
      unitName = "weechat-log-sealer";
      manager = "user";
      description = "Hash-seal weechat IRC logs older than 2 days";
      # The registered surface unit is the *timer*, so the service resolves
      # its class directly rather than by unit lookup.
      resourceClass = "background-maintenance";
      execStart = "${pkgs.python3}/bin/python3 ${ircRoot}/scripts/seal_logs.py ${ircRoot}";
      serviceConfig = {
        # Bound runtime so a stuck mount doesn't pin a stale unit.
        TimeoutStartSec = "10min";
      };
      unit = {
        # The captures dir lives on /realm; don't bother running until it's
        # mounted. The user manager surfaces system mounts via default.target.
        after = [ "default.target" ];
      };
      timer = {
        description = "Daily seal of weechat IRC logs";
        onCalendar = cfg.onCalendar;
        # Catch up if the machine was off when the run was due; spread across
        # five minutes so same-host timers don't pile on simultaneously.
        persistent = true;
        randomizedDelaySec = "5min";
      };
    };
} args
