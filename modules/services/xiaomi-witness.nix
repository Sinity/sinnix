# Xiaomi cloud vendor witness: the band's data read from Xiaomi's servers,
# beside (not through) the phone's Health Connect lane.
#
# Why it exists (sinnix-ogll, measured 2026-08-17): Mi Fitness writes to
# Health Connect only when its on-screen Sync button is pressed -- the forced
# SyncJobService was tested and writes nothing -- but it syncs Xiaomi's cloud
# silently, so the cloud held heart rate two hours fresher than HC on the
# night this was built. The cloud sleep summaries also carry sleep_score,
# REM duration and per-segment naps that the HC write path never gets. This
# service polls that cloud with a QR-established token (one browser-session
# confirmation, agent-drivable; token refresh sustains it) and appends
# write-on-change envelopes to the lane.
#
# No BLE contention by construction: this never talks to the band, so it can
# never fight Mi Fitness for the bond the way Gadgetbridge does.
{
  mkServiceModule,
  lib,
  pkgs,
  helpers,
  ...
}@args:
let
  scriptPkgs = helpers.mkSinnixPackagesFor pkgs;
  stateDir = "/realm/state/xiaomi-witness";
  # Under health/, where the 2026-08-17 subject recut moved this lane's files
  # while the service was running -- the writer kept its old captures/ path and
  # would have split the lane in two on the next changed envelope. A literal,
  # like stateDir above, because this `let` runs outside the module's config
  # scope; point it at paths.healthRoot once that option lands.
  laneDir = "/realm/data/health/xiaomi-cloud";
in
mkServiceModule {
  name = "xiaomi-witness";
  description = "Xiaomi cloud health witness (band data via Xiaomi's servers)";
  extraOptions = {
    intervalSec = lib.mkOption {
      type = lib.types.ints.positive;
      default = 1800;
      description = "Seconds between cloud sync passes. The cloud itself lags the band by Mi Fitness's own sync cadence (hours), so this bounds our half of the latency, not the total.";
    };
  };
  surface = {
    unit = "sinnix-xiaomi-witness.service";
    manager = "user";
    resourceClass = "capture-runtime";
    observe = {
      enable = true;
      restartable = true;
    };
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
  # The timer's own Description= is dropped: the factory's generated timer
  # body carries no description field, unlike the hand-written one it
  # replaces -- cosmetic only, doesn't affect scheduling.
  job =
    { cfg, ... }:
    {
      description = "Xiaomi cloud health witness sync pass";
      manager = "user";
      execStart = lib.getExe scriptPkgs.sinnix-xiaomi-witness;
      # The module declares this lane to the runtime inventory and creates
      # its directory, so it must also be what the writer uses. It was
      # not: both sides carried the same literal independently, and when
      # the lane moved, the declaration followed and the writer did not.
      environment = {
        XIAOMI_WITNESS_LANE = laneDir;
        XIAOMI_WITNESS_STATE = stateDir;
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
      "d ${laneDir} 0755 sinity users -"
    ];
  };
} args
