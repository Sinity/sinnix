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
let
  scriptPkgs = helpers.mkSinnixPackagesFor pkgs;
  stateDir = "${config.sinnix.paths.activityRoot}/url-ledger/state";
  derivedDir = "${config.sinnix.paths.activityRoot}/url-ledger";
in
mkServiceModule {
  name = "url-ledger";
  description = "Daily URL visit x archive-snapshot coverage ledger";
  surface = {
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
  job =
    { cfg, ... }:
    {
      description = "URL visit x archive-snapshot coverage ledger";
      # Reads the operator's webhistory capture and writes into the
      # operator-owned data lake.
      user = config.sinnix.user.name;
      execStart = "${scriptPkgs.sinnix-url-ledger}/bin/sinnix-url-ledger run --max-requests ${toString cfg.maxRequestsPerRun} --max-seconds ${toString cfg.maxSecondsPerRun} --window-days ${toString cfg.windowDays}";
      serviceConfig = {
        # The script stops itself at maxSecondsPerRun; this is the backstop
        # for a wedged provider socket, not the normal bound.
        #
        # TimeoutStartSec, not RuntimeMaxSec: systemd ignores RuntimeMaxSec
        # for Type=oneshot and says so on every start ("RuntimeMaxSec= has
        # no effect in combination with Type=oneshot"), so the backstop was
        # not armed at all. A oneshot spends its whole life "starting", and
        # TimeoutStartSec is the bound that applies there.
        TimeoutStartSec = cfg.maxSecondsPerRun + 900;
      };
      timer = {
        onCalendar = "daily";
        persistent = true;
        randomizedDelaySec = "2h";
      };
    };
  # restartIfChanged=false is not expressible through the job argument, so
  # it's declared here as an independent definition on the same unit -- the
  # module system merges disjoint fields of the same systemd.services.<name>
  # submodule across separate config blocks. A switch must not restart this,
  # and must not wait for it. It is a daily oneshot with a two-hour budget,
  # so a plain restart makes every `switch` block for up to 2h15m in
  # activation while the ledger grinds through its provider queue --
  # observed 2026-08-17, holding the transaction with video-resolve queued
  # behind it. The next timer firing picks up the new code, which is all a
  # periodic job needs. Same reasoning as the borg drain jobs in
  # modules/backup.nix.
  configFn = _: {
    systemd.services.sinnix-url-ledger.restartIfChanged = false;
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
