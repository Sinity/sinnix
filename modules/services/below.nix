# below: Time-traveling resource monitor for Linux
#
# Records system state continuously for post-mortem debugging.
# Use `below replay` to investigate what happened at any point in time.
#
# Data stored under storeDir (defaults to /realm/data/captures/machine/below
# — same realm subtree as the rest of machine telemetry). Earlier installs
# wrote to /var/log/below; the rollover lives in the dotfile/agent retrospective
# trail. Retention is indefinite: at 1 s with dict-compress (chunk-32, ~8.8×
# over plain zstd) this is ~720 MB/day = ~260 GB/year. Export via:
# below dump -O json/csv. Excluded from Borg in modules/backup.nix.
{
  mkServiceModule,
  lib,
  pkgs,
  helpers,
  ...
}@args:
let
  scriptPkgs = helpers.mkSinnixPackagesFor pkgs;
in
mkServiceModule {
  name = "below";
  description = "below time-traveling resource monitor";
  surface = {
    unit = "below.service";
    resourceClass = "observability";
    observe = {
      enable = true;
      restartable = true;
    };
  };
  extraOptions = {
    collectIntervalSec = lib.mkOption {
      type = lib.types.int;
      default = 1;
      description = "Collection interval in seconds.";
    };
    storeDir = lib.mkOption {
      type = lib.types.path;
      default = "/var/log/below";
      description = "Below data directory — keeps store/, home/, cache/, state/ subtrees. Set to a path on /realm if you want telemetry kept off the root filesystem.";
    };
  };
  configFn =
    {
      cfg,
      config,
      pkgs,
      ...
    }:
    {
      environment.systemPackages = [
        pkgs.below
        scriptPkgs.sinnix-observe
      ];

      # below 0.11+ reads store_dir/log_dir from /etc/below/below.conf;
      # the --store-dir CLI flag was removed. Generate the config so data
      # stays on the configured storeDir (e.g. /realm on prime).
      environment.etc."below/below.conf".text = ''
        store_dir = "${cfg.storeDir}/store"
        log_dir = "${cfg.storeDir}"
      '';

      systemd.tmpfiles.rules = [
        "d ${cfg.storeDir} 0755 root root -"
        "d ${cfg.storeDir}/store 0755 root root -"
        "d ${cfg.storeDir}/home 0755 root root -"
        "d ${cfg.storeDir}/cache 0755 root root -"
        "d ${cfg.storeDir}/state 0755 root root -"
      ];

      systemd.services.below =
        let
          storeOnRealm = lib.hasPrefix "/realm/" cfg.storeDir;
        in
        {
          description = "below - Time traveling resource monitor";
          wantedBy = [ "multi-user.target" ];
          after = [ "local-fs.target" ] ++ lib.optional storeOnRealm "realm.mount";
          requires = lib.optional storeOnRealm "realm.mount";

          serviceConfig = {
            Type = "simple";
            ExecStart = "${pkgs.below}/bin/below record --collect-io-stat --compress --dict-compress-chunk-size 32 --interval-s ${toString cfg.collectIntervalSec}";
            Restart = "on-failure";
            RestartSec = "5s";
          }
          // lib.sinnix.mkRuntimeServiceConfig {
            runtimeInventory = config.sinnix.runtime.inventory;
            unit = "below.service";
          };
        };

    };
} args
