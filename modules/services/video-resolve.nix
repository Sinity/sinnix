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
let
  scriptPkgs = helpers.mkSinnixPackagesFor pkgs;
  archiveRoot = "${config.sinnix.paths.activityRoot}/video-resolve";
  ledgerParquet = "${config.sinnix.paths.activityRoot}/url-ledger/url_ledger.parquet";
in
mkServiceModule {
  name = "video-resolve";
  description = "yt-dlp resolution of video-hosting URLs found in the URL ledger";
  surface = {
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
  job = {
    description = "Resolve video-hosting URLs from the URL ledger into archived copies";
    user = config.sinnix.user.name;
    execStart = "${scriptPkgs.sinnix-video-resolve}/bin/sinnix-video-resolve";
    timer = {
      onCalendar = "weekly";
      persistent = true;
      randomizedDelaySec = "3h";
    };
    unit = {
      # Weekly oneshot that shells out to yt-dlp for as long as the queue
      # takes; a switch has no business restarting it or waiting on it.
      restartIfChanged = false;
      # Ordering only, and only within a shared transaction -- which two
      # independent timers never have. The real dependency is the artifact:
      # the script exits 1 when the ledger parquet is absent, so the
      # condition turns "my input does not exist yet" into a skip instead
      # of a reported failure.
      after = [ "sinnix-url-ledger.service" ];
      unitConfig.ConditionPathExists = [ ledgerParquet ];
    };
  };
} args
