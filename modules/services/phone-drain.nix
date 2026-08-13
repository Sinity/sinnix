# Drain-on-a-schedule for the phone-side capture lanes, gated on wifi rather
# than pulled manually. Wraps `sinnix-phone drain` (scripts/sinnix-phone),
# which does the actual reachability/wifi checks and skips quietly when
# conditions aren't met -- this unit only provides the schedule. The wifi
# gate is deliberate: this is the large/opportunistic raw-audio tier, not a
# small always-on VAD-gated stream.
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
  description = "Scheduled phone -> lake drain (wifi gated)";
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
    # A dead phone mic and a quiet room are otherwise indistinguishable, so
    # this watches the LAKE side (did the drain land a new chunk) rather than
    # the phone-side recorder. The threshold is generous because the drain is
    # wifi-conditional: a phone off wifi for hours is a real, non-alarming
    # gap, not evidence the mic died.
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
        description = "Pull phone capture lanes into the data lake, if on wifi";
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
