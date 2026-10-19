# IRC log hashing
#
# Daily user timer that hashes "old enough" per-day IRC logs in the
# captures archive and renames them to ``YYYY-MM-DD.b2-<12hex>.log``.
# The script is packaged from ./irc-log-hash/hash_logs.py; the /realm data tree
# holds data only (the in-tree scripts/ copy was retired 2026-08-24; the
# ad-hoc analysis siblings moved to sinity-lynchpin scripts/irc/).
#
# See the hash_logs.py header for the 2-day buffer rationale (avoids
# racing weechat fds across midnight on dormant channels).
{
  mkServiceModule,
  lib,
  pkgs,
  ...
}@args:
mkServiceModule {
  name = "irc-log-hash";
  defaultOnDesktop = true;
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
      unit = "sinnix-irc-log-hash.timer";
      manager = "user";
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
          path = "${config.sinnix.paths.capturePaths.irc}";
          eventDriven = true;
          staleAfterSeconds = 3600;
        }
      ];
    };
  job =
    { cfg, config, ... }:
    let
      ircRoot = "${config.sinnix.paths.capturePaths.irc}";
    in
    {
      # Unit predates the sinnix- prefix; keep its name.
      unitName = "sinnix-irc-log-hash";
      manager = "user";
      description = "Hash-seal weechat IRC logs older than 2 days";
      # The registered surface unit is the *timer*, so the service resolves
      # its class directly rather than by unit lookup.
      resourceClass = "background";
      execStart = "${pkgs.python3}/bin/python3 ${./irc-log-hash/hash_logs.py} ${ircRoot}";
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
