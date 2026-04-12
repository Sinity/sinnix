# below: Time-traveling resource monitor for Linux
#
# Records system state continuously for post-mortem debugging.
# Use `below replay` to investigate what happened at any point in time.
#
# Data stored in /var/log/below (default).
# Storage: ~720 MB/day at 1s interval with dict-compress (chunk-32, ~9x over plain zstd).
# Without dict-compress: ~6.5 GB/day. No retention limit — accumulate indefinitely
# (~26 GB/year). below's CBOR format repeats field-name strings per frame;
# dict-compress learns them across adjacent frames for the extra 9x.
# Export via: below dump -O json/csv
{
  mkServiceModule,
  lib,
  pkgs,
  ...
}@args:
mkServiceModule {
  name = "below";
  description = "below time-traveling resource monitor";
  health = {
    unit = "below.service";
    type = "service";
    restartable = true;
  };
  extraOptions = {
    collectIntervalSec = lib.mkOption {
      type = lib.types.int;
      default = 1;
      description = "Collection interval in seconds.";
    };
  };
  configFn =
    { cfg, pkgs, ... }:
    {
      environment.systemPackages = [ pkgs.below ];

      # /var/log/below/store is the below data directory. Create it via tmpfiles
      # so below.service can start even if the /persist bind-mount hasn't activated
      # yet (e.g. first boot without @blank). When impermanence is active, the
      # bind-mount overlays this and persists the data across reboots.
      systemd.tmpfiles.rules = [
        "d /var/log/below 0755 root root -"
        "d /var/log/below/store 0755 root root -"
      ];

      systemd.services.below = {
        description = "below - Time traveling resource monitor";
        wantedBy = [ "multi-user.target" ];
        after = [ "local-fs.target" ];

        serviceConfig = {
          Type = "simple";
          ExecStart = "${pkgs.below}/bin/below record --collect-io-stat --compress --dict-compress-chunk-size 32 --interval-s ${toString cfg.collectIntervalSec}";
          Restart = "on-failure";
          RestartSec = "5s";
        };
      };

    };
} args
