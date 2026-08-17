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
  };
  # None of these are expressible through the job argument, so they're
  # declared here as independent definitions on the same unit -- the module
  # system merges disjoint fields of the same systemd.services.<name>
  # submodule across separate config blocks.
  configFn = _: {
    systemd.services.sinnix-video-resolve = {
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
    };
  };
} args
