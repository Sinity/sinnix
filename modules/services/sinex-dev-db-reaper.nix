# Sinex dev-postgres idle reaper (backstop).
#
# The sinex devshell starts a per-checkout PostgreSQL under
# /var/cache/sinex/<user>/<checkout-hash>/dev-state that daemonizes and can
# outlive its shell. The PRIMARY cleanup is the per-checkout owner-watcher that
# sinnix-direnvrc launches on devshell entry (see scripts/sinnix-sinex-dev-db
# `watch`). This timer is the BACKSTOP: a periodic sweep that stops instances
# the watcher never saw — a host crash, a `nix develop` one-shot that bypassed
# the direnv hook, or a watcher that itself died. It only stops instances with
# no live owning shell, no active client connection, and an uptime past the idle
# threshold, so an in-use devshell (or a legitimate `xtask ... --bg` / sinexd
# still connected) is never touched.
#
# Runs as the operator's systemd --user manager because the dev-postgres
# instances are owned by that uid; the sweep needs to read their /proc and
# signal them.
#
# Enable with: sinnix.services.sinex-dev-db-reaper.enable = true;
{
  mkServiceModule,
  lib,
  pkgs,
  helpers,
  ...
}@args:
let
  scriptPkgs = helpers.mkSinnixPackagesFor pkgs;
  reaper = scriptPkgs."sinnix-sinex-dev-db";
in
mkServiceModule {
  name = "sinex-dev-db-reaper";
  description = "Idle reaper for orphaned sinex per-checkout dev-postgres instances";
  extraOptions = {
    onCalendar = lib.mkOption {
      type = lib.types.str;
      default = "*-*-* *:07,37:00";
      description = ''
        systemd ``OnCalendar`` expression for the reaper sweep. Defaults to
        twice hourly (:07 and :37). The primary owner-watcher handles the common
        case within ~60s; this only needs to be frequent enough to bound how
        long a watcher-missed orphan can linger.
      '';
    };
    idleSeconds = lib.mkOption {
      type = lib.types.int;
      default = 7200;
      description = ''
        Minimum uptime, in seconds, before an owner-less, un-connected
        dev-postgres is eligible for reaping. Two hours by default — long enough
        that a genuinely-idle-but-wanted instance the watcher already knows about
        is never surprised, matching sinex's own >2h stale-nats cleanup floor.
      '';
    };
  };
  surface = {
    unit = "sinex-dev-db-reaper.timer";
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
      ...
    }:
    let
      userName = config.sinnix.user.name;
    in
    {
      home-manager.users.${userName} = {
        systemd.user.services.sinex-dev-db-reaper = {
          Unit.Description = "Reap orphaned sinex dev-postgres instances";
          Service = {
            Type = "oneshot";
            ExecStart = "${reaper}/bin/sinnix-sinex-dev-db reap --idle-secs ${toString cfg.idleSeconds}";
            # A wedged instance escalates SIGINT→SIGQUIT→SIGKILL internally with
            # bounded waits; cap the whole sweep so a stuck unit cannot linger.
            TimeoutStartSec = "5min";
          };
        };

        systemd.user.timers.sinex-dev-db-reaper = {
          Unit.Description = "Periodic reap of orphaned sinex dev-postgres";
          Timer = {
            OnCalendar = cfg.onCalendar;
            Persistent = true;
            RandomizedDelaySec = "2min";
            Unit = "sinex-dev-db-reaper.service";
          };
          Install.WantedBy = [ "timers.target" ];
        };
      };
    };
} args
