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
    lib.mkMerge [
      {
        sinnix.runtime.surfaces.mi-unlock = {
          unit = "sinnix-mi-unlock.service";
          manager = "user";
          resourceClass = "background";
          observe.enable = true;
        };
      }
      (lib.sinnix.mkScheduledJob
        {
          inherit config;
          unitName = "sinnix-mi-unlock";
          description = "Apply for Xiaomi bootloader unlock at the quota reset";
          surface = config.sinnix.runtime.surfaces.mi-unlock;
        }
        {
          manager = "user";
          resourceClass = "background";
          execStart = "${runner}/bin/sinnix-mi-unlock-run";
          serviceConfig = {
            # The process waits for the quota boundary after it starts.
            Type = "simple";
            StateDirectory = "sinnix-mi-unlock";
            # Exit 75 is the ordinary refusal before the quota window.
            SuccessExitStatus = "75";
          };
          unit.unitConfig.ConditionPathExists = "!%S/sinnix-mi-unlock/granted";
          timer = {
            onCalendar = cfg.onCalendar;
            accuracySec = "1s";
            # A missed quota window cannot be caught up after the fact.
            persistent = false;
            description = "Daily trigger for the Xiaomi unlock window";
          };
        }
      )
    ];
} args
