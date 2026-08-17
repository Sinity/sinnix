# A queryable index of what is actually on this machine's disks, kept
# current. sinnix-fs-inventory (directories) and sinnix-fs-content (document
# files) produced a real 2026-08-16 scan, but nothing invoked either of them
# -- the index was a one-shot, already stale the day after it was built.
# sinnix-fs-ledger then materializes the judgment ledger against that scan
# into resolved judgments, prefix inheritance and a coverage report. All
# three run in sequence here because the ledger step reads the scan's
# output tables.
{
  mkServiceModule,
  config,
  lib,
  helpers,
  pkgs,
  ...
}@args:
let
  scriptPkgs = helpers.mkSinnixPackagesFor pkgs;
  # Regenerable machine artifact (inventory.duckdb, judgments.jsonl), not
  # operator data -- lives on the state side, not under data/.
  indexDir = "${config.sinnix.paths.stateRoot}/fs-index";
in
mkServiceModule {
  name = "fs-index";
  description = "Periodic filesystem inventory, content scan and judgment-ledger materialization";
  surface = {
    unit = "sinnix-fs-index.service";
    resourceClass = "background-maintenance";
    observe.enable = true;
    workload = {
      class = "sacrificial";
      rationale = "Full re-walk of /realm and /outer-realm; rerunnable at will, next timer firing recovers a killed run.";
    };
    captures = [
      {
        name = "fs-index";
        path = indexDir;
        eventDriven = true;
      }
    ];
  };
  job =
    { cfg, ... }:
    {
      description = "Rebuild the filesystem inventory, content scan and judgment ledger";
      user = config.sinnix.user.name;
      # Three scripts, one unit: the ledger step reads the scan's own
      # DuckDB output, so splitting into three units would need a
      # dependency chain for no benefit -- nothing else consumes the
      # scan without the ledger materialized on top of it.
      execStart = pkgs.writeShellScript "sinnix-fs-index-run" ''
        set -euo pipefail
        ${scriptPkgs.sinnix-fs-inventory}/bin/sinnix-fs-inventory --out-dir ${lib.escapeShellArg indexDir}
        ${scriptPkgs.sinnix-fs-content}/bin/sinnix-fs-content --out-dir ${lib.escapeShellArg indexDir}
        ${scriptPkgs.sinnix-fs-ledger}/bin/sinnix-fs-ledger --index-dir ${lib.escapeShellArg indexDir}
      '';
      serviceConfig = {
        TimeoutStartSec = cfg.maxSecondsPerRun;
      };
      timer = {
        onCalendar = cfg.schedule;
        persistent = true;
        randomizedDelaySec = "1h";
      };
      unit = {
        # This walks multiple TB and would otherwise hold a `switch` in
        # activation for its entire run. The next scheduled firing picks up
        # new code.
        restartIfChanged = false;
      };
    };
  extraOptions = {
    schedule = args.lib.mkOption {
      type = args.lib.types.str;
      default = "weekly";
      description = ''
        How often to re-walk the estate. Weekly, not daily: a full scan of
        /realm and /outer-realm is multi-TB and multi-million-file, and the
        judgment ledger it feeds changes by hand-authored rows, not by the
        clock -- there is no benefit to a fresher mechanical scan than the
        rate at which anyone is adding judgments.
      '';
    };
    maxSecondsPerRun = args.lib.mkOption {
      type = args.lib.types.int;
      default = 21600;
      description = "Wall-clock backstop for a wedged run (6h). The scan itself has no internal budget, unlike url-ledger; this is what stops a run overlapping the next timer firing.";
    };
  };
} args
