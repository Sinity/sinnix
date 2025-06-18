# Services
# System services and daemons

{ ... }:
{
  config = {
    services = {
      transmission = {
        enable = true;
        settings = {
          script-torrent-done-enabled = false;
          ratio-limit-enabled = false;
          umask = 18; # 002
          download-dir = "/outer-realm/inbox";
          incomplete-dir-enabled = false;
          rpc-port = 9091;
        };
      };

      ollama = {
        enable = false;
        acceleration = "cuda";
      };

      # Temporarily disabled due to module conflicts
      # sinex = {
      #   enable = true;
      #   preset = "normal";
      #   blobStorage.repositoryPath = /realm/annex;
      #   blobStorage.healthCheck.wantedSize = null;
      #   unifiedCollector.logLevel = "debug";
      #   unifiedCollector.sources.kittyScrollback.captureOnCommand = true;
      #   unifiedCollector.sources.asciinema.autoRecord = true;
      #   unifiedCollector.sources.filesystem.watchPaths = [
      #     "/realm"
      #     "/home/sinity"
      #   ];
      #   # unifiedCollector.sources.filesystem.excludePatterns = [ ];
      # };
    };
  };
}
