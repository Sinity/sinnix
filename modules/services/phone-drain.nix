# sinnix-uyvt.2.1 (2): drain-on-a-schedule for the phone-side capture
# lanes, gated on wifi + charging rather than pulling manually. Wraps
# `sinnix-phone drain` (scripts/sinnix-phone), which does the actual
# reachability/charging/wifi checks and skips quietly when conditions
# aren't met -- this unit just provides the schedule.
{
  mkServiceModule,
  lib,
  pkgs,
  helpers,
  ...
}@args:
let
  scriptPkgs = helpers.mkSinnixPackagesFor pkgs;
in
mkServiceModule {
  name = "phone-drain";
  description = "Scheduled phone -> lake drain (wifi + charging gated)";
  extraOptions = {
    intervalSec = lib.mkOption {
      type = lib.types.ints.positive;
      default = 1800;
      description = "Seconds between drain attempts. Cheap to check often -- the script itself skips instantly when conditions aren't met.";
    };
  };
  surface = {
    unit = "sinnix-phone-drain.service";
    manager = "user";
    resourceClass = "capture-runtime";
    observe = {
      enable = true;
      restartable = true;
    };
    # sinnix-uyvt.2.1 (4): a dead phone mic and a quiet room are otherwise
    # indistinguishable -- this is a proxy on the LAKE side (when did the
    # drain last actually land a new chunk), not a direct liveness check on
    # the phone-side recorder, so the threshold is generous: the drain is
    # conditional (wifi + charging), and a phone off both for many hours is
    # a real, non-alarming gap, not evidence the mic died.
    captures = [
      {
        name = "phone-ambient";
        path = "/realm/data/captures/phone/ambient";
        cadenceSeconds = 1800;
        staleAfterSeconds = 86400;
      }
    ];
  };
  configFn =
    { cfg, ... }:
    {
      systemd.user.services.sinnix-phone-drain = {
        description = "Pull phone capture lanes into the data lake, if on wifi + charging";
        serviceConfig = {
          Type = "oneshot";
          ExecStart = "${scriptPkgs.sinnix-phone}/bin/sinnix-phone drain";
        };
      };

      systemd.user.timers.sinnix-phone-drain = {
        description = "Periodic trigger for the phone drain check";
        wantedBy = [ "timers.target" ];
        timerConfig = {
          OnBootSec = "5min";
          OnUnitActiveSec = "${toString cfg.intervalSec}s";
          AccuracySec = "1min";
        };
      };
    };
} args
