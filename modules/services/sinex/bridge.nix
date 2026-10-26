# Sinex on this host
#
# Host glue between Sinnix and Sinex's NixOS module (`services.sinex`, from the
# pinned `sinex` flake input): where its state lives, the agenix secrets that
# carry the NATS passwords, the operator's session, and the runtime inventory
# entries of its units. The sources a host reads are host facts and are set in
# the host's configuration under `services.sinex.sources`.
#
# State is on /var/lib/sinex, the /state/sinex subvolume on the /realm NVMe
# (hosts/sinnix-prime/storage.nix), outside the realm snapshots:
#   daemon/      API tokens, NATS JetStream, capture spools, and the content
#                store (daemon/store)
#   postgresql/  the PostgreSQL cluster
# State of earlier deployments stays beside them under dated names.
#
# Backups: the content store is archived by the sinex-blobs Borg job
# (modules/backup.nix). The daily database dump lands in
# /realm/state/db-dumps/sinex, inside the realm snapshot and Borg coverage.
#
# Activation never restarts sinexd or its NATS; restart them by hand after a
# deploy and check the running binary.
{
  config,
  lib,
  options,
  ...
}:
let
  cfg = config.sinnix.services.sinex;
  operator = config.sinnix.user.name;
  secrets = config.sinnix.secrets.paths;
  root = "/var/lib/sinex";
  dumpRoot = "${config.sinnix.paths.realmRoot}/state/db-dumps";
  runtimeServiceConfig =
    unit:
    lib.sinnix.mkRuntimeServiceConfig {
      runtimeInventory = config.sinnix.runtime.inventory;
      inherit unit;
    };
in
{
  config = lib.mkIf (options.services ? sinex && cfg.enable) {
    services.sinex = {
      enable = true;
      stateDir = "${root}/daemon";
      database.dataDir = "${root}/postgresql";
      # Shell histories, browser and ActivityWatch databases and the capture
      # lanes are private to the operator; sinexd reads them, never writes.
      readAnyFile = true;
      nats = {
        daemonPasswordFile = secrets.sinex-nats-daemon;
        producers.polylogue.passwordFile = secrets.sinex-nats-polylogue;
      };
      session = {
        enable = true;
        user = operator;
        passwordFile = secrets.sinex-nats-session;
      };
      backup = {
        dumpDir = "${dumpRoot}/sinex";
        # Empty while no source is sealed.
        keysDir = "${dumpRoot}/sinex-keys";
      };
    };

    sinnix.runtime.units = {
      sinexd = {
        unit = "sinexd.service";
        resourceClass = "capture";
        notifyOnFailure = true;
        operatorRestart = false;
      };
      sinex-nats = {
        unit = "sinex-nats.service";
        resourceClass = "capture";
        notifyOnFailure = true;
        operatorRestart = false;
      };
      sinex-capture-journald = {
        unit = "sinex-capture-journald.service";
        resourceClass = "capture";
        notifyOnFailure = true;
        operatorRestart = false;
      };
      # PostgreSQL serves only Sinex on this host.
      postgresql = {
        unit = "postgresql.service";
        resourceClass = "ordinary";
        resources = {
          Nice = 8;
          IOSchedulingClass = "best-effort";
          IOSchedulingPriority = 7;
          IOWeight = 20;
          MemoryHigh = "8G";
        };
        notifyOnFailure = true;
        operatorRestart = false;
      };
      sinex-dump = {
        unit = "sinex-dump.service";
        resourceClass = "backup";
        notifyOnFailure = true;
      };
    };

    systemd.services = {
      postgresql = {
        unitConfig.RequiresMountsFor = [ root ];
        serviceConfig = runtimeServiceConfig "postgresql.service";
      };
      sinexd = {
        unitConfig.RequiresMountsFor = [ root ];
        serviceConfig = runtimeServiceConfig "sinexd.service";
      };
      sinex-nats = {
        unitConfig.RequiresMountsFor = [ root ];
        serviceConfig = runtimeServiceConfig "sinex-nats.service";
      };
      sinex-capture-journald = {
        unitConfig.RequiresMountsFor = [ root ];
        serviceConfig = runtimeServiceConfig "sinex-capture-journald.service";
      };
      sinex-dump = {
        unitConfig.RequiresMountsFor = [
          root
          dumpRoot
        ];
        serviceConfig = runtimeServiceConfig "sinex-dump.service";
      };
    };
  };
}
