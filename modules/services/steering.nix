# steering: the estate's memory for the operator's own intentions. What it
# is and what every surface shows: docs/steering.md.
#
# Store: sqlite at /realm/project/steering/repo/steering.sqlite (created by
# sinnix-steer on first run; the CLI source lives in the steering workspace
# itself, consumed via the `steering` flake input). This lives on
# the persistent /realm NVMe volume, not under the ephemeral root subvolume,
# so no impermanence persistence entry is needed -- only a tmpfiles rule to
# create the directory on first activation.
#
# One nightly user timer exports the store to the capture lake.
{
  mkServiceModule,
  pkgs,
  lib,
  config,
  helpers,
  ...
}@args:
let
  username = config.sinnix.user.name;
  scriptPkgs = helpers.mkSinnixPackagesFor pkgs;
  steer = scriptPkgs.sinnix-steer;
  stateDir = "/realm/project/steering/repo";
  exportDir = "${config.sinnix.paths.capturePaths.steering}";
in
mkServiceModule {
  name = "steering";
  description = "Personal steering: intention store and its nightly export";
  docs = "docs/steering.md";
  surface = {
    unit = "sinnix-steering-export.service";
    manager = "user";
    resourceClass = "ordinary";
    observe.enable = true;
    captures = [
      {
        name = "steering";
        path = exportDir;
        # Unconditional: the exporter writes the day's file whether or not
        # the store changed, so silence here measures the exporter.
        cadenceSeconds = 86400;
        # One missed day tolerated; two is a dead timer.
        staleAfterSeconds = 172800;
      }
    ];
  };
  configFn =
    { cfg, config, ... }:
    lib.mkMerge [
      (lib.sinnix.mkScheduledJob
        {
          inherit config;
          unitName = "sinnix-steering-export";
          description = "Export the steering store to the capture lake";
          surface = config.sinnix.runtime.surfaces.steering;
        }
        {
          manager = "user";
          resourceClass = "ordinary";
          serviceConfig.UMask = "0077";
          execStart = "${steer}/bin/sinnix-steer export";
          environment = {
            SINNIX_STEERING_STATE_DIR = stateDir;
            SINNIX_STEERING_EXPORT_DIR = exportDir;
          };
          timer = {
            onCalendar = "*-*-* 23:50:00";
            persistent = true;
            accuracySec = "10min";
            description = "Nightly trigger for the steering store export";
          };
        }
      )
      {
        # `steer` reaches PATH here; no separate home.packages entry needed.
        environment.systemPackages = [ steer ];
        systemd.tmpfiles.rules = [
          "d ${stateDir} 0700 ${username} users -"
          "d ${exportDir} 0700 ${username} users -"
        ];
      }
    ];
} args
