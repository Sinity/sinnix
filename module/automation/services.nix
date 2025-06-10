# Automation Services
# System services and daemons

{ pkgs, ... }:
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
        enable = true;
        acceleration = "cuda";
      };

      # Monero service (commented out for easy enablement)
      # monero = {
      #   enable = true;
      #   dataDir = "/var/lib/monero";
      # };.
      postgresql = {
        enable = true;
        package = pkgs.postgresql_16;
        extensions =
          ps: with ps; [
            timescaledb
            pgvector
            pgx_ulid # This is a custom package built from source
          ];
        settings = {
          shared_preload_libraries = "timescaledb";
        };
      };
      sinex = {
        enable = true;
        systemUser = "sinity";

        autoConfigureSystem = true;

        ingestors = {
          hyprland = {
            enable = true;
            interval = 1;
          };

          filesystem = {
            enable = true;
            watchDirectories = [
              "~"
              "/realm"
            ];
            excludePatterns = [
              "*.tmp"
              "*.log"
              "*.cache"
              ".git/**"
              "node_modules/**"
              "__pycache__/**"
              "*.swp"
              "*.swo"
              "target/**"
              ".direnv/**"
            ];
            debounceMs = 200;
          };

          kitty = {
            enable = true;
            captureCommands = true;
            captureOutput = true; # Maximalist approach - capture everything
            shellIntegration = true; # Automatic shell markers for command tracking
          };
        };
      };
    };
  };
}
