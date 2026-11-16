# Sinex on this host
#
# Host glue between Sinnix and Sinex's NixOS module (`services.sinex`, from the
# pinned `sinex` flake input): where its state lives, the agenix secrets that
# carry the NATS passwords, the operator's session, and the runtime inventory
# entries of its units. The sources a host reads are host facts and are set in
# the host's canonical roots under `services.sinex.discovery`.
#
# State is on /var/lib/sinex, the /realm/state/sinex subvolume on the NVMe
# (hosts/sinnix-prime/storage.nix), outside the realm snapshots:
#   daemon/      API tokens, NATS JetStream, capture spools, and the content
#                store (daemon/store)
#   postgresql/  the PostgreSQL cluster, No_COW (hosts/sinnix-prime/storage.nix
#                sets the attribute so every file the cluster creates inherits it)
# State of earlier deployments stays beside them under dated names.
#
# Sinex's own sinex-backup.service prepares its backup and archives it into
# two Borg repositories (content, keys). The nightly coordinator starts it and
# reuses its completed pair on boot catch-up. Stopped earlier deployments are
# archived separately, whole, until their import has been compared.
#
# Sinex's module sets restartIfChanged on sinexd and sinex-nats, so an
# activation that changes either unit (a Sinex bump changes sinexd's start
# script; a resource change here changes its unit) restarts it. Check the
# running binary after a deploy.
{
  config,
  helpers,
  inputs,
  lib,
  options,
  pkgs,
  ...
}:
let
  # Each live unit's protected line in the host memory budget
  # (docs/resource-control.md).
  budget = helpers.data.runtimeDefaults.memoryBudget;
  mib = value: "${toString value}M";
  cfg = config.sinnix.services.sinex;
  operator = config.sinnix.user.name;
  secrets = config.sinnix.secrets.paths;
  root = "/var/lib/sinex";
  backupRoot = "${config.sinnix.paths.outerRealm}/backup";
  backupArchiveUnits = [
    "borgbackup-job-sinex"
    "borgbackup-job-sinex-keys"
  ];
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
  # These are the existing local WAL readers' host permissions. Discovery
  # belongs to Sinex and receives roots, rather than per-source path copies.
  sqlitePaths = [
    "${config.users.users.${operator}.home}/.local/share/atuin/history.db"
    "${config.users.users.${operator}.home}/.local/share/activitywatch/aw-server-rust/sqlite.db"
    "${config.sinnix.paths.realmRoot}/project/steering/repo/steering.sqlite"
  ];
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
  # Retry indefinitely with backoff after I/O stalls or startup failures while producers spool frames.
  restartForever = {
    StartLimitIntervalSec = 0;
    RestartSec = "10s";
    RestartSteps = 6;
    RestartMaxDelaySec = "5min";
  };
  # Reserve unswappable 2 MiB huge pages at boot, before fragmentation limits allocation.
  # The reservation includes a 6% margin and 32 extra pages for PostgreSQL shared memory.
  sharedBuffersMiB = 4096;
  hugePages = (sharedBuffersMiB / 2) * 106 / 100 + 32;
in
{
  config = lib.mkIf (options.services ? sinex && cfg.enable) {
    services.sinex = {
      enable = true;
      stateDir = "${root}/daemon";
      # The PostgreSQL build and extensions Sinex's package is tested with.
      database.package = inputs.sinex.packages.${pkgs.stdenv.hostPlatform.system}.postgresql;
      database.dataDir = "${root}/postgresql";
      # Shell histories, browser and ActivityWatch databases and the capture
      # lanes are private to the operator; sinexd reads them, never writes.
      readAnyFile = true;
      nats = {
        daemonPasswordFile = secrets.sinex-nats-daemon;
        producers.polylogue.passwordFile = secrets.sinex-nats-polylogue;
      };
      session = {
        user = operator;
        stateDir = "${config.users.users.${operator}.home}/.local/state/sinex-session-v3";
        passwordFile = secrets.sinex-nats-session;
      };
      backup = {
        # Immutable segment prefixes exceed the live NVMe's staging headroom.
        # Keep staging on a different disk from the paired Borg repositories.
        artifactDir = "${config.sinnix.paths.neoOuterRealm}/state/sinex/backup";
        repo = "${backupRoot}/borg-sinex-core-v1";
        keysRepo = "${backupRoot}/borg-sinex-keys-v1";
        passCommand = "${pkgs.coreutils}/bin/cat ${secrets.borg-passphrase}";
        # The nightly backup coordinator starts it.
        startAt = [ ];
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
      shared_buffers = "${toString sharedBuffersMiB}MB";
      # `try` until the host has booted with the reservation: `on` would
      # refuse to start PostgreSQL while the pages are missing.
      huge_pages = "try";
      effective_cache_size = "12GB";
      work_mem = "64MB";
      maintenance_work_mem = "512MB";
      max_wal_size = "16GB";
      checkpoint_timeout = "30min";
      log_temp_files = "16MB";
    };

    boot.kernelParams = [ "hugepages=${toString hugePages}" ];

    systemd.tmpfiles.rules = sqliteIndexRules;
    sinnix.persistence.home.directories = lib.optional (lib.hasPrefix "${config.users.users.${operator}.home}/" config.services.sinex.session.stateDir) (
      lib.removePrefix "${config.users.users.${operator}.home}/" config.services.sinex.session.stateDir
    );

    sinnix.runtime.units = {
      sinexd = {
        unit = "sinexd.service";
        resourceClass = "live";
        resources = {
          # A ceiling without a throttling band below it. Between memory.high
          # and memory.max the kernel throttles the daemon and reclaims its
          # own page cache first, so a daemon held there rereads its segment
          # and spool files from disk at the live weight for as long as it
          # stays; at the ceiling it is killed and restarted instead.
          # Its resident peak over two weeks was 6.0G with 2G more swapped.
          MemoryMax = "8G";
          # Keep the daemon's working set resident: every producer frame waits for its acknowledgment.
          MemoryLow = mib budget.sinexd;
        };
        notifyOnFailure = true;
        operatorRestart = false;
      };
      sinex-nats = {
        unit = "sinex-nats.service";
        resourceClass = "live";
        # Peaks of 0.5-0.7G over two weeks.
        resources = {
          MemoryLow = mib budget.nats;
          MemoryHigh = "1G";
          MemoryMax = "1536M";
        };
        notifyOnFailure = true;
        operatorRestart = false;
      };
      sinex-capture-journald = {
        unit = "sinex-capture-journald.service";
        resourceClass = "live";
        # Its peaks (1-2G) are page cache of the journal files it reads.
        resources = {
          MemoryLow = mib budget.journaldCapture;
          MemoryHigh = "1G";
          MemoryMax = "2G";
        };
        notifyOnFailure = true;
        operatorRestart = false;
      };
      # PostgreSQL serves only Sinex on this host.
      postgresql = {
        unit = "postgresql.service";
        resourceClass = "live";
        resources = {
          # The huge pages of shared buffers (4.3G) are charged here; the rest
          # of the band is backends and page cache of the cluster.
          MemoryHigh = "8G";
          MemoryMax = "9G";
          # The huge pages plus 1.2G of backends and cache stay resident when
          # the host reclaims. Needs live.slice's MemoryLow (runtime-defaults.nix).
          MemoryLow = mib budget.postgresql;
        };
        notifyOnFailure = true;
        operatorRestart = false;
      };
      # The session producer waits on sinexd's acknowledgment of each frame.
      sinex-session = {
        unit = "sinex-session.service";
        manager = "user";
        resourceClass = "live";
        # Keep the session producer's working set resident because it waits on acknowledgments.
        resources.MemoryLow = mib budget.sessionProducer;
        notifyOnFailure = true;
        operatorRestart = false;
      };
      sinex-backup = {
        unit = "sinex-backup.service";
        resourceClass = "backup";
        notifyOnFailure = true;
        operatorRestart = false;
      };
    }
    // lib.genAttrs backupArchiveUnits (name: {
      unit = "${name}.service";
      resourceClass = "backup";
      notifyOnFailure = true;
      operatorRestart = false;
    });

    # The producer retries unacknowledged frames without a start limit; its spool preserves them across restarts.
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
          # Shutdown and recovery checkpoints can write gigabytes of WAL; the timeout must cover both.
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
      sinex-backup = {
        unitConfig.RequiresMountsFor = [
          root
          backupRoot
          config.services.sinex.backup.artifactDir
        ];
        serviceConfig = runtimeServiceConfig "sinex-backup.service";
      };
    }
    // lib.genAttrs backupArchiveUnits (name: {
      serviceConfig = runtimeServiceConfig "${name}.service";
    });
  };
}
