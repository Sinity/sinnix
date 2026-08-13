# URL x visit x archive-snapshot coverage ledger. Weekly evidence join:
# browser-history URLs against public archive CDX indexes (Wayback, Common
# Crawl, Memento). Read-only against third-party archive APIs; no crawling,
# no SavePageNow -- it reports coverage gaps, it does not act on them.
{
  mkServiceModule,
  config,
  lib,
  helpers,
  pkgs,
  ...
}@args:
mkServiceModule {
  name = "url-ledger";
  description = "Weekly URL visit x archive-snapshot coverage ledger";
  configFn =
    { cfg, ... }:
    let
      scriptPkgs = helpers.mkSinnixPackagesFor pkgs;
      stateDir = "${config.sinnix.paths.capturesRoot}/url-ledger/state";
      cdxRawDir = "${config.sinnix.paths.capturesRoot}/url-ledger/cdx-raw";
      derivedDir = "${config.sinnix.paths.dataRoot}/derived/url-ledger";
    in
    {
      sinnix.runtime.surfaces.url-ledger = {
        unit = "sinnix-url-ledger.service";
        resourceClass = "background-maintenance";
        observe.enable = true;
        workload = {
          class = "sacrificial";
          rationale = "Weekly read-only join against public archive CDX APIs; rerunnable at will.";
        };
        captures = [
          {
            name = "url-ledger-state";
            path = stateDir;
            eventDriven = true;
          }
          {
            name = "url-ledger-coverage";
            path = derivedDir;
            eventDriven = true;
          }
        ];
      };
      systemd.services.sinnix-url-ledger = {
        description = "URL visit x archive-snapshot coverage ledger";
        serviceConfig = lib.sinnix.mkRuntimeServiceConfig {
          runtimeInventory = config.sinnix.runtime.inventory;
          unit = "sinnix-url-ledger.service";
          overrides = {
            Type = "oneshot";
            # Reads the operator's webhistory capture and writes into the
            # operator-owned data lake.
            User = config.sinnix.user.name;
            ExecStart = "${scriptPkgs.sinnix-url-ledger}/bin/sinnix-url-ledger run --max-requests ${toString cfg.maxRequestsPerRun} --window-days ${toString cfg.windowDays}";
          };
        };
      };
      systemd.timers.sinnix-url-ledger = {
        wantedBy = [ "timers.target" ];
        timerConfig = {
          OnCalendar = "weekly";
          Persistent = true;
          RandomizedDelaySec = "2h";
        };
      };
    };
  extraOptions = {
    maxRequestsPerRun = args.lib.mkOption {
      type = args.lib.types.int;
      default = 2000;
      description = "Bound on provider CDX queries per weekly run (resolve is resumable across runs).";
    };
    windowDays = args.lib.mkOption {
      type = args.lib.types.int;
      default = 30;
      description = "Coverage window in days for the nearest-snapshot-to-visit join.";
    };
  };
} args
