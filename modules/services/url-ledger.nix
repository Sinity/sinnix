# URL x visit x archive-snapshot coverage ledger. Daily evidence join:
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
  description = "Daily URL visit x archive-snapshot coverage ledger";
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
          rationale = "Read-only join against public archive indexes; rerunnable at will.";
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
            ExecStart = "${scriptPkgs.sinnix-url-ledger}/bin/sinnix-url-ledger run --max-requests ${toString cfg.maxRequestsPerRun} --max-seconds ${toString cfg.maxSecondsPerRun} --window-days ${toString cfg.windowDays}";
            # The script stops itself at maxSecondsPerRun; this is the backstop
            # for a wedged provider socket, not the normal bound.
            RuntimeMaxSec = cfg.maxSecondsPerRun + 900;
          };
        };
      };
      systemd.timers.sinnix-url-ledger = {
        wantedBy = [ "timers.target" ];
        timerConfig = {
          OnCalendar = "daily";
          Persistent = true;
          RandomizedDelaySec = "2h";
        };
      };
    };
  extraOptions = {
    maxRequestsPerRun = args.lib.mkOption {
      type = args.lib.types.int;
      default = 200000;
      description = ''
        Backstop bound on provider queries per run. maxSecondsPerRun is the
        real control; this only catches a pathologically fast failure loop.

        The old pairing of 2000 queries with a weekly timer could not finish:
        540k history URLs across two live providers is ~1.1M queries, which at
        2000 a week is measured in centuries. Resolve is resumable, so the
        backfill converges only if a run's budget is a meaningful fraction of
        the work.
      '';
    };
    maxSecondsPerRun = args.lib.mkOption {
      type = args.lib.types.int;
      default = 7200;
      description = "Wall-clock budget per run. Bounds what actually matters -- that a run finishes inside its own interval -- since query cost varies by two orders of magnitude.";
    };
    windowDays = args.lib.mkOption {
      type = args.lib.types.int;
      default = 30;
      description = "Coverage window in days for the nearest-snapshot-to-visit join.";
    };
  };
} args
