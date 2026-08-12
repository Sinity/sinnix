# ActivityWatch bucket-event rollup into the captures lake (sinnix-9pd
# Phase 3a, 3.6). See pkgs/capture-aw-rollup/rollup.py's module docstring
# for the full rationale: the `activitywatch` service (activitywatch.nix)
# keeps its own SQLite DB under a persisted home directory, not the
# captures lake, so this periodic pull over AW's REST API is what
# actually makes the `activitywatch` capture lane real. Depends on
# `sinnix.features.desktop.activitywatch.enable` for a server to poll;
# this module does not enable that feature itself.
{
  mkServiceModule,
  lib,
  pkgs,
  config,
  helpers,
  ...
}@args:
let
  username = config.sinnix.user.name;
  scriptPkgs = helpers.mkSinnixPackagesFor pkgs;
  capturesRoot = config.sinnix.paths.capturesRoot;
  laneDir = "${capturesRoot}/activitywatch";
  stateDir = "${capturesRoot}/aw-rollup/state";

  rollup = pkgs.writeTextFile {
    name = "capture-aw-rollup";
    destination = "/bin/capture-aw-rollup";
    executable = true;
    text = ''
      #!${pkgs.python3}/bin/python3
    ''
    + builtins.readFile ../../pkgs/capture-aw-rollup/rollup.py;
  };
in
mkServiceModule {
  name = "capture-aw-rollup";
  description = "Periodic ActivityWatch bucket-event pull into the activitywatch capture lane";
  extraOptions = {
    intervalMinutes = lib.mkOption {
      type = lib.types.ints.positive;
      default = 15;
      description = "Minutes between rollup runs.";
    };
  };
  surface = {
    unit = "sinnix-capture-aw-rollup.service";
    manager = "user";
    resourceClass = "capture-runtime";
    observe = {
      enable = true;
      restartable = false;
    };
    captures = [
      {
        name = "activitywatch";
        path = laneDir;
        eventDriven = true;
        # Matches the budget the surface carried before this module
        # existed (activitywatch.nix, pre-revival): an hour of total
        # AW silence (no window/AFK activity at all) is a real signal.
        staleAfterSeconds = 3600;
      }
    ];
  };
  configFn =
    { cfg, config, ... }:
    {
      systemd.tmpfiles.rules = [
        "d ${laneDir} 0755 ${username} users -"
        "d ${stateDir} 0700 ${username} users -"
      ];

      home-manager.users.${username} = {
        systemd.user.services.sinnix-capture-aw-rollup = {
          Unit = {
            Description = "ActivityWatch bucket-event rollup";
            After = [
              "graphical-session.target"
              "activitywatch.service"
            ];
          };
          Service = lib.sinnix.mkRuntimeServiceConfig {
            runtimeInventory = config.sinnix.runtime.inventory;
            unit = "sinnix-capture-aw-rollup.service";
            overrides = {
              Type = "oneshot";
              ExecStart = lib.escapeShellArgs [
                "${rollup}/bin/capture-aw-rollup"
                "--capture-root"
                capturesRoot
                "--lane"
                "activitywatch"
                "--state-file"
                "${stateDir}/watermarks.json"
                "--sinnix-capture-bin"
                "${scriptPkgs.sinnix-capture}/bin/sinnix-capture"
              ];
              NoNewPrivileges = true;
              ProtectSystem = "strict";
              ProtectHome = "read-only";
              ReadWritePaths = [
                laneDir
                stateDir
              ];
            };
          };
        };

        systemd.user.timers.sinnix-capture-aw-rollup = {
          Unit.Description = "Periodic trigger for the ActivityWatch rollup";
          Timer = {
            OnUnitActiveSec = "${toString cfg.intervalMinutes}min";
            OnStartupSec = "3min";
            Persistent = true;
          };
          Install.WantedBy = [ "timers.target" ];
        };
      };
    };
} args
