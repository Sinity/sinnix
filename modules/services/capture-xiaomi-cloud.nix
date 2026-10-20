# Capture Xiaomi cloud records independently of phone Health Connect and BLE.
# The writer retains raw samples and vendor summaries as separate records.
{
  mkServiceModule,
  lib,
  pkgs,
  helpers,
  config,
  ...
}@args:
let
  scriptPkgs = helpers.mkSinnixPackagesFor pkgs;
  stateDir = "/realm/state/xiaomi-witness";
  laneDir = "${config.sinnix.paths.healthRoot}/xiaomi-cloud";
in
mkServiceModule {
  name = "capture-xiaomi-cloud";
  description = "Xiaomi cloud health capture (band data via Xiaomi's servers)";
  extraOptions = {
    intervalSec = lib.mkOption {
      type = lib.types.ints.positive;
      default = 1800;
      description = "Seconds between cloud sync passes. The cloud itself lags the band by Mi Fitness's own sync cadence (hours), so this bounds our half of the latency, not the total.";
    };
  };
  surface = {
    unit = "sinnix-capture-xiaomi-cloud.service";
    manager = "user";
    resourceClass = "capture";
    notifyOnFailure = true;
    operatorRestart = true;
    captures = [
      {
        name = "xiaomi-cloud";
        path = laneDir;
        cadenceSeconds = 1800;
        # Write-on-change means a quiet pass appends nothing, and the cloud
        # side goes genuinely quiet when the phone is off. Sleep lands every
        # morning and daily aggregates revise through the day, so half a day
        # with zero changed envelopes is evidence of a broken link (dead
        # token, shard move), not an ordinary gap.
        staleAfterSeconds = 43200;
      }
    ];
  };
  job =
    { cfg, ... }:
    {
      description = "Xiaomi cloud health capture sync pass";
      manager = "user";
      serviceConfig.UMask = "0077";
      # Scheduled and recovery passes share the write-on-change state.
      execStart = "${pkgs.util-linux}/bin/flock --exclusive ${stateDir}/sync.lock ${lib.getExe scriptPkgs.sinnix-capture-xiaomi-cloud}";
      # Keep the writer on the registered lane and shared sync state.
      environment = {
        XIAOMI_CLOUD_LANE = laneDir;
        XIAOMI_CLOUD_STATE = stateDir;
      };
      timer = {
        onBootSec = "3min";
        intervalSec = cfg.intervalSec;
        accuracySec = "5min";
      };
      # A refused token refresh writes this marker after alarming once;
      # the login flow removes it. Until then a firing is skipped, not failed.
      unit.unitConfig.ConditionPathExists = "!${stateDir}/credential-expired";
    };
  configFn = _: {
    # Token + write-on-change hash state. 0700: the token file is a live
    # Xiaomi account credential.
    systemd.tmpfiles.rules = [
      "d ${stateDir} 0700 sinity users -"
      "d ${laneDir} 0700 sinity users -"
    ];
  };
} args
