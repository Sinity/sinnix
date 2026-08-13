# steering: the operator-instrumentation walking skeleton.
#
# Store: sqlite at /realm/state/steering/steering.sqlite (created by
# sinnix-steer on first run; schema v1 in scripts/sinnix-steer). This lives on
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
  inherit (config.sinnix.paths) capturesRoot;
  scriptPkgs = helpers.mkSinnixPackagesFor pkgs;
  steer = scriptPkgs.sinnix-steer;
  cockpit = scriptPkgs.sinnix-cockpit;
  stateDir = "/realm/state/steering";
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

      home-manager.users.${username} =
        { ... }:
        {
          home.packages = [
            steer
            cockpit
          ];

          # Shared env: both rituals and export need to agree on store/export
          # paths with the CLI's own defaults (scripts/sinnix-steer).
          systemd.user.services.sinnix-steering-morning = {
            Unit.Description = "Morning steering ritual (root-probe + decide-once intentions)";
            Service = lib.sinnix.mkRuntimeServiceConfig {
              runtimeInventory = config.sinnix.runtime.inventory;
              unit = "sinnix-steering-morning.service";
              overrides = {
                Type = "oneshot";
                ExecStart = "${steer}/bin/sinnix-steer ritual morning";
                Environment = [
                  "SINNIX_STEERING_STATE_DIR=${stateDir}"
                  "SINNIX_STEERING_EXPORT_DIR=${exportDir}"
                ];
              };
            };
          };
          systemd.user.timers.sinnix-steering-morning = {
            Unit.Description = "Daily trigger for the morning steering ritual";
            Timer = {
              OnCalendar = "*-*-* ${cfg.morningTime}:00";
              Persistent = true;
              AccuracySec = "5min";
            };
            Install.WantedBy = [ "timers.target" ];
          };

          systemd.user.services.sinnix-steering-evening = {
            Unit.Description = "Evening steering review ritual";
            Service = lib.sinnix.mkRuntimeServiceConfig {
              runtimeInventory = config.sinnix.runtime.inventory;
              unit = "sinnix-steering-evening.service";
              overrides = {
                Type = "oneshot";
                ExecStart = "${steer}/bin/sinnix-steer ritual evening";
                Environment = [
                  "SINNIX_STEERING_STATE_DIR=${stateDir}"
                  "SINNIX_STEERING_EXPORT_DIR=${exportDir}"
                ];
              };
            };
          };
          systemd.user.timers.sinnix-steering-evening = {
            Unit.Description = "Daily trigger for the evening steering review";
            Timer = {
              OnCalendar = "*-*-* ${cfg.eveningTime}:00";
              Persistent = true;
              AccuracySec = "5min";
            };
            Install.WantedBy = [ "timers.target" ];
          };

          # Daily JSONL export, independent of the rituals so the lake gets
          # the raw store even on a day neither ritual runs.
          systemd.user.services.sinnix-steering-export = {
            Unit.Description = "Export the steering store to the capture lake";
            Service = lib.sinnix.mkRuntimeServiceConfig {
              runtimeInventory = config.sinnix.runtime.inventory;
              unit = "sinnix-steering-export.service";
              overrides = {
                Type = "oneshot";
                ExecStart = "${steer}/bin/sinnix-steer export";
                Environment = [
                  "SINNIX_STEERING_STATE_DIR=${stateDir}"
                  "SINNIX_STEERING_EXPORT_DIR=${exportDir}"
                ];
              };
            };
          };
          systemd.user.timers.sinnix-steering-export = {
            Unit.Description = "Nightly trigger for the steering store export";
            Timer = {
              OnCalendar = "*-*-* 23:50:00";
              Persistent = true;
              AccuracySec = "10min";
            };
            Install.WantedBy = [ "timers.target" ];
          };

          systemd.user.services.sinnix-cockpit = {
            Unit.Description = "Sinnix steering cockpit (read-only FastAPI+htmx)";
            Service = lib.sinnix.mkRuntimeServiceConfig {
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
            Install.WantedBy = [ "default.target" ];
          };
        };
    };
} args
