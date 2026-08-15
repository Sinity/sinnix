# Daily attempt at Xiaomi's bootloader-unlock quota window.
#
# The quota resets at 00:00 Beijing (18:00 local under CEST) and empties in
# seconds, so the attempt has to land on the boundary rather than be
# remembered. Fires once per day: probe the window's edges, then submit on
# the deadline the server itself reports.
#
# Stops permanently once granted -- the sentinel below is the whole
# termination condition, so this cannot keep applying after it has won.
{
  mkServiceModule,
  config,
  lib,
  helpers,
  pkgs,
  ...
}@args:
mkServiceModule {
  name = "mi-unlock";
  description = "Daily Xiaomi bootloader-unlock application at the quota reset";
  extraOptions = {
    onCalendar = lib.mkOption {
      type = lib.types.str;
      default = "*-*-* 17:25:00";
      description = ''
        When to start. Must precede the window by more than the first probe
        offset (T-30min), since the run begins by probing rather than
        submitting. Local time: the window is 00:00 Beijing, so this tracks
        the local offset rather than naming a UTC hour.
      '';
    };
  };
  configFn =
    { cfg, ... }:
    let
      scriptPkgs = helpers.mkSinnixPackagesFor pkgs;
      user = config.sinnix.user.name;
      stateDir = "%S/sinnix-mi-unlock";
      sentinel = "${stateDir}/granted";
      runner = pkgs.writeShellApplication {
        name = "sinnix-mi-unlock-run";
        runtimeInputs = [ scriptPkgs.sinnix-mi-unlock-request ];
        text = ''
          # The token is pulled from the live browser over CDP, so a run
          # without a logged-in Chrome cannot succeed. Say which of the two
          # it is rather than reporting a generic failure at 18:00.
          if ! curl -sf -m 3 -o /dev/null http://127.0.0.1:9222/json/version; then
            echo "no Chrome DevTools endpoint on :9222 -- cannot fetch the session token" >&2
            exit 1
          fi
          sinnix-mi-unlock-request --observe-window
          rc=$?
          if [ "$rc" -eq 0 ]; then
            mkdir -p "$(dirname "${sentinel}")"
            date -Iseconds > "${sentinel}"
            echo "unlock granted; this timer will not run again"
          fi
          exit "$rc"
        '';
      };
    in
    {
      sinnix.runtime.surfaces.mi-unlock = {
        unit = "sinnix-mi-unlock.service";
        manager = "user";
        resourceClass = "background-maintenance";
        observe.enable = true;
      };

      home-manager.users.${user} = {
        systemd.user.services.sinnix-mi-unlock = {
          Unit = {
            Description = "Apply for Xiaomi bootloader unlock at the quota reset";
            # Skip entirely once granted.
            ConditionPathExists = "!%S/sinnix-mi-unlock/granted";
          };
          Service = {
            # The process intentionally waits for the quota boundary after
            # it has started.  Keep activation asynchronous so a config
            # switch does not block on the daily observation window.
            Type = "simple";
            StateDirectory = "sinnix-mi-unlock";
            ExecStart = "${runner}/bin/sinnix-mi-unlock-run";
            # A failed application is the ordinary outcome while the pool is
            # exhausted; retrying within the same day cannot help and would
            # only add requests, so there is deliberately no Restart.
          };
        };

        systemd.user.timers.sinnix-mi-unlock = {
          Unit.Description = "Daily trigger for the Xiaomi unlock window";
          Timer = {
            OnCalendar = cfg.onCalendar;
            AccuracySec = "1s";
            # Deliberately NOT Persistent: a missed window cannot be caught
            # up after the fact, and a late run would submit outside the
            # boundary for no reason.
            Persistent = false;
          };
          Install.WantedBy = [ "timers.target" ];
        };
      };
    };
} args
