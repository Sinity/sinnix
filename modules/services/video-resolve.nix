# Video special-case over the URL ledger. Neither Wayback nor Common Crawl
# preserves video content -- their CDX coverage check only proves a page
# existed, not that the video survives -- so URLs on known video-hosting
# domains get resolved into a real yt-dlp'd copy instead of relying on the
# archive-availability join sinnix-url-ledger does for everything else. Runs
# after the ledger's weekly build so it has a fresh parquet to query.
{
  mkServiceModule,
  config,
  lib,
  helpers,
  pkgs,
  ...
}@args:
mkServiceModule {
  name = "video-resolve";
  description = "yt-dlp resolution of video-hosting URLs found in the URL ledger";
  configFn =
    { ... }:
    let
      scriptPkgs = helpers.mkSinnixPackagesFor pkgs;
      archiveRoot = "${config.sinnix.paths.capturesRoot}/video-resolve";
      ledgerParquet = "${config.sinnix.paths.dataRoot}/derived/url-ledger/url_ledger.parquet";
    in
    {
      sinnix.runtime.surfaces.video-resolve = {
        unit = "sinnix-video-resolve.service";
        resourceClass = "background-maintenance";
        observe.enable = true;
        workload = {
          class = "sacrificial";
          rationale = "Weekly, rerunnable at will; yt-dlp's own download-archive de-dups across runs.";
        };
        captures = [
          {
            name = "video-resolve";
            path = archiveRoot;
            eventDriven = true;
          }
        ];
      };
      systemd.services.sinnix-video-resolve = {
        description = "Resolve video-hosting URLs from the URL ledger into archived copies";
        # Weekly oneshot that shells out to yt-dlp for as long as the queue
        # takes; a switch has no business restarting it or waiting on it. It
        # was also queued behind sinnix-url-ledger in the same blocked
        # activation, since it is ordered after it.
        restartIfChanged = false;
        # Ordering only, and only within a shared transaction -- which two
        # independent timers never have, so this alone never sequenced
        # anything. The real dependency is the artifact: the script exits 1
        # when the ledger parquet is absent, so a run that lands before the
        # ledger has ever built reports a failure for a precondition it does
        # not own. The condition below turns that into a skip, which is what
        # "my input does not exist yet" actually is.
        after = [ "sinnix-url-ledger.service" ];
        unitConfig.ConditionPathExists = [ ledgerParquet ];
        serviceConfig = lib.sinnix.mkRuntimeServiceConfig {
          runtimeInventory = config.sinnix.runtime.inventory;
          unit = "sinnix-video-resolve.service";
          overrides = {
            Type = "oneshot";
            User = config.sinnix.user.name;
            ExecStart = "${scriptPkgs.sinnix-video-resolve}/bin/sinnix-video-resolve";
          };
        };
      };
      systemd.timers.sinnix-video-resolve = {
        wantedBy = [ "timers.target" ];
        timerConfig = {
          OnCalendar = "weekly";
          Persistent = true;
          RandomizedDelaySec = "3h";
        };
      };
    };
} args
