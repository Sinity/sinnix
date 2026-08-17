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
      unit = {
        # A switch must not restart or wait on this: a daily oneshot with a
        # two-hour budget held an activation for 2h15m on 2026-08-17, with
        # video-resolve queued behind it. The next timer firing picks up new
        # code, which is all a periodic job needs. Same reasoning as the
        # borg drain jobs in modules/backup.nix.
        restartIfChanged = false;
      };
    };
} args
