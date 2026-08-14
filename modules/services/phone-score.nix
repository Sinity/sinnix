# Scoring for the traces the phone hands over, on the same cadence they arrive.
#
# The phone's design deliberately splits the work -- it owns stimulus timing
# and raw signal, prime owns the model -- so every hold-still instrument ends
# by telling the operator a result will come back later. Nothing sent one until
# this unit existed: traces landed in the lake and stopped, and four
# instruments (pulse, tremor, sway, interoception) ended on an unkept promise.
#
# Scheduled slightly behind the drain rather than triggered by it. The drain is
# wifi-gated and can skip for hours, and a scorer chained to it would inherit
# that gate for no reason -- the work is local, cheap, and worth doing the
# moment a trace is on disk, whether it arrived a minute or a day ago.
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
  name = "phone-score";
  description = "Score phone traces and return the receipt";
  extraOptions = {
    intervalSec = lib.mkOption {
      type = lib.types.ints.positive;
      default = 900;
      description = "Seconds between scoring passes. Cheap: the script exits immediately when the outbox holds nothing new.";
    };
  };
  surface = {
    unit = "sinnix-phone-score.service";
    manager = "user";
    resourceClass = "background-maintenance";
    observe = {
      enable = true;
      restartable = true;
    };
    # No captures entry. This lane's freshness is a function of whether the
    # operator ran an instrument, not of whether the machine is healthy -- a
    # week with no PPG trace is a week the operator did not take their pulse,
    # and alarming on it would be alarming about their behaviour.
  };
  configFn =
    { cfg, ... }:
    {
      systemd.user.services.sinnix-phone-score = {
        description = "Score newly drained phone traces and emit receipts";
        serviceConfig = {
          Type = "oneshot";
          ExecStart = "${scriptPkgs.sinnix-score}/bin/sinnix-score run";
        };
      };

      systemd.user.timers.sinnix-phone-score = {
        description = "Periodic scoring of phone traces";
        wantedBy = [ "timers.target" ];
        timerConfig = {
          OnBootSec = "7min";
          OnUnitActiveSec = "${toString cfg.intervalSec}s";
          AccuracySec = "1min";
        };
      };
    };
} args
