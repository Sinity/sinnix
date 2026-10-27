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
#   postgresql/  the PostgreSQL cluster, No_COW (hosts/sinnix-prime/storage.nix
#                sets the attribute so every file the cluster creates inherits it)
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
  inputs,
  ...
}:
let
  cfg = config.sinnix.services.sinex;
  operator = config.sinnix.user.name;
  secrets = config.sinnix.secrets.paths;
  root = "/var/lib/sinex";
  dumpRoot = "${config.sinnix.paths.realmRoot}/state/db-dumps";
  # SQLite opens a WAL-mode database's -shm index and -wal log writable even
  # for a read-only connection, which never writes the database; readAnyFile
  # reads files but cannot write them. The sinex user gets write access to
  # both for each database a SQLite source reads, and by default ACL to those
  # the program creates next (the default mask must not cut that entry down);
  # the database itself stays read-only to it. It gets no write access to the
  # directory, so sinexd never creates a file there: while the program is
  # closed and its index absent, the source reports the database unavailable.
  sqlitePaths = lib.concatMap (
    source:
    let
      configured = config.services.sinex.sources.${source.name};
    in
    lib.optionals (configured.enable && lib.elem "sqlite-rows" source.drivers) configured.paths
  ) (lib.importJSON "${inputs.sinex}/nix/catalog.json").sources;
  # `-`: an index that does not exist yet (a database not in WAL mode, or a
  # program not running) is not an activation failure.
  sqliteIndexRules = lib.concatMap (path: [
    "a+- ${path} - - - - u:${config.services.sinex.user}:r"
    "a+- ${dirOf path} - - - - d:u:${config.services.sinex.user}:rw,d:m::rwx"
    "a+- ${path}-shm - - - - u:${config.services.sinex.user}:rw"
    "a+- ${path}-wal - - - - u:${config.services.sinex.user}:rw"
  ]) sqlitePaths;
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

    # Sized for the QLC /realm NVMe, where writes are what stall the desktop.
    # At the stock 128MB buffers, 1GB WAL and 5min checkpoints, every
    # checkpoint made the next write to each page log the whole page again:
    # 8.8M full-page images in 73 GB of WAL over 18 hours, with 61 of 252
    # checkpoints forced by WAL size during a catch-up. Sorts spilled 2.4 TB
    # to temp files at 4MB work_mem. Spills of 16MB and more are logged so
    # the next one names its statement.
    services.postgresql.settings = {
      shared_buffers = "4GB";
      effective_cache_size = "12GB";
      work_mem = "64MB";
      maintenance_work_mem = "512MB";
      max_wal_size = "16GB";
      checkpoint_timeout = "30min";
      log_temp_files = "16MB";
    };

    systemd.tmpfiles.rules = sqliteIndexRules;

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
          # Shared buffers (4GB) plus working memory stay resident when the
          # host reclaims; swapping them turns every buffer hit into a
          # swap-in. Needs system.slice's MemoryLow (runtime-defaults.nix).
          MemoryLow = "5G";
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
        serviceConfig = runtimeServiceConfig "postgresql.service" // {
          # With 16GB of WAL between 30-minute checkpoints, the shutdown and
          # end-of-recovery checkpoints write gigabytes at IO priority 7 on
          # the QLC drive. Under the module's 120 s, an activation on
          # 2026-10-27 killed the shutdown checkpoint, then killed the
          # recovery checkpoint at start and left the unit start-limit-hit.
          TimeoutSec = lib.mkForce 1800;
        };
      };
      sinexd = {
        unitConfig.RequiresMountsFor = [ root ];
        serviceConfig = runtimeServiceConfig "sinexd.service" // {
          # A runaway sinexd is killed inside its own unit rather than
          # pushing the workstation into swap.
          MemorySwapMax = "2G";
        };
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
