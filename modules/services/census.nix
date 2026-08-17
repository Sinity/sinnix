# Usage census — evidence-joined audit of sinnix-owned artifact classes.
# Read-only joins of declaration inventories vs atuin/polylogue/journald
# evidence; JSONL to the machine capture lake. Absence of an evidence source degrades verdicts to
# `unknown`, never to a false `unused`.
{
  mkServiceModule,
  config,
  lib,
  helpers,
  pkgs,
  ...
}@args:
mkServiceModule {
  name = "census";
  description = "Weekly evidence-joined usage census";
  configFn =
    { cfg, ... }:
    let
      scriptPkgs = helpers.mkSinnixPackagesFor pkgs;
      jsonlPath = "${config.sinnix.paths.machineRoot}/usage-census.jsonl";
    in
    {
      sinnix.runtime.surfaces.census = {
        unit = "sinnix-census.service";
        resourceClass = "background-maintenance";
        observe.enable = true;
        workload = {
          class = "sacrificial";
          rationale = "Weekly read-only usage audit; rerunnable at will.";
        };
        captures = [
          {
            name = "usage-census";
            path = jsonlPath;
            eventDriven = true;
          }
        ];
      };
      systemd.services.sinnix-census = {
        description = "Evidence-joined usage census";
        serviceConfig = lib.sinnix.mkRuntimeServiceConfig {
          runtimeInventory = config.sinnix.runtime.inventory;
          unit = "sinnix-census.service";
          overrides = {
            Type = "oneshot";
            # Runs as the operator: the evidence lives in the user's atuin DB,
            # polylogue archive, and user-manager journal.
            User = config.sinnix.user.name;
            ExecStart = "${scriptPkgs.sinnix-census}/bin/sinnix-census --window-days ${toString cfg.windowDays}";
          };
        };
      };
      systemd.timers.sinnix-census = {
        wantedBy = [ "timers.target" ];
        timerConfig = {
          OnCalendar = "weekly";
          Persistent = true;
          RandomizedDelaySec = "2h";
        };
      };
    };
  extraOptions = {
    windowDays = args.lib.mkOption {
      type = args.lib.types.int;
      default = 90;
      description = "Evidence lookback window in days.";
    };
  };
} args
