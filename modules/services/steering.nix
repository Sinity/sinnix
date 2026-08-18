# steering: the operator-instrumentation walking skeleton.
#
# Store: sqlite at /realm/project/steering/steering.sqlite (created by
# sinnix-steer on first run; the CLI source lives in the steering workspace
# itself, consumed via the `steering` flake input). This lives on
# the persistent /realm NVMe volume, not under the ephemeral root subvolume,
# so no impermanence persistence entry is needed -- only a tmpfiles rule to
# create the directory on first activation.
#
# Two systemd user timers run the morning/evening rituals (each invokes
# `claude -p` with store context, writes a review row, notifies via
# notify-send); a third service runs the read-only cockpit (FastAPI+htmx,
# pkgs/sinnix-cockpit) on loopback.
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
  capturesRoot = config.sinnix.paths.activityRoot;
  scriptPkgs = helpers.mkSinnixPackagesFor pkgs;
  steer = scriptPkgs.sinnix-steer;
  cockpit = scriptPkgs.sinnix-cockpit;
  stateDir = "/realm/project/steering";
  exportDir = "${capturesRoot}/steering";
in
mkServiceModule {
  name = "steering";
  description = "Operator steering store, rituals, and read-only cockpit (sinnix-jfiy.1)";
  extraOptions = {
    morningTime = lib.mkOption {
      type = lib.types.str;
      default = "08:00";
      description = "OnCalendar time-of-day for the morning intention ritual.";
    };
    eveningTime = lib.mkOption {
      type = lib.types.str;
      default = "21:30";
      description = "OnCalendar time-of-day for the evening review ritual.";
    };
    cockpitPort = lib.mkOption {
      type = lib.types.port;
      default = 8791;
      description = "Loopback port for the read-only cockpit (FastAPI+htmx).";
    };
  };
  surface = {
    unit = "sinnix-steering-morning.service";
    manager = "user";
    resourceClass = "interactive-agent";
    observe.enable = true;
  };
  configFn =
    { cfg, config, ... }:
    lib.mkMerge [
      # Morning/evening/export are each an oneshot-on-a-timer, so they go
      # through mkScheduledJob directly rather than mkServiceModule's `job`
      # sugar: a job binds exactly one unit and this module owns three (plus
      # the non-scheduled cockpit service below). `steer` reaches PATH via
      # environment.systemPackages below already; no separate home.packages
      # entry is needed. Shared env: both rituals and export need to agree on
      # store/export paths with the CLI's own defaults (sinnix-steer in the
      # steering workspace).
      (lib.sinnix.mkScheduledJob
        {
          inherit config;
          unitName = "sinnix-steering-morning";
          description = "Morning steering ritual (root-probe + decide-once intentions)";
          surface = config.sinnix.runtime.surfaces.steering;
        }
        {
          manager = "user";
          resourceClass = "interactive-agent";
          execStart = "${steer}/bin/sinnix-steer ritual morning";
          environment = {
            SINNIX_STEERING_STATE_DIR = stateDir;
            SINNIX_STEERING_EXPORT_DIR = exportDir;
          };
          timer = {
            onCalendar = "*-*-* ${cfg.morningTime}:00";
            persistent = true;
            accuracySec = "5min";
            description = "Daily trigger for the morning steering ritual";
          };
        }
      )
      (lib.sinnix.mkScheduledJob
        {
          inherit config;
          unitName = "sinnix-steering-evening";
          description = "Evening steering review ritual";
          surface = config.sinnix.runtime.surfaces.steering-evening;
        }
        {
          manager = "user";
          resourceClass = "interactive-agent";
          execStart = "${steer}/bin/sinnix-steer ritual evening";
          environment = {
            SINNIX_STEERING_STATE_DIR = stateDir;
            SINNIX_STEERING_EXPORT_DIR = exportDir;
          };
          timer = {
            onCalendar = "*-*-* ${cfg.eveningTime}:00";
            persistent = true;
            accuracySec = "5min";
            description = "Daily trigger for the evening steering review";
          };
        }
      )
      # Daily JSONL export, independent of the rituals so the lake gets the
      # raw store even on a day neither ritual runs.
      (lib.sinnix.mkScheduledJob
        {
          inherit config;
          unitName = "sinnix-steering-export";
          description = "Export the steering store to the capture lake";
          surface = config.sinnix.runtime.surfaces.steering-export;
        }
        {
          manager = "user";
          resourceClass = "interactive-agent";
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
        environment.systemPackages = [
          steer
          cockpit
        ];
        systemd.tmpfiles.rules = [
          "d ${stateDir} 0700 ${username} users -"
          "d ${exportDir} 0755 ${username} users -"
        ];

        sinnix.runtime.surfaces.steering-evening = {
          unit = "sinnix-steering-evening.service";
          manager = "user";
          resourceClass = "interactive-agent";
          observe.enable = true;
        };
        sinnix.runtime.surfaces.steering-export = {
          unit = "sinnix-steering-export.service";
          manager = "user";
          resourceClass = "interactive-agent";
          observe.enable = true;
          captures = [
            {
              name = "steering";
              path = exportDir;
              # Unconditional: the exporter runs at 23:50 and writes the day's
              # file whether or not the operator did a ritual, so silence here
              # measures the exporter rather than the operator -- which is what
              # makes a budget honest for this lane and not for the ones whose
              # content depends on him having something to say.
              cadenceSeconds = 86400;
              # One missed day tolerated; two is a dead timer.
              staleAfterSeconds = 172800;
            }
          ];
        };
        sinnix.runtime.surfaces.cockpit = {
          unit = "sinnix-cockpit.service";
          manager = "user";
          resourceClass = "interactive-agent";
          observe = {
            enable = true;
            restartable = true;
          };
          workload = {
            class = "protected";
            rationale = "Read-only steering cockpit; no lifecycle actions, loopback-only.";
            processMatchers = [ "sinnix-cockpit" ];
            earlyoomAvoid = true;
          };
        };

        systemd.user.services.sinnix-cockpit = {
          description = "Sinnix steering cockpit (read-only FastAPI+htmx)";
          serviceConfig = lib.sinnix.mkRuntimeServiceConfig {
            runtimeInventory = config.sinnix.runtime.inventory;
            unit = "sinnix-cockpit.service";
            overrides = {
              Type = "simple";
              # Idempotent (checks existing activity names before inserting), so
              # this runs harmlessly on every start -- it's what guarantees the
              # cockpit has seed data to render on a fresh install rather than
              # requiring a manual `sinnix-steer seed` first.
              ExecStartPre = "${steer}/bin/sinnix-steer seed";
              ExecStart = "${cockpit}/bin/sinnix-cockpit --port ${toString cfg.cockpitPort}";
              Restart = "on-failure";
              RestartSec = "5s";
              Environment = [
                "SINNIX_STEERING_STATE_DIR=${stateDir}"
                "SINNIX_COCKPIT_PORT=${toString cfg.cockpitPort}"
              ];
            };
          };
          wantedBy = [ "default.target" ];
        };
      }
    ];
} args
