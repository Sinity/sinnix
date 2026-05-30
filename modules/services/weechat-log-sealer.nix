# WeeChat IRC log sealer
#
# Daily user timer that hashes "old enough" per-day IRC logs in the
# captures archive and renames them to ``YYYY-MM-DD.b2-<12hex>.log``.
# The script lives next to the rest of the IRC pipeline at
# ``${capturesRoot}/comms/irc/scripts/seal_logs.py`` so the user can
# edit it inplace; this module just schedules it.
#
# See ``/realm/data/captures/comms/irc/scripts/seal_logs.py`` for the
# 2-day buffer rationale (avoids racing weechat fds across midnight on
# dormant channels).
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
  surface = {
    unit = "weechat-log-sealer.timer";
    manager = "user";
    kind = "timer";
    resourceClass = "background-maintenance";
    observe = {
      enable = true;
      restartable = false;
    };
  };
  configFn =
    {
      cfg,
      config,
      pkgs,
      ...
    }:
    let
      userName = config.sinnix.user.name;
      ircRoot = "${config.sinnix.paths.capturesRoot}/comms/irc";
      scriptPath = "${ircRoot}/scripts/seal_logs.py";
    in
    {
      home-manager.users.${userName} = {
        systemd.user.services.weechat-log-sealer = {
          Unit = {
            Description = "Hash-seal weechat IRC logs older than 2 days";
            # The captures dir lives on /realm; don't bother running until
            # it's mounted. The user manager surfaces system mounts via the
            # ``mounts.target`` user target.
            After = [ "default.target" ];
          };
          Service = {
            Type = "oneshot";
            ExecStart = "${pkgs.python3}/bin/python3 ${scriptPath} ${ircRoot}";
            # Bound runtime so a stuck mount doesn't pin a stale unit.
            TimeoutStartSec = "10min";
          };
        };

        systemd.user.timers.weechat-log-sealer = {
          Unit.Description = "Daily seal of weechat IRC logs";
          Timer = {
            OnCalendar = cfg.onCalendar;
            # Catch up if the machine was off when the run was due.
            Persistent = true;
            Unit = "weechat-log-sealer.service";
            # Spread across the first 5 minutes after the calendar trigger
            # so two same-host timers don't pile on simultaneously.
            RandomizedDelaySec = "5min";
          };
          Install.WantedBy = [ "timers.target" ];
        };
      };
    };
} args
