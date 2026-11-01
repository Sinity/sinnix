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
  # the program creates next. SQLite creates the index and log with the
  # database's own permission bits, and on a file with an ACL the group bits
  # are the mask, so a database whose group bits lack write (Atuin's is 0654)
  # gives every index it recreates a mask that cuts the sinex entry to
  # read-only, and reads then fail with "attempt to write a readonly
  # database". Each rule therefore sets the mask: on the database so the files
  # created from it keep the entry writable, and on the index and log so
  # activation repairs ones created before. The mask grants nothing by itself;
  # the database stays read-only to sinex and to the group. Sinex gets no
  # write access to the directory, so sinexd never creates a file there:
  # while the program is closed and its index absent, the source reports the
  # database unavailable.
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
    "a+- ${path} - - - - u:${config.services.sinex.user}:r,m::rw"
    "a+- ${dirOf path} - - - - d:u:${config.services.sinex.user}:rw,d:m::rwx"
    "a+- ${path}-shm - - - - u:${config.services.sinex.user}:rw,m::rw"
    "a+- ${path}-wal - - - - u:${config.services.sinex.user}:rw,m::rw"
  ]) sqlitePaths;
  runtimeServiceConfig =
    unit:
    lib.sinnix.mkRuntimeServiceConfig {
      runtimeInventory = config.sinnix.runtime.inventory;
      inherit unit;
    };
  # The default start limit (three failures in ten minutes) left the session
  # producer dead for days; sinexd and NATS would stop the same way after an
  # I/O stall or a schema refusal at start while producers keep spooling.
  # They retry forever, backing off from 10 s to 5 min between attempts.
  restartForever = {
    StartLimitIntervalSec = 0;
    RestartSec = "10s";
    RestartSteps = 6;
    RestartMaxDelaySec = "5min";
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
        resourceClass = "live";
        resources = {
          MemoryHigh = "6G";
          MemoryMax = "8G";
          # Its working set stays resident under host reclaim: on 2026-11-01
          # 726 MB of it sat in swap, on the acknowledgment path of every
          # producer frame. Fits beside PostgreSQL's 5G in live.slice's 6G.
          MemoryLow = "1G";
        };
        notifyOnFailure = true;
        operatorRestart = false;
      };
      sinex-nats = {
        unit = "sinex-nats.service";
        resourceClass = "live";
        resources = {
          MemoryHigh = "6G";
          MemoryMax = "8G";
        };
        notifyOnFailure = true;
        operatorRestart = false;
      };
      sinex-capture-journald = {
        unit = "sinex-capture-journald.service";
        resourceClass = "live";
        resources = {
          MemoryHigh = "6G";
          MemoryMax = "8G";
        };
        notifyOnFailure = true;
        operatorRestart = false;
      };
      # PostgreSQL serves only Sinex on this host.
      postgresql = {
        unit = "postgresql.service";
        resourceClass = "live";
        resources = {
          MemoryHigh = "8G";
          # Shared buffers (4GB) plus working memory stay resident when the
          # host reclaims; swapping them turns every buffer hit into a
          # swap-in. Needs live.slice's MemoryLow (runtime-defaults.nix).
          MemoryLow = "5G";
        };
        notifyOnFailure = true;
        operatorRestart = false;
      };
      # The session producer waits on sinexd's acknowledgment of each frame.
      sinex-session = {
        unit = "sinex-session.service";
        manager = "user";
        resourceClass = "live";
        # 186 MB of its 235 MB working set was swapped on 2026-11-01.
        resources.MemoryLow = "256M";
        notifyOnFailure = true;
        operatorRestart = false;
      };
      sinex-dump = {
        unit = "sinex-dump.service";
        resourceClass = "backup";
        notifyOnFailure = true;
        # The nightly dump is replaced atomically; a day plus 2h grace.
        captures = [
          {
            name = "sinex-dump";
            path = "${dumpRoot}/sinex/sinex.dump";
            eventDriven = true;
            staleAfterSeconds = 26 * 60 * 60;
          }
        ];
      };
    };

    # The session producer exits when a frame goes unacknowledged; under build
    # I/O load on the /realm NVMe that happens, and three failures in ten
    # minutes left it dead for days (2026-10-29, 2026-11-01). It keeps
    # retrying; its spool holds unacknowledged frames across restarts.
    systemd.user.services.sinex-session = {
      unitConfig.StartLimitIntervalSec = lib.mkForce 0;
      serviceConfig =
        lib.sinnix.mkRuntimeServiceConfig {
          runtimeInventory = config.sinnix.runtime.inventory;
          unit = "sinex-session.service";
          manager = "user";
        }
        // {
          RestartSec = lib.mkForce "10s";
        };
    };

    systemd.services = {
      postgresql = {
        unitConfig.RequiresMountsFor = [ root ];
        serviceConfig = runtimeServiceConfig "postgresql.service" // {
          # With 16GB of WAL between 30-minute checkpoints, the shutdown and
          # end-of-recovery checkpoints write gigabytes on the QLC drive. Under the module's 120 s, an activation on
          # 2026-10-27 killed the shutdown checkpoint, then killed the
          # recovery checkpoint at start and left the unit start-limit-hit.
          TimeoutSec = lib.mkForce 1800;
        };
      };
      sinexd = {
        unitConfig = {
          RequiresMountsFor = [ root ];
          StartLimitIntervalSec = lib.mkForce restartForever.StartLimitIntervalSec;
        };
        serviceConfig = runtimeServiceConfig "sinexd.service" // {
          RestartSec = lib.mkForce restartForever.RestartSec;
          inherit (restartForever) RestartSteps RestartMaxDelaySec;
          # A runaway sinexd is killed inside its own unit rather than
          # pushing the workstation into swap.
          MemorySwapMax = "2G";
        };
      };
      sinex-nats = {
        unitConfig = {
          RequiresMountsFor = [ root ];
          StartLimitIntervalSec = lib.mkForce restartForever.StartLimitIntervalSec;
        };
        serviceConfig = runtimeServiceConfig "sinex-nats.service" // {
          RestartSec = lib.mkForce restartForever.RestartSec;
          inherit (restartForever) RestartSteps RestartMaxDelaySec;
        };
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
