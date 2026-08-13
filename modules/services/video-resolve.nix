# Video special-case over the URL ledger (sinnix-e8k9, split from the
# web-capture bead). Neither Wayback nor Common Crawl actually preserve
# video content -- their CDX coverage check only proves a page existed,
# not that the video survives -- so URLs on known video-hosting domains
# get resolved into a real yt-dlp'd copy instead of relying on the
# archive-availability join sinnix-url-ledger already does for everything
# else. Runs after the ledger's own weekly build so it has a fresh
# parquet to query.
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
        after = [ "sinnix-url-ledger.service" ];
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
