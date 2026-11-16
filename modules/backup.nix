# Comprehensive Unified Backup Strategy
#
# 1. btrbk: Local snapshots for fast rollbacks (copy-on-write, shared data extents)
#    Creation writes metadata; rewritten/deleted extents remain referenced until
#    the snapshots holding them are released.
# 2. Borg: Off-disk incremental backups (file-level, with exclusions, deduplicated)
#
# Drive           Label            Mount            Purpose
# ────────────────────────────────────────────────────────────────────────────
# /dev/nvme0n1p3  SSD_4TB          /realm           Source: projects, data
# /dev/sda2       root_btrfs       /persist         Source: system & home state
# /dev/sdb1       outer-realm      /outer-realm     Target: Borg repositories
# Note: / is ephemeral — not snapshotted by btrbk (initrd saves pre-wipe states)
{
  pkgs,
  lib,
  config,
  options,
  helpers,
  ...
}:
let
  inherit (config.sinnix.paths) realmRoot;
  # Stopped earlier Sinex deployments are archived whole, read in place,
  # until their import into the running Sinex has been compared. The running
  # Sinex is backed up by sinex-backup.service from a copy it prepares.
  sinexStorePaths = lib.optionals (
    options.services ? sinex && config.services.sinex.enable
  ) config.sinnix.services.sinex.retainedStores;
  sinexBackupRepositories = lib.optionals (options.services ? sinex && config.services.sinex.enable) [
    config.services.sinex.backup.repo
    config.services.sinex.backup.keysRepo
  ];
  borgRepoRoot = "${config.sinnix.paths.outerRealm}/backup";
  scriptPkgs = helpers.mkSinnixPackagesFor pkgs;
  username = config.sinnix.user.name;
  backupCfg = config.sinnix.backup;
  genomeSnapshots = "${config.sinnix.paths.neoOuterRealm}/.btrfs/genome-snapshots";

  # state/polylogue is a nested btrfs subvolume (sinnix-3pvd): btrbk snapshots
  # `subvolume .` of /realm, which does not cross subvolume boundaries, so
  # this tree archives as an empty directory under the normal realm coverage.
  # Pulling it into btrbk directly was tried and reverted (commits 9c2c068d,
  # a99f2f7b) because a snapshot forces copy-on-write on the daemon's
  # nodatacow SQLite files on their next write. The fix is the same shape
  # machine-telemetry-sqlite-backup already uses: a
  # logical dump/direct-path copy on a timer, landing in a plain directory
  # that IS covered by ordinary realm snapshot+borg. No daemon writes this
  # Python archive any more, so these jobs run against a quiescent tree.
  polylogueStateRoot = config.sinnix.services.polylogue.dataDir;
  polylogueBackupRoot = "${realmRoot}/state/db-dumps/polylogue";
  # The purchased embedding vectors (the 2026-07-10 stores). They no longer
  # change and cost money to recompute; the nightly Polylogue state archive
  # carries the copy on the disk that is not the Borg destination.
  paidVectorRoot = "${config.sinnix.paths.neoOuterRealm}/archive/polylogue/embeddings";
  # The daemon's live SQLite databases at the top level of the state root.
  # index.db is deliberately NOT in this list: the symlink points into
  # .index-generations/ at a 40.5 GB derived rebuild-generation product --
  # the first live run spent its whole 30-minute budget copying and
  # compressing it (measured 2026-08-18) while the five real mutable dbs
  # (~2.7 GB together) had finished in minutes. The index still MUST be
  # backed up (with the migration broken, sinnix-qh6s, it is not currently
  # regenerable), but its coverage is the direct-path borg job below, whose
  # dedup makes a 40 GB near-static file cheap -- not a daily full
  # copy+zstd through the dump path.
  polylogueDbNames = [
    "source.db"
    "embeddings.db"
    "ops.db"
    "audit.db"
    "user.db"
  ];
  # Direct-path borg (below) must not file-copy these live databases or
  # their WAL/SHM sidecars mid-write -- that is exactly the torn-copy risk
  # the sqlite-backup dump job exists to avoid. Retired/historical sibling
  # files (e.g. embeddings.db.retired-20260627) don't match these exact
  # names and stay in the direct-path job's coverage, which is correct: they
  # are static and a plain file copy of a static file is safe.
  polylogueDbExcludes = lib.concatMap (name: [
    name
    "${name}-wal"
    "${name}-shm"
  ]) polylogueDbNames;

  # The live archive and every archive set aside after a cutover, relative to
  # the realm root: their derived index.db (rebuilt from archive.db) is left
  # out of the realm drain.
  polylogueCfg = config.sinnix.services.polylogue;
  polylogueArchiveRoot = config.sinnix.runtime.inventory.polylogue.archiveRoot;
  polylogueIndexExcludes = lib.concatMap (
    archive:
    map (name: lib.removePrefix "${realmRoot}/" "${archive}/${name}") [
      "index.db"
      "index.db-wal"
      "index.db-shm"
    ]
  ) ([ polylogueArchiveRoot ] ++ polylogueCfg.retainedArchives);

  # Snapshot directories
  realmSnapshots = "${realmRoot}/.btrfs/snapshot";
  persistSnapshots = "/persist/.btrfs/snapshot";
  borgSnapshotBindRoot = "/run/borgbackup-snapshot-inputs";
  borgPersistSnapshotBind = "${borgSnapshotBindRoot}/persist";
  borgRealmSnapshotBind = "${borgSnapshotBindRoot}/realm";
  borgDrainStateRoot = "/persist/root/.cache/borg-drain";
  borgIntegrityReceipt = "${borgDrainStateRoot}/integrity-check.json";
  realmCoverageAuditReceipt = "${borgDrainStateRoot}/realm.independent-coverage-audit.json";

  # Borg Configuration
  borgRepoPersistPath = "${borgRepoRoot}/borg-persist-v1";
  borgRepoRealmPath = "${borgRepoRoot}/borg-realm-v2";
  borgRepoRootSnapshotsPath = "${borgRepoRoot}/borg-root-snapshots-v1";
  borgRepoSinexBlobsPath = "${borgRepoRoot}/borg-sinex-blobs-v1";
  borgRepoPolylogueStatePath = "${borgRepoRoot}/borg-polylogue-state-v1";
  borgRepoLiveSmallPath = "${borgRepoRoot}/borg-live-small-v1";
  borgRepoPersist = "file://${borgRepoPersistPath}";
  borgRepoRealm = "file://${borgRepoRealmPath}";
  borgRepoRootSnapshots = "file://${borgRepoRootSnapshotsPath}";
  borgRepoSinexBlobs = "file://${borgRepoSinexBlobsPath}";
  borgRepoPolylogueState = "file://${borgRepoPolylogueStatePath}";
  borgRepoLiveSmall = "file://${borgRepoLiveSmallPath}";
  borgPassphrasePath = config.sinnix.secrets.paths."borg-passphrase";
  outerRealmMountUnit = "outer\\x2drealm.mount";
  borgLockWaitSec = 60;
  # A Borg cache commit rewrites the whole chunk index and files cache. Both
  # caches are regenerable and kept off the worn root SSD, where that added
  # tens of GB per nightly run. The nightly cache is on /realm, which is
  # quiet at night. The hourly jobs write about 1 GB per run, so their cache
  # sits on the repository disk, which is idle between backups, instead of
  # the /realm QLC drive that interactive work and builds use all day.
  borgCacheDir = "${realmRoot}/state/cache/borg";
  borgHourlyCacheDir = "${borgRepoRoot}/borg-hourly-cache";
  # Producer spools: frames not yet acknowledged by sinexd. The session
  # producer spools under the operator's home on /persist.
  sinexSpoolPaths =
    lib.optional (
      options.services ? sinex && config.services.sinex.enable
    ) "${config.services.sinex.stateDir}/spool"
    ++ lib.optional (
      options.services ? sinex && config.services.sinex.enable
    ) "${config.services.sinex.session.stateDir}/spool";
  borgGlobalLock = "/run/lock/sinnix-borg.lock";
  # Every Beads task store a project declares as its task authority. The
  # restore check requires each one in the archive; other trackers found
  # under state/tasks are checked as well.
  taskAuthorities = lib.filter (authority: authority != null) (
    map (project: project.taskAuthority or null) (lib.attrValues config.sinnix.projects.entries)
  );
  beadsArchivePaths = map (
    authority:
    assert lib.assertMsg (
      lib.hasPrefix "${realmRoot}/" authority.workspace
      && lib.hasPrefix "${authority.workspace}/" authority.database
    ) "Beads task authorities must keep their workspace and database inside /realm";
    {
      path = lib.removePrefix "${realmRoot}/" authority.workspace;
      database = lib.removePrefix "${authority.workspace}/" authority.database;
      projectUuid = authority.projectUuid or null;
    }
  ) taskAuthorities;
  # Archives, independent checks and manual Borg commands share this lock.
  # Unit ordering cannot serialize commands started outside systemd.
  beadsCheckLockWaitSec = 3 * 60 * 60;
  # The file keeps its historical name: Lynchpin reads it by path.
  beadsCheckLog = "${config.sinnix.paths.machineRoot}/borg_beads_drill.jsonl";
  # Ranking domains (items and the append-only comparison log): operator
  # judgments that cannot be recomputed from anything.
  rankingArchivePath = "activity/shared/ranking";
  # Paths under /realm no exclude pattern may cover, ancestors included.
  protectedRealmArchivePaths =
    lib.concatMap (store: [
      store.path
      "${store.path}/metadata.json"
      "${store.path}/config.yaml"
      "${store.path}/${store.database}"
    ]) beadsArchivePaths
    ++ [
      rankingArchivePath
      "library/model/control-vector"
    ];
  # Nightly archival permits a day between accepted source cuts, plus 6h
  # grace; any backup older than 30h is reported stale (DUR-2).
  borgDataFreshnessMaxAgeSec = 30 * 60 * 60;
  # Hourly jobs skip while the nightly coordinator holds the Borg lock (up to
  # ~2.5h observed), so six hours without an hourly archive is an outage.
  borgHourlyMaxAgeSec = 6 * 60 * 60;
  borgAcquisitionObservationMaxAgeSec = 3 * 6 * 60 * 60;
  genomeAcquisitionInventory = "${borgDrainStateRoot}/genome.acquisition-inventory.json";
  # Direct-path archives run nightly in the coordinator: a day plus 6h grace.
  borgDailyArchiveMaxAgeSec = 30 * 60 * 60;
  # Every unit in this module is the same shape: a oneshot a timer wakes,
  # never restarted by activation (a switch mid-drain would abandon a bind
  # mount and a held Borg lock), inside the backup envelope. Only
  # the first two are stated here -- the envelope comes from the unit's own
  # registered surface, which mkScheduledJob resolves by unit lookup. A
  # module-local serviceConfig helper used to recompute exactly that lookup
  # per unit; the class was never declared twice, only applied twice.
  # A daily marker counts only while its fingerprint matches the current inputs
  # and policy, so a change to either makes the job due again.
  coordinatorPolicies = {
    polylogue = builtins.hashString "sha256" (
      builtins.toJSON {
        root = polylogueStateRoot;
        excludes = polylogueDbExcludes;
        hooks = builtins.readFile ../pkgs/sinnix-backup/sinnix_backup/hook_cut.py;
      }
    );
    sinex = builtins.hashString "sha256" (builtins.toJSON sinexStorePaths);
    localDumps = builtins.hashString "sha256" (
      builtins.toJSON {
        root = "${realmRoot}/state/db-dumps";
        policy = realmCoveragePolicy;
      }
    );
  };

  sinexCoreRepository = lib.findFirst (repo: repo != null) null (lib.take 1 sinexBackupRepositories);
  sinexKeysRepository = lib.findFirst (repo: repo != null) null (lib.drop 1 sinexBackupRepositories);
  sinexRepositoryNames =
    lib.optional (sinexCoreRepository != null) "sinex-core"
    ++ lib.optional (sinexKeysRepository != null) "sinex-keys";

  persistCoverage = mkCoverage {
    label = "persist";
    bindTarget = borgPersistSnapshotBind;
    exclude = persistExcludes;
    noncanonical = persistNoncanonical;
  };
  realmCoverage = mkCoverage {
    label = "realm";
    bindTarget = borgRealmSnapshotBind;
    exclude = realmExcludes;
    noncanonical = realmNoncanonical;
  };
  genomeCoverage = mkCoverage {
    label = "genome";
    bindTarget = "${borgSnapshotBindRoot}/genome";
    exclude = genomeExcludes;
    noncanonical = genomeExcludes;
    producerProof = true;
  };
  # Root snapshot paths left out of the archive; the same list is the
  # coverage policy, so an excluded root is never reported missing.
  rootSnapshotExcludes = [
    "dev"
    "home/${username}/.cache"
    "mnt"
    "neo-outer-realm"
    "nix"
    "outer-realm"
    "persist"
    "proc"
    "realm"
    "root/.cache"
    "run"
    "swap"
    "sys"
    "tmp"
    "var/cache"
  ];

  # A disabled producer module contributes no unit to the nightly sequence.
  configuredUnits = lib.filter (
    name: builtins.hasAttr name config.systemd.services && config.systemd.services.${name}.enable
  );
  dumpUnits = configuredUnits (
    lib.optional config.sinnix.services.machine-telemetry.enable "machine-telemetry-sqlite-backup"
    ++ lib.optional config.sinnix.services.polylogue.enable "polylogue-sqlite-backup"
  );
  # Daily direct-path archives run before the snapshot drains, so a long
  # snapshot backlog cannot push them past their start window.
  archiveUnits = configuredUnits (
    lib.optional config.sinnix.services.polylogue.enable "borgbackup-job-polylogue-state"
    ++ [
      "borgbackup-job-sinex-blobs"
      "borgbackup-job-realm"
      "borgbackup-job-genome"
      "borgbackup-job-persist"
      "borgbackup-root-snapshots"
    ]
  );
  finalUnits = configuredUnits [
    "borgbackup-maintenance"
    "borgbackup-coverage-audit-realm"
    "borgbackup-local-dumps"
  ];
  acquisitionPolicy = builtins.hashString "sha256" (
    builtins.toJSON {
      dumps = map (
        name:
        let
          service = config.systemd.services.${name};
        in
        if service.script != "" then service.script else service.serviceConfig.ExecStart
      ) dumpUnits;
      snapshots = config.environment.etc."btrbk/btrbk.conf".text;
    }
  );

  # The policy every `sinnix-backup` command reads from /etc/sinnix/backup.json.
  # Each `coverage` object is hashed into stored archive records: changing an
  # entry, its order or a key makes the next archive of that source a new
  # policy (see docs/backups.md, "Exclusions and why").
  backupConfig = {
    state_directory = borgDrainStateRoot;
    lock_path = borgGlobalLock;
    cache_directory = borgCacheDir;
    hourly_cache_directory = borgHourlyCacheDir;
    passphrase_path = borgPassphrasePath;
    scratch_directory = "${realmRoot}/tmp/work";
    lock_wait_seconds = borgLockWaitSec;
    repositories =
      lib.mapAttrs
        (_: url: {
          inherit url;
          path = lib.removePrefix "file://" url;
        })
        (
          {
            persist = borgRepoPersist;
            realm = borgRepoRealm;
            root-snapshots = borgRepoRootSnapshots;
            sinex-blobs = borgRepoSinexBlobs;
            polylogue-state = borgRepoPolylogueState;
            live-small = borgRepoLiveSmall;
          }
          // lib.optionalAttrs (sinexCoreRepository != null) { sinex-core = sinexCoreRepository; }
          // lib.optionalAttrs (sinexKeysRepository != null) { sinex-keys = sinexKeysRepository; }
        );
    sources = {
      persist = {
        repository = "persist";
        snapshot_directory = persistSnapshots;
        name_glob = "persist.*";
        bind_path = borgPersistSnapshotBind;
        archive_prefix = "persist";
        replacement_suffix = "-coverage-v2";
        coverage = persistCoverage;
        create_check = false;
        files_cache_suffix = null;
      };
      realm = {
        repository = "realm";
        snapshot_directory = realmSnapshots;
        name_glob = "realm.*";
        bind_path = borgRealmSnapshotBind;
        archive_prefix = "realm";
        replacement_suffix = "-coverage-v3";
        coverage = realmCoverage;
        create_check = true;
        files_cache_suffix = null;
      };
      # Initrd snapshots of the ephemeral root, relative to the top-level
      # subvolume of jobs.root_snapshots.device mounted for the job.
      root = {
        repository = "root-snapshots";
        snapshot_directory = ".snapshots";
        name_glob = "root.*";
        bind_path = null;
        archive_prefix = "root";
        replacement_suffix = "";
        coverage = rootSnapshotExcludes;
        create_check = false;
        files_cache_suffix = null;
      };
    }
    // lib.optionalAttrs (backupCfg.genomeRoot != null) {
      genome = {
        repository = "realm";
        snapshot_directory = genomeSnapshots;
        name_glob = "genome.*";
        bind_path = "${borgSnapshotBindRoot}/genome";
        archive_prefix = "genome";
        replacement_suffix = "";
        coverage = genomeCoverage;
        create_check = true;
        # Realm backlogs must not age genome entries out of Borg's files
        # cache; the repository and chunk cache stay shared.
        files_cache_suffix = "genome";
      };
    };
    nightly = {
      dump_units = map (name: "${name}.service") dumpUnits;
      archive_units = map (name: "${name}.service") archiveUnits;
      final_units = map (name: "${name}.service") finalUnits;
      drain_sources = [
        "realm"
        "persist"
      ]
      ++ lib.optional (backupCfg.genomeRoot != null) "genome";
      verify_unit = "borgbackup-verify.service";
      acquisition_policy = acquisitionPolicy;
      daily_markers = {
        "borgbackup-job-polylogue-state.service" = [
          "${borgDrainStateRoot}/polylogue-state.last-success"
          coordinatorPolicies.polylogue
        ];
        "borgbackup-job-sinex-blobs.service" = [
          "${borgDrainStateRoot}/sinex-blobs.last-success"
          coordinatorPolicies.sinex
        ];
        "borgbackup-local-dumps.service" = [
          "${borgDrainStateRoot}/local-dumps.last-success"
          coordinatorPolicies.localDumps
        ];
      };
    };
    jobs = {
      freshness_seconds = borgDataFreshnessMaxAgeSec;
      sinex_store_paths = sinexStorePaths;
      polylogue = {
        user = username;
        state_root = polylogueStateRoot;
        dump_root = polylogueBackupRoot;
        database_names = polylogueDbNames;
        state_excludes = polylogueDbExcludes ++ [ ".salvage-internals-20261008" ];
        hook_cut_directory = "${realmRoot}/state/cache/polylogue-backup-hooks";
        paid_vector_root = paidVectorRoot;
      };
      hourly = {
        user = username;
        persist_source = "/persist";
        persist_cut = "/persist/.btrfs/borg-hourly-cut";
        polylogue_archive_database = "${polylogueArchiveRoot}/archive.db";
        tasks_root = "${realmRoot}/state/tasks";
        tasks_excludes = [
          "migration-backups"
          "**/dolt-server.log"
        ];
        sinex_spools = sinexSpoolPaths;
      };
      local_dumps_root = "${realmRoot}/state/db-dumps";
      root_snapshots.device = "/dev/disk/by-uuid/f4782d9f-aabe-408e-b18b-2f2baa9e9a02";
      genome = lib.optionalAttrs (backupCfg.genomeRoot != null) {
        source = toString backupCfg.genomeRoot;
        acquisition_inventory = genomeAcquisitionInventory;
        max_observation_age_seconds = borgAcquisitionObservationMaxAgeSec;
        producer_unit = "btrbk.service";
      };
      audit = {
        record = realmCoverageAuditReceipt;
        attempt = "${borgDrainStateRoot}/realm.independent-coverage-audit-attempt.json";
        max_age_seconds = 604800;
        status_max_age_seconds = 691200;
        sample_bytes = 1073741824;
        sample_files = 128;
        scratch_directory = "${borgCacheDir}/coverage-scratch";
      };
      beads = {
        stores = map (store: {
          inherit (store) path database;
          project_uuid = store.projectUuid;
        }) beadsArchivePaths;
        log = beadsCheckLog;
        lock_wait_seconds = beadsCheckLockWaitSec;
        restore_parent = "${realmRoot}/tmp";
      };
      maintenance = {
        marker = "${borgDrainStateRoot}/maintenance.last-success";
        compact_marker = "${borgDrainStateRoot}/compact.last-success";
        retention_directory = "${borgDrainStateRoot}/retention";
        # Each repository's active series keep recent, daily, weekly and
        # monthly points; retired series keep six monthly ones and expire.
        repositories = [
          {
            repository = "persist";
            active = [
              "persist-*"
              "hourly-persist-*"
            ];
            retired = [ "sinnix-prime-persist-*" ];
          }
          {
            repository = "realm";
            active = [
              "realm-*"
              "genome-genome.*"
            ];
            retired = [
              "sinnix-prime-realm-*"
              "machine-telemetry-dumps-*"
            ];
          }
          {
            repository = "sinex-blobs";
            active = [ "sinex-blobs-*" ];
            retired = [ ];
          }
        ]
        ++ map (repository: {
          inherit repository;
          active = [ "sinex-core-*" ];
          retired = [ ];
        }) sinexRepositoryNames
        ++ [
          {
            repository = "root-snapshots";
            active = [ "root-*" ];
            retired = [ ];
          }
          {
            repository = "polylogue-state";
            active = [ "polylogue-state-*" ];
            retired = [ ];
          }
          {
            repository = "live-small";
            active = [
              "live-small-*"
              "polylogue-archive-*"
            ];
            retired = [ ];
          }
        ];
      };
      integrity = {
        record = borgIntegrityReceipt;
        # --max-duration makes each pass incremental: successive weekly runs
        # cycle through a repository without holding its lock for a day.
        repositories = [
          {
            repository = "persist";
            seconds = 1800;
          }
          {
            repository = "realm";
            seconds = 7200;
          }
          {
            repository = "sinex-blobs";
            seconds = 1800;
          }
        ]
        ++ map (repository: {
          inherit repository;
          seconds = 900;
        }) sinexRepositoryNames;
        expected_jobs = [
          "persist"
          "realm"
          "sinex-blobs"
        ]
        ++ lib.optionals (sinexRepositoryNames != [ ]) [
          "sinex"
          "sinex-keys"
        ];
      };
    };
  };

  mkBackupJob =
    name:
    { description, ... }@job:
    lib.sinnix.mkScheduledJob
      {
        inherit config description;
        unitName = name;
        surface = config.sinnix.runtime.units.${name};
      }
      (
        lib.removeAttrs job [ "description" ]
        // {
          unit = {
            restartIfChanged = false;
          }
          // (job.unit or { });
        }
      );

  # Exclusion patterns are written relative to the archive root, but borg
  # matches them against the FULL SOURCE PATH it walks -- the bind mount, e.g.
  # run/borgbackup-snapshot-inputs/realm/state/cache/... (borg strips the leading
  # separator). A bare `cache` must match from the start of that path and never
  # can, so every plain-path exclusion in realmExcludes was inert. Only the
  # `**/...` entries worked, because `**` absorbs the bind prefix -- and since
  # every visibly-working example had that shape, the broken ones read as
  # normal.
  #
  # Measured 2026-08-16 in archive realm-realm.20260816T223000+0200:
  # `cache` 73,805 entries present, `library/media/Steam/steamapps` 92,639 present,
  # while `**/node_modules`, `**/target` and `**/.venv` were each 0. Roughly
  # 870G of explicitly-excluded regenerable data (cache 280G, library/models 120G,
  # library/media/Steam 103G, private project caches, and container layers
  # 23G) had been replicating into a 1.9T repository.
  #
  # Reproduced and fixed in a throwaway repo before landing: `--exclude cache`
  # left cache/sub/f in the archive, while the same pattern qualified with the
  # source path removed it.
  #
  # Qualified patterns stay in the default fnmatch style rather than becoming
  # `pp:` path prefixes, and that is load-bearing rather than incidental: `pp:`
  # is a LITERAL prefix with no globbing, and the persist list contains
  # wildcard entries for Chrome extension cache producers. Measured both ways
  # with GPUCache: `pp:` left the directory in the archive, fnmatch excluded it, and
  # both handled a literal directory correctly. fnmatch also matches "from the
  # start of the full path to just before a path separator", so a qualified
  # directory covers everything beneath it.
  #
  # `**/...` patterns pass through unchanged: they are deliberately
  # match-anywhere and qualifying them would defeat that.
  borgExcludePatterns =
    root: exclude:
    let
      rootRelative = lib.removePrefix "/" root;
      qualify = pattern: if lib.hasPrefix "**" pattern then pattern else "${rootRelative}/${pattern}";
    in
    map qualify exclude;

  mkBorgExcludeArgs =
    root: exclude:
    lib.concatMapStringsSep " " (pattern: "--exclude ${lib.escapeShellArg pattern}") (
      borgExcludePatterns root exclude
    );

  borgHostIdentity = ''
    # Borg's uuid.getnode() fallback can change between invocations. A stable
    # local identity lets Borg's own reaper recognize its abandoned locks.
    if [ -z "''${BORG_HOST_ID:-}" ]; then
      borg_machine_id="$(cat /etc/machine-id)"
      if [[ ! "$borg_machine_id" =~ ^[0-9a-f]{32}$ ]]; then
        echo "Invalid machine identity; refusing to start Borg" >&2
        exit 1
      fi
      export BORG_HOST_ID="$(uname -n)@$borg_machine_id"
    fi
  '';

  mkBorgCommonScript = repo: ''
    export BORG_REPO=${lib.escapeShellArg repo}
    export BORG_PASSCOMMAND=${lib.escapeShellArg "${pkgs.coreutils}/bin/cat ${borgPassphrasePath}"}
    export BORG_CACHE_DIR=${lib.escapeShellArg borgCacheDir}
    ${borgHostIdentity}

    with_borg_lock() {
      if [ "''${SINNIX_BORG_GLOBAL_LOCK_HELD:-0}" = 1 ]; then
        "$@"
      else
        flock ${lib.escapeShellArg borgGlobalLock} "$@"
      fi
    }

    acquire_borg_global_lock() {
      if [ "''${SINNIX_BORG_GLOBAL_LOCK_HELD:-0}" = 1 ]; then
        return
      fi
      exec 9>${lib.escapeShellArg borgGlobalLock}
      flock 9
      export SINNIX_BORG_GLOBAL_LOCK_HELD=1
    }

    release_borg_global_lock() {
      if [ "''${SINNIX_BORG_GLOBAL_LOCK_HELD:-0}" = 1 ]; then
        flock -u 9
        exec 9>&-
        unset SINNIX_BORG_GLOBAL_LOCK_HELD
      fi
    }

    acquire_borg_global_lock_or_skip() {
      if [ "''${SINNIX_BORG_GLOBAL_LOCK_HELD:-0}" = 1 ]; then
        return
      fi
      reason="$1"
      exec 9>${lib.escapeShellArg borgGlobalLock}
      if ! flock -n 9; then
        echo "Another Borg operation is active; skipping $reason and keeping work queued"
        exit 0
      fi
      export SINNIX_BORG_GLOBAL_LOCK_HELD=1
    }

    acquire_borg_global_lock_or_fail() {
      if [ "''${SINNIX_BORG_GLOBAL_LOCK_HELD:-0}" = 1 ]; then
        return
      fi
      reason="$1"
      exec 9>${lib.escapeShellArg borgGlobalLock}
      if ! flock -n 9; then
        echo "Another Borg operation is active; $reason remains due" >&2
        return 1
      fi
      export SINNIX_BORG_GLOBAL_LOCK_HELD=1
    }

    publish_backup_marker() {
      local marker marker_dir marker_base temporary
      marker="$1"
      marker_dir="$(dirname "$marker")"
      marker_base="$(basename "$marker")"
      temporary="$(mktemp "$marker_dir/.''${marker_base}.tmp.XXXXXX")"
      trap 'rm -f "$temporary"' RETURN
      cat > "$temporary" || return 1
      chmod 0644 "$temporary" || return 1
      # Persist only this file and its rename, not unrelated filesystem writes.
      sync -- "$temporary" || return 1
      mv -f "$temporary" "$marker" || return 1
      sync -- "$marker_dir" || return 1
      trap - RETURN
    }
  '';

  # Full verification indexes millions of paths on disk. System services do
  # not inherit the workstation session's TMPDIR; default to Realm scratch.
  # The independent full audit overrides it with Borg's cache on persist so
  # its inventory cannot consume the audited filesystem's remaining space.
  snapshotCoverage = "${pkgs.coreutils}/bin/env TMPDIR=\"\${TMPDIR:-${realmRoot}/tmp/work}\" ${pkgs.python3}/bin/python3 ${../pkgs/sinnix-backup/sinnix_backup/coverage.py}";

  mkCoverage =
    {
      label,
      bindTarget,
      exclude,
      noncanonical,
      producerProof ? label == "realm",
    }:
    {
      inherit noncanonical;
      chrome_extension_caches = label == "persist";
      borg_excludes = borgExcludePatterns bindTarget exclude;
    }
    // lib.optionalAttrs producerProof {
      producer_contract = "realm-borg-create-v2";
    };
  mkCoveragePolicy =
    args: pkgs.writeText "${args.label}-snapshot-coverage.json" (builtins.toJSON (mkCoverage args));

  genomeExcludes = [
    "cache/reference"
    "cache/pgs_catalog"
    "cache/tools"
    "cache/pylibs"
    "cache/snpeff"
    "cache/gwas_sumstats"
    ".direnv"
  ];
  genomeCoveragePolicy = mkCoveragePolicy {
    label = "genome";
    bindTarget = "/run/borgbackup-snapshot-inputs/genome";
    exclude = genomeExcludes;
    noncanonical = genomeExcludes;
    producerProof = true;
  };

  realmCoveragePolicy = mkCoveragePolicy {
    label = "realm";
    bindTarget = borgRealmSnapshotBind;
    exclude = realmExcludes;
    noncanonical = realmNoncanonical;
  };

  mkSnapshotDrainScript =
    {
      label,
      repo,
      repoPath,
      snapshotDir,
      snapshotGlob,
      bindTarget,
      archivePrefix,
      replacementSuffix ? "",
      exclude,
      noncanonical,
      producerProof ? label == "realm",
    }:
    let
      coveragePolicy = mkCoveragePolicy {
        inherit
          label
          bindTarget
          exclude
          noncanonical
          producerProof
          ;
      };
    in
    ''
      set -euo pipefail
      export LC_ALL=C
      ${mkBorgCommonScript repo}
      install -d -m 0750 -o root -g users ${lib.escapeShellArg borgDrainStateRoot}
      latest_marker=${lib.escapeShellArg "${borgDrainStateRoot}/${label}.latest-archived"}
      pending_receipt=${lib.escapeShellArg "${borgDrainStateRoot}/${label}.pending-create.json"}
      acquire_borg_global_lock_or_skip "${label} Borg drain"

      cleanup_snapshot_bind_mount() {
        if mountpoint -q ${lib.escapeShellArg bindTarget}; then
          umount ${lib.escapeShellArg bindTarget}
        fi
      }
      cleanup_snapshot_bind_mount
      trap cleanup_snapshot_bind_mount EXIT
      install -d -m 0700 -o root -g root ${lib.escapeShellArg repoPath}
      install -d -m 0700 -o root -g root ${lib.escapeShellArg bindTarget}
      if [ ! -e ${lib.escapeShellArg "${repoPath}/config"} ]; then
        with_borg_lock borg init --encryption repokey-blake2 "$BORG_REPO"
      fi

      marker=${lib.escapeShellArg "${borgDrainStateRoot}/${label}.last-success"}
      acknowledgement_root="$latest_marker.by-snapshot"
      install -d -m 0750 -o root -g users "$acknowledgement_root"
      # Adopt only the same named, still-identified current-policy proof. This
      # does not repeat a large comparison or hand the snapshot to another state.
      if [ -f "$latest_marker" ] && previous="$(${snapshotCoverage} acknowledged --policy ${coveragePolicy} -- ${lib.escapeShellArg snapshotDir} ${lib.escapeShellArg snapshotGlob} "$latest_marker" ${lib.escapeShellArg archivePrefix} ${lib.escapeShellArg replacementSuffix})"; then
        previous_acknowledgement="$acknowledgement_root/$previous"
        if [ ! -e "$previous_acknowledgement" ] && [ ! -L "$previous_acknowledgement" ]; then
          publish_backup_marker "$previous_acknowledgement" < "$latest_marker"
        fi
      fi
      publish_acknowledgement() {
        advance="$(${snapshotCoverage} advance-marker ${lib.escapeShellArg snapshotDir} "$latest_marker" "$snapshot")"
        if [ "$advance" = yes ]; then
          publish_backup_marker "$latest_marker" < "$acknowledgement"
        fi
        publish_backup_marker "$marker" < "$acknowledgement"
      }
      # Admit one finite queue. Later acquisitions wait for the next wake.
      snapshots="$(${snapshotCoverage} queue -- ${lib.escapeShellArg snapshotDir} ${lib.escapeShellArg snapshotGlob} "$latest_marker" ${lib.escapeShellArg archivePrefix} ${lib.escapeShellArg replacementSuffix})"
      release_borg_global_lock

      # Archive one snapshot ($snapshot): create, verify and acknowledge it.
      # The caller holds the Borg lock for the whole call. A failure exits
      # the script, which releases the lock with the process.
      drain_cut() {
        acknowledgement="$acknowledgement_root/$snapshot"
        if [ -f "$acknowledgement" ]; then
          acknowledged="$(${snapshotCoverage} acknowledged -- ${lib.escapeShellArg snapshotDir} ${lib.escapeShellArg snapshotGlob} "$acknowledgement" ${lib.escapeShellArg archivePrefix} ${lib.escapeShellArg replacementSuffix})"
          [ "$acknowledged" = "$snapshot" ] || exit 1
          publish_acknowledgement
          return
        fi
        snapshot_path=${lib.escapeShellArg snapshotDir}/"$snapshot"
        archive_name=${lib.escapeShellArg archivePrefix}-"$snapshot"
        # btrbk long-iso names carry the cut's offset. Retention follows
        # source time even when a newest-first backlog is archived much later.
        cut="''${snapshot#*.}"
        snapshot_timestamp="$(date --date="''${cut:0:4}-''${cut:4:2}-''${cut:6:2} ''${cut:9:2}:''${cut:11:2}:''${cut:13:2} ''${cut:15}" --utc +%Y-%m-%dT%H:%M:%S)"
        original_archive_name="$archive_name"
        snapshot_details="$(${snapshotCoverage} details "$snapshot_path")"
        snapshot_filesystem="$(${snapshotCoverage} filesystem-identity "$snapshot_path")"
        IFS=$'\t' read -r snapshot_uuid snapshot_generation snapshot_id <<< "$snapshot_details"
        mount --bind "$snapshot_path" ${lib.escapeShellArg bindTarget}
        archives="$(with_borg_lock borg list --short "$BORG_REPO")"
        archive_created=0
        producer_proof=""
        create_archive_id=""
        create_seconds=0
        create_original_bytes=0
        if [ -n ${lib.escapeShellArg replacementSuffix} ] && printf '%s\n' "$archives" | grep -Fxq "$original_archive_name"; then
          # This archive predates the policy repair. Keep it untouched and
          # prove a separately named archive before deleting the snapshot.
          archive_name="$original_archive_name"${lib.escapeShellArg replacementSuffix}
        fi
        if [ ${lib.escapeShellArg label} = persist ]; then
          # Recheck the newest previously created coverage replacement after
          # an interrupted full proof, rather than creating another archive.
          suffix=3
          while printf '%s\n' "$archives" | grep -Fxq "$original_archive_name-coverage-v$suffix"; do
            archive_name="$original_archive_name-coverage-v$suffix"
            suffix=$((suffix + 1))
          done
        fi
        create_archive() {
          create_started="$(date +%s)"
          if ! create_stats="$(with_borg_lock borg create \
            --json --quick-stats \
            --timestamp "$snapshot_timestamp" \
            --files-cache ctime,size,inode --files-changed ctime \
            --compression auto,zstd,1 \
            --lock-wait ${toString borgLockWaitSec} \
            --comment "sinnix-snapshot-v1:$snapshot_uuid" \
            ${mkBorgExcludeArgs bindTarget exclude} \
            "::$archive_name" ${lib.escapeShellArg "${bindTarget}/./"})"; then
            echo "borg create failed for ${label} snapshot $snapshot; subvolume kept on disk" >&2
            return 1
          fi
          create_seconds=$(( $(date +%s) - create_started ))
          if ! create_receipt="$(printf '%s' "$create_stats" | ${pkgs.jq}/bin/jq -er \
            --arg name "$archive_name" 'select(.archive.name == $name) | [.archive.id,.archive.stats.original_size] | @tsv')"; then
            echo "borg create returned no usable stats; retaining ${label} snapshot $snapshot" >&2
            return 1
          fi
          IFS=$'\t' read -r create_archive_id create_original_bytes <<< "$create_receipt"
          if [[ ! "$create_archive_id" =~ ^[0-9a-f]{64}$ || ! "$create_original_bytes" =~ ^[0-9]+$ ]]; then
            echo "borg create returned invalid stats; retaining ${label} snapshot $snapshot" >&2
            return 1
          fi
          if [ ${lib.boolToString producerProof} = true ]; then
            if ! created_receipt="$(printf '%s' "$create_stats" | ${snapshotCoverage} record-create \
              ${lib.escapeShellArg bindTarget} "$archive_name" ${coveragePolicy} | ${pkgs.jq}/bin/jq -c \
              --argjson seconds "$create_seconds" '. + {create_seconds:$seconds}')"; then
              echo "Could not bind Borg create to snapshot; retaining ${label} snapshot $snapshot" >&2
              return 1
            fi
            if ! printf '%s\n' "$created_receipt" | publish_backup_marker "$pending_receipt"; then
              echo "Could not publish creation receipt; retaining ${label} snapshot $snapshot" >&2
              return 1
            fi
          fi
          archive_created=1
          echo "backup_phase=create label=${label} archive=$archive_name elapsed_seconds=$create_seconds original_bytes=$create_original_bytes"
        }
        if [ ${lib.boolToString producerProof} = true ] && [ -f "$pending_receipt" ]; then
          if receipt_archive="$(${pkgs.jq}/bin/jq -er '.archive' "$pending_receipt" 2>/dev/null)" \
            && [[ "$receipt_archive" == "$original_archive_name" || "$receipt_archive" == "$original_archive_name"-* ]] \
            && printf '%s\n' "$archives" | grep -Fxq "$receipt_archive" \
            && producer_proof="$(${snapshotCoverage} verify-created ${lib.escapeShellArg bindTarget} \
              "$receipt_archive" "$snapshot_uuid" ${coveragePolicy} "$pending_receipt" 2>/dev/null)"; then
            archive_name="$receipt_archive"
          fi
        fi
        if [ ${lib.boolToString producerProof} = true ] && [ -z "$producer_proof" ] \
          && printf '%s\n' "$archives" | grep -Fxq "$archive_name"; then
          if ! producer_proof="$(${snapshotCoverage} verify-created ${lib.escapeShellArg bindTarget} \
            "$archive_name" "$snapshot_uuid" ${coveragePolicy} "$pending_receipt" 2>/dev/null)"; then
            # An unreceipted archive has no observed successful create. Do
            # not promote it; create a separately named archive instead.
            suffix=1
            archive_name="$original_archive_name-producer-v$suffix"
            while printf '%s\n' "$archives" | grep -Fxq "$archive_name"; do
              suffix=$((suffix + 1))
              archive_name="$original_archive_name-producer-v$suffix"
            done
          fi
        fi
        if [ -z "$producer_proof" ] && ! printf '%s\n' "$archives" | grep -Fxq "$archive_name"; then
          if ! create_archive; then
            cleanup_snapshot_bind_mount
            exit 1
          fi
        fi
        # These lanes accept only the observed zero-warning create or its matching
        # durable receipt; its independent full comparison has its own job.
        # Persist keeps its first/policy-change/weekly full comparison and
        # uses a producer proof on fresh creates between those checks.
        if [ ${lib.boolToString producerProof} = true ]; then
          proof_mode=created
          if [ -n "$producer_proof" ]; then
            proof="$producer_proof"
          elif ! proof="$(${snapshotCoverage} verify-created ${lib.escapeShellArg bindTarget} \
            "$archive_name" "$snapshot_uuid" ${coveragePolicy} "$pending_receipt")"; then
            cleanup_snapshot_bind_mount
            exit 1
          fi
        else
          proof_mode=full
          if [ "$archive_created" = 1 ]; then
            proof_mode="$(${snapshotCoverage} proof-mode "$latest_marker" ${lib.escapeShellArg snapshotDir} ${coveragePolicy})"
          fi
          if ! proof="$(${snapshotCoverage} verify ${lib.escapeShellArg bindTarget} "$archive_name" "$snapshot_uuid" ${coveragePolicy} \
            --mode "$proof_mode" --latest-marker "$latest_marker" --snapshot-directory ${lib.escapeShellArg snapshotDir})"; then
            if [ "$archive_created" = 1 ]; then
              cleanup_snapshot_bind_mount
              exit 1
            fi
            # A legacy archive can have omitted a canonical directory under
            # marker-driven Borg exclusions. A failed full comparison never
            # acknowledges it; retry one fresh name under the current policy.
            suffix=3
            archive_name="$original_archive_name-coverage-v$suffix"
            while printf '%s\n' "$archives" | grep -Fxq "$archive_name"; do
              suffix=$((suffix + 1))
              archive_name="$original_archive_name-coverage-v$suffix"
            done
            if ! create_archive; then
              cleanup_snapshot_bind_mount
              exit 1
            fi
            proof_mode=full
            if ! proof="$(${snapshotCoverage} verify ${lib.escapeShellArg bindTarget} "$archive_name" "$snapshot_uuid" ${coveragePolicy} \
              --mode full --latest-marker "$latest_marker" --snapshot-directory ${lib.escapeShellArg snapshotDir})"; then
              cleanup_snapshot_bind_mount
              exit 1
            fi
          fi
        fi
        if [ "$archive_created" = 1 ] && ! printf '%s' "$proof" | ${pkgs.jq}/bin/jq -e \
          --arg id "$create_archive_id" '.archive_id == $id' >/dev/null; then
          echo "Created archive identity changed; retaining $snapshot_path" >&2
          cleanup_snapshot_bind_mount
          exit 1
        fi
        proof="$(printf '%s' "$proof" | ${pkgs.jq}/bin/jq -c \
          --argjson create_seconds "$create_seconds" \
          --argjson create_original_bytes "$create_original_bytes" \
          '. + {create_seconds:(.create_seconds // $create_seconds),create_original_bytes:(.create_original_bytes // $create_original_bytes)}')"
        echo "backup_phase=verify label=${label} archive=$archive_name mode=$proof_mode $(printf '%s' "$proof" | ${pkgs.jq}/bin/jq -r '"elapsed_seconds=\(.verification_seconds) source_hashed_bytes=\(.source_hashed_bytes) archive_content_verified_bytes=\(.archive_content_verified_bytes)"')"
        cleanup_snapshot_bind_mount
        if [ "$(${snapshotCoverage} details "$snapshot_path")" != "$snapshot_details" ] ||
          [ "$(${snapshotCoverage} filesystem-identity "$snapshot_path")" != "$snapshot_filesystem" ]; then
          echo "Snapshot identity changed; retaining $snapshot_path" >&2
          exit 1
        fi
        {
          printf 'archive=%s\n' "$archive_name"
          printf 'snapshot=%s\n' "$snapshot"
          printf 'filesystem_uuid=%s\n' "$snapshot_filesystem"
          printf 'generation=%s\n' "$snapshot_generation"
          printf 'subvolume_id=%s\n' "$snapshot_id"
          printf 'coverage=%s\n' "$proof"
          printf 'epoch=%s\n' "$(date +%s)"
        } | publish_backup_marker "$acknowledgement"
        publish_acknowledgement
      }

      # Delete one acknowledged snapshot ($old, with its expected identity).
      # The caller holds the Borg lock. Maintenance may have changed archives
      # since the plan was made, so this snapshot's archive and source are
      # checked again first. Sets retired=1 when it deleted the snapshot.
      retire_snapshot() {
        current="$(${snapshotCoverage} prune-candidate -- ${lib.escapeShellArg snapshotDir} ${lib.escapeShellArg snapshotGlob} "$latest_marker" ${lib.escapeShellArg archivePrefix} ${lib.escapeShellArg replacementSuffix} "$old")"
        [ "$current" = "$(printf '%s\t%s\t%s\t%s' "$old" "$expected_uuid" "$expected_generation" "$expected_id")" ] || return 0
        old_path=${lib.escapeShellArg snapshotDir}/"$old"
        # Independent audits pin only their selected snapshot, not the Borg
        # lock. Never wait on that pin while draining.
        exec 8<"$old_path"
        if ! flock -n -x 8; then
          echo "Retaining snapshot held by an independent audit: $old"
          exec 8<&-
          return 0
        fi
        actual_details="$(${snapshotCoverage} details "$old_path")"
        cutoff_filesystem="$(${pkgs.gnused}/bin/sed -n 's/^filesystem_uuid=//p' "$latest_marker")"
        if [ "$(${snapshotCoverage} filesystem-identity "$old_path")" != "$cutoff_filesystem" ]; then
          echo "Snapshot filesystem changed; retaining $old_path" >&2
          exit 1
        fi
        if [ "$actual_details" != "$(printf '%s\t%s\t%s' "$expected_uuid" "$expected_generation" "$expected_id")" ]; then
          echo "Snapshot identity changed; retaining $old_path" >&2
          exit 1
        fi
        btrfs subvolume delete "$old_path"
        exec 8<&-
        retired=1
      }

      # The Borg lock is taken once per snapshot, so maintenance and checks
      # queued behind it run between cuts and between deletions.
      while IFS= read -r snapshot; do
        [ -n "$snapshot" ] || continue
        acquire_borg_global_lock
        drain_cut
        release_borg_global_lock
      done <<< "$snapshots"

      # Every acknowledged snapshot except the newest is deleted; the newest
      # stays for the independent audit. An interrupted run resumes next wake.
      if [ -f "$latest_marker" ]; then
        acquire_borg_global_lock
        prune_plan="$(${snapshotCoverage} prune-plan -- ${lib.escapeShellArg snapshotDir} ${lib.escapeShellArg snapshotGlob} "$latest_marker" ${lib.escapeShellArg archivePrefix} ${lib.escapeShellArg replacementSuffix})"
        release_borg_global_lock
        while IFS=$'\t' read -r old expected_uuid expected_generation expected_id; do
          [ -n "$old" ] || continue
          retired=0
          acquire_borg_global_lock
          retire_snapshot
          release_borg_global_lock
          [ "$retired" = 1 ] || continue
          # Cleaner completion and pressure settling do not use Borg, so they
          # run without the lock. Waiting for both before the next deletion
          # keeps the cleaners' I/O from piling up.
          btrfs subvolume sync ${lib.escapeShellArg snapshotDir} "$expected_id"
          for _ in $(seq 60); do
            io_full="$(${pkgs.gawk}/bin/awk '/^full/ { sub("avg10=", "", $2); print int($2) }' /proc/pressure/io)"
            [ "''${io_full:-0}" -lt 10 ] && break
            sleep 5
          done
        done <<< "$prune_plan"
      fi
    '';

  chromeCacheRoot = "home/sinity/.config/chrome-ws";
  chromeCacheRoots = map (path: "${chromeCacheRoot}/${path}") [
    "Default/Shared Dictionary/cache"
    "System Profile/Shared Dictionary/cache"
    "Default/AutofillAiModelCache"
    "Default/DawnGraphiteCache"
    "Default/DawnWebGPUCache"
    "Default/GPUCache"
    "Default/optimization_guide_hint_cache_store"
    "GPUPersistentCache"
    "GrShaderCache"
    "GraphiteDawnCache"
    "ShaderCache"
    "component_crx_cache"
    "extensions_crx_cache"
  ];
  # The verifier accepts these only when the wildcard is a Chrome extension ID
  # (32 lowercase a-p characters) and the terminal path names this producer.
  chromeExtensionCacheExcludes = map (path: "${chromeCacheRoot}/Default/Storage/ext/*/def/${path}") [
    "DawnGraphiteCache"
    "DawnWebGPUCache"
    "GPUCache"
    "Shared Dictionary/cache"
  ];

  persistExcludes = [
    # Archive-relative patterns: paths start from the /persist snapshot root.
    "home/sinity/.local/share/Steam"
    "home/sinity/.cache/huggingface"
    "home/sinity/.cache/spotify"
    "root/.cache/borg"
    # User caches are regenerable and currently large enough to dominate
    # backup churn if included.
    "home/sinity/.cache"
    # Pure regenerable caches and logs, multi-GB each.
    "home/sinity/.cargo/registry"
    "home/sinity/.cargo/git"
    "home/sinity/.npm/_cacache"
    # Python virtualenvs and tool stores, CACHEDIR.TAG'd by their own tooling
    # and therefore already absent from every archive. Measured shares of the
    # persist coverage gap on 2026-09-14: venv 13651, .venv 4441, uv 13151,
    # the nested cargo registry 10366 -- together 41609 of 43057.
    "home/sinity/.hermes/hermes-agent/venv"
    "home/sinity/.hermes/hermes-agent/.venv"
    "home/sinity/.local/share/uv"
    # Agent CLI installs: npm trees and source-built recovery copies are
    # reinstalled by the bootstrap; the ledgers beside them stay covered.
    "home/sinity/.local/state/claude-code/npm"
    "home/sinity/.local/state/claude-code/npm-recovery"
    "home/sinity/.npm/_npx"
    "home/sinity/.local/share/nvim/mason"
    "home/sinity/.local/share/hyprland/logs"
    "var/lib/systemd/coredump"
    # Sinex runtime state is backed up through structured service tooling.
    "var/lib/sinex"
    # AgentCTL launch inputs are transient launch documents. Inputs written
    # before secret values moved to the runtime directory still hold them;
    # none belongs in an archive.
    "home/sinity/.local/state/agentctl/inputs"
  ]
  ++ chromeCacheRoots
  ++ chromeExtensionCacheExcludes;

  realmExcludes = [
    # Re-acquirable media: Steam, model weights, and private project caches
    # regenerable members carry their own provenance. Precious-small media
    # (books, videos, substack, edu, music-audio-features, web-content)
    # deliberately stays in coverage.
    # steamapps, not library/game/steam: the games are 98G of the 103G and Steam
    # re-downloads them, but the remaining ~5G is client state that CONTAINS
    # library/game/steam/userdata -- Steam Cloud save files and game recordings, which
    # no reinstall recreates.
    #
    # While the plain-path patterns were inert, userdata was being backed up by
    # accident (145 entries measured in archive realm-realm.20260816T223000).
    # Repairing the patterns immediately dropped it, which is the whole hazard
    # of fixing a rule that was never doing anything: whatever it was quietly
    # over-preserving starts disappearing on the same commit.
    #
    # Excluding the parent and re-including the child does NOT work here --
    # measured: borg stops recursing into an excluded directory, so a `+`
    # pattern for the subtree never gets the chance to match, and the archive
    # ends at `media` with nothing beneath it.
    # Acquired weight stores keep their existing exclusion policy. Authored
    # control vectors and unclassified new model children stay covered.
    # The model home itself is never an exclusion boundary.
    # Steam's exclusion names steamapps directly to retain userdata.
    "library/game/steam/steamapps"
    "library/model/ollama"
    "library/model/gguf"
    "library/model/sherpa"
    "library/model/photoprism"
    "library/model/sd-checkpoints"
    "library/model/tts"
    # Older snapshots still hold these paths.
    "library/games/steam/steamapps"
    "library/models"
    # Regenerable-cache root (sinex cargo/dev caches via the
    # /var/cache/sinex bind, nix-build) — pure churn, never backup material.
    "state/cache"
    # 285G of public reference downloads: GRCh38 reference (156G), PGS Catalog
    # (101G), kraken2, dbSNP, snpEff, GWAS sumstats. Re-acquirable from their
    # upstreams exactly like media/model, and matched by neither "cache"
    # (top-level only) nor "**/.cache" (dot-prefixed only), so it had been
    # replicating into borg-realm-v2 in full. The irreplaceable half of that
    # tree — genotype/, holding the 70G of raw FASTQ reads that cannot be
    # regenerated without re-sequencing — stays in coverage deliberately.
    "health/genome/cache"
    # 23G of podman OCI layers (the graphroot set in services/ml-containers.nix,
    # deliberately on /realm rather than the wear-limited root). Images are
    # re-pullable by digest and the modules that use them pin those digests, so
    # this is the same class as library/model and the caches above -- it simply
    # was not named, and had been replicating in full. Checked before
    # excluding: the whole 23G is overlay/ image layers, and volumes/ is
    # EMPTY -- these containers keep their data on bind mounts under
    # /realm/library and /realm/state, which stay in coverage. If a named
    # volume ever appears here, this exclusion starts dropping real state.
    "state/containers"
    # Codex installs its app-server releases here; it re-fetches them.
    "state/codex/home/packages"
    # Scratch trees, declared unbacked in /realm/INVENTORY.md: TMPDIR and job
    # scratch under tmp/, agent checkouts under worktrees/ whose commits live
    # in their origin repositories. Neither self-describes as a cache, so both
    # had been archiving in full -- 47.5 GB over 248,583 entries and 1.4 GB
    # over 95,835 entries respectively, measured in archive
    # realm-realm.20260905T160000+0200.
    #
    # Top-level entries, not `**/tmp` or `**/worktrees`: a tmp/ inside a real
    # dataset stays covered. inbox/ is deliberately absent -- downloads land
    # there (196 GB in the same archive) and exist nowhere else.
    "tmp"
    "worktree"
    "worktrees"
    ".pytest_cache"
    "project/.pytest_cache"
    # A directory name alone does not establish that its contents can be
    # recreated. Broad exclusions formerly matched source material under
    # build/, dist/, node_modules/, and other project-local names. The two
    # pytest roots above are classified separately; nested names stay covered.
    # Freedesktop trash at the realm root is one such exact root.
    ".Trash-1000"
    # Regenerable build and environment trees, each checked to hold only
    # rebuildable content: Cargo targets (CACHEDIR.TAG), Python virtualenvs,
    # Stash's analysis cache and generated media (tagged by sinnix), and
    # downloaded embedding weights. Exact roots, because coverage waives only
    # explicitly classified paths, never a tag or glob.
    "project/polylogue/repo/target"
    "project/polylogue-sinex-common/repo/target"
    "project/sinex/repo/target"
    "project/sinnix/repo/.venv"
    "project/sinity-lynchpin/repo/.venv"
    "project/yt-polisher/repo/.venv"
    # Polylogue's index.db is "everything parsed and derived", rebuilt from
    # archive.db when deleted (polylogue docs/architecture.md). At 16 GB and
    # rewritten continuously, it was reread by every realm drain.
    # The rest of state/polylogue-live is a plain directory of the /realm
    # subvolume, so the drain reads it from an atomic btrbk snapshot while the
    # daemon runs. Polylogue's docs/operations.md accepts an atomic snapshot of
    # the archive directory as a consistent backup; no dump step is needed.
  ]
  ++ polylogueIndexExcludes
  ++ [
    "state/stashbox/analysis-cache"
    "state/stashbox/generated"
    "state/stashbox/gpu-venv"
    "state/comfyui/venv"
    "library/model/embedding"
    # Steam's runtimes and client package, re-downloaded by the client.
    # userdata beside them stays covered.
    "library/game/steam/ubuntu12_32"
    "library/game/steam/ubuntu12_64"
    "library/game/steam/steamrt32"
    "library/game/steam/steamrt64"
    "library/game/steam/package"
  ];

  # These named roots have an existing cache/scratch producer policy. Broad
  # globs and inherited CACHEDIR.TAG/.nobackup annotations are not evidence
  # that unknown matching material is noncanonical. Missing such material
  # therefore retains its snapshot. Dedicated live Sinex state and Steam user
  # state are also not excused by a cache classification.
  # Intersect an explicit classification with the real creation exclusions:
  # adding another exclusion never silently authorizes snapshot deletion.
  persistNoncanonical = lib.intersectLists persistExcludes (
    [
      "home/sinity/.cache/huggingface"
      "home/sinity/.cache/spotify"
      "root/.cache/borg"
      "home/sinity/.cache"
      # Cargo tags both of these with CACHEDIR.TAG, so --exclude-caches already
      # kept them out of every archive while nothing classified them. The lane
      # could not prove coverage and retained every snapshot (96853 entries under
      # .cargo/git alone). Classified here explicitly, as the policy above
      # requires: the tag is not the authorization, this line is. Both are
      # re-fetched by cargo from the network on demand.
      "home/sinity/.cargo/registry"
      "home/sinity/.cargo/git"
      "home/sinity/.npm/_cacache"
      # Python virtualenvs and tool stores, CACHEDIR.TAG'd by their own tooling
      # and therefore already absent from every archive. Measured shares of the
      # persist coverage gap on 2026-09-14: venv 13651, .venv 4441, uv 13151,
      # the nested cargo registry 10366 -- together 41609 of 43057.
      "home/sinity/.hermes/hermes-agent/venv"
      "home/sinity/.hermes/hermes-agent/.venv"
      "home/sinity/.local/share/uv"
      "home/sinity/.local/state/claude-code/npm"
      "home/sinity/.local/state/claude-code/npm-recovery"
      "home/sinity/.npm/_npx"
      "home/sinity/.local/share/nvim/mason"
      "home/sinity/.local/share/hyprland/logs"
      "var/lib/systemd/coredump"
      # Launch documents of queued jobs, rewritten per launch. Results and
      # logs stay covered under jobs/; an input is not needed to read them.
      "home/sinity/.local/state/agentctl/inputs"
    ]
    ++ chromeCacheRoots
  );
  realmNoncanonical = lib.intersectLists realmExcludes (
    [
      "library/game/steam/steamapps"
      "library/model/ollama"
      "library/model/gguf"
      "library/model/sherpa"
      "library/model/photoprism"
      "library/model/sd-checkpoints"
      "library/model/tts"
      # Older snapshots still hold these paths.
      "library/games/steam/steamapps"
      "library/models"
      "state/cache"
      "health/genome/cache"
      "state/containers"
      # Codex installs its app-server releases here; it re-fetches them.
      "state/codex/home/packages"
      "tmp"
      "worktree"
      "worktrees"
      # Pytest writes these caches from subprocess runs rooted at /realm and
      # /realm/project. Borg excludes them through **/.pytest_cache; these
      # exact roots are disposable and may be absent from an archive.
      ".pytest_cache"
      "project/.pytest_cache"
      # Freedesktop trash: deleted-by-the-operator content. Its absence from an
      # archive is the intended state, not missing canonical data. Without this
      # the coverage checker reports "canonical content missing from archive"
      # and correctly retains every snapshot -- which stalled the realm drain
      # from 2026-09-14 and starved three other borg repositories behind its
      # lock. 23 GB / ~1.55M entries at the time of diagnosis.
      ".Trash-1000"
      # Regenerable build and environment trees, each checked to hold only
      # rebuildable content: Cargo targets (CACHEDIR.TAG), Python virtualenvs,
      # Stash's analysis cache and generated media (tagged by sinnix), and
      # downloaded embedding weights. Exact roots, because coverage waives only
      # explicitly classified paths, never a tag or glob.
      "project/polylogue/repo/target"
      "project/polylogue-sinex-common/repo/target"
      "project/sinex/repo/target"
      "project/sinnix/repo/.venv"
      "project/sinity-lynchpin/repo/.venv"
      "project/yt-polisher/repo/.venv"
      # Polylogue's index.db is "everything parsed and derived", rebuilt from
      # archive.db when deleted (polylogue docs/architecture.md). At 16 GB and
      # rewritten continuously, it was reread by every realm drain.
    ]
    ++ polylogueIndexExcludes
    ++ [
      "state/stashbox/analysis-cache"
      "state/stashbox/generated"
      "state/stashbox/gpu-venv"
      "state/comfyui/venv"
      "library/model/embedding"
      # Steam's runtimes and client package, re-downloaded by the client.
      # userdata beside them stays covered.
      "library/game/steam/ubuntu12_32"
      "library/game/steam/ubuntu12_64"
      "library/game/steam/steamrt32"
      "library/game/steam/steamrt64"
      "library/game/steam/package"
    ]
  );

  realmExcludeMatchesProtectedPath = import ./lib/backup/protected-paths.nix {
    inherit lib;
    paths = protectedRealmArchivePaths;
  };

  mkBeadsCheckScript = ''
    set -euo pipefail

    ${mkBorgCommonScript borgRepoRealm}
    exec 9>${lib.escapeShellArg borgGlobalLock}
    if ! flock -w ${toString beadsCheckLockWaitSec} 9; then
      echo "another Borg operation held the lock for ${toString beadsCheckLockWaitSec} s; the Beads restore check did not run" >&2
      exit 1
    fi

    mapfile -t archives < <(borg list --short --glob-archives 'realm-*' ${lib.escapeShellArg borgRepoRealm} | sort)
    if [ "''${#archives[@]}" -eq 0 ]; then
      echo "no realm Borg archive is available for the Beads restore check" >&2
      exit 1
    fi
    archive="''${archives[$(( ''${#archives[@]} - 1 ))]}"

    # Declared task authorities must be in the archive; every other tracker
    # the archive holds under state/tasks is checked too.
    declare -A project_uuid=(${
      lib.concatMapStrings (
        store:
        "[${lib.escapeShellArg store.path}]=${
          lib.escapeShellArg (if store.projectUuid == null then "" else store.projectUuid)
        } "
      ) beadsArchivePaths
    })
    # Only tracker metadata files are listed: listing every file under
    # state/tasks held millions of names in memory (2.7 GB peak on the host).
    mapfile -t members < <(borg list --short \
      --pattern '+ re:^state/tasks/[^/]+/\.beads/metadata\.json$' ${
        lib.escapeShellArgs (
          lib.concatMap (store: [
            "--pattern"
            "+ pf:${store.path}/metadata.json"
          ]) beadsArchivePaths
        )
      } \
      --pattern '- re:.*' \
      "${borgRepoRealm}::''${archive}" ${
        lib.escapeShellArgs (
          [ "state/tasks" ]
          ++ lib.filter (path: !lib.hasPrefix "state/tasks/" path) (map (store: store.path) beadsArchivePaths)
        )
      })
    # A set lookup, not `printf | grep -q`: grep stopping at the first match
    # breaks the pipe, which pipefail reports as a failure.
    declare -A archived=()
    stores=(${lib.escapeShellArgs (map (store: store.path) beadsArchivePaths)})
    for member in "''${members[@]}"; do
      archived["$member"]=1
      if [[ "$member" =~ ^state/tasks/[^/]+/\.beads/metadata\.json$ ]]; then
        stores+=("''${member%/metadata.json}")
      fi
    done
    mapfile -t stores < <(printf '%s\n' "''${stores[@]}" | sort -u)
    for store in "''${stores[@]}"; do
      if [ -z "''${archived["$store/metadata.json"]:-}" ]; then
        echo "Beads store $store is missing from $archive" >&2
        exit 1
      fi
    done

    # The stores together are a few gigabytes, too much for the /tmp tmpfs.
    mkdir -p ${lib.escapeShellArg "${realmRoot}/tmp"}
    restore_root="$(mktemp -d -p ${lib.escapeShellArg "${realmRoot}/tmp"} beads-restore.XXXXXX)"
    cleanup() {
      rm -rf "$restore_root"
    }
    trap cleanup EXIT

    (
      cd "$restore_root"
      borg extract "${borgRepoRealm}::''${archive}" "''${stores[@]}"
    )

    records=()
    for store in "''${stores[@]}"; do
      beads_path="$restore_root/$store"
      test -s "$beads_path/metadata.json"
      jq -e 'type == "object"' "$beads_path/metadata.json" >/dev/null
      test -s "$beads_path/config.yaml"
      database_name="$(jq -er '.dolt_database | select(type == "string" and test("^[A-Za-z0-9_-]+$"))' "$beads_path/metadata.json")"
      expected_uuid="''${project_uuid[$store]:-}"
      if [ -n "$expected_uuid" ]; then
        jq -e --arg project_id "$expected_uuid" '.project_id == $project_id' "$beads_path/metadata.json" >/dev/null
      fi
      # A server-mode store keeps its databases under dolt/, an embedded one
      # under embeddeddolt/.
      if jq -e '.dolt_mode == "server"' "$beads_path/metadata.json" >/dev/null; then
        database_path="$beads_path/dolt"
      else
        database_path="$beads_path/embeddeddolt"
      fi
      test -d "$database_path/$database_name/.dolt"

      # A restored server configuration can name a live port. Open the
      # database in a separate scratch data directory without that
      # configuration.
      offline_root="$restore_root/offline/$store"
      mkdir -p "$offline_root"
      mv "$database_path/$database_name" "$offline_root/$database_name"
      dolt_commit="$(${pkgs.dolt}/bin/dolt --data-dir "$offline_root" --use-db "$database_name" sql \
        -q 'SELECT commit_hash FROM dolt_log LIMIT 1' -r json \
        | jq -er '.rows[0].commit_hash | select(test("^[0-9a-v]{32}$"))')"
      issue="$(${pkgs.dolt}/bin/dolt --data-dir "$offline_root" --use-db "$database_name" sql \
        -q 'SELECT id, title FROM issues ORDER BY id LIMIT 1' -r json \
        | jq -cer '.rows[0] | select(.id != null and .id != "" and .title != null and .title != "")')"
      records+=("$(jq -nc \
        --arg type beads_restore_drill \
        --arg archive "$archive" \
        --arg store "$store" \
        --arg dolt_commit "$dolt_commit" \
        --argjson issue "$issue" \
        --arg ts "$(date -Iseconds)" \
        '{ts:$ts,type:$type,archive:$archive,store:$store,dolt_commit:$dolt_commit,issue:$issue,ok:true}')")
    done

    # Records are written only after every store restored.
    install -d -m 0755 ${lib.escapeShellArg (builtins.dirOf beadsCheckLog)}
    printf '%s\n' "''${records[@]}" | tee -a ${lib.escapeShellArg beadsCheckLog}
  '';

  btrbkConfig = ''
    # === Global settings ===
    timestamp_format        long-iso
    snapshot_create          onchange
    incremental             yes
    preserve_day_of_week    monday
    snapshot_preserve_min   latest
    ssh_identity            /etc/ssh/ssh_host_ed25519_key
    transaction_log         /var/log/btrbk.log
    lockfile                /var/lock/btrbk.lock

    # ─── Snapshot handoff queue ───
    # btrbk creates point-in-time local snapshots; Borg is responsible for
    # durable retention. The systemd btrbk service runs with
    # --preserve-snapshots, so only Borg drain jobs delete snapshots, after
    # each candidate snapshot has its own verified archive.

    volume ${realmRoot}
      snapshot_dir   .btrfs/snapshot
      subvolume .
        snapshot_preserve_min   all

    volume /persist
      snapshot_dir   .btrfs/snapshot
      subvolume .
        snapshot_preserve_min   all

    # / is ephemeral (wiped and recreated each boot by initrd rollback script).
    # Pre-wipe states are saved to .snapshots/root.TIMESTAMP and archived by
    # a separate borg job (borgbackup-root-snapshots) that picks them up,
    # backs them up, and deletes the subvolume.

  ''
  + lib.optionalString (backupCfg.genomeRoot != null) ''
    volume ${config.sinnix.paths.neoOuterRealm}
      snapshot_dir .btrfs/genome-snapshots
      subvolume ${lib.removePrefix "${config.sinnix.paths.neoOuterRealm}/" (toString backupCfg.genomeRoot)}
          snapshot_name genome
        snapshot_preserve_min all
  '';

in
{
  options.sinnix.backup = {
    enable = (lib.mkEnableOption "workstation snapshot and archive backups") // {
      default = config.sinnix.machine.isDesktop;
    };
    genomeRoot = lib.mkOption {
      type = lib.types.nullOr lib.types.path;
      default = null;
      description = "Optional HDD-backed genome subvolume with its own snapshot and Borg coverage.";
    };
  };

  config = lib.mkIf backupCfg.enable (
    lib.mkMerge (
      [
        {
          assertions = [
            {
              assertion = lib.all (
                path: builtins.elem path realmExcludes && builtins.elem path realmNoncanonical
              ) (import ./lib/storage/scratch-roots.nix);
              message = "Realm scratch subvolumes must name exact Borg-excluded regenerable roots.";
            }
          ];

          services.borgbackup.jobs = lib.mkMerge [
            (lib.mkIf
              (
                options.services ? sinex
                && config.services.sinex.enable
                && config.services.sinex.backup.repo != null
              )
              {
                sinex.preHook = lib.mkBefore borgHostIdentity;
              }
            )
            (lib.mkIf
              (
                options.services ? sinex
                && config.services.sinex.enable
                && config.services.sinex.backup.keysRepo != null
              )
              {
                sinex-keys.preHook = lib.mkBefore borgHostIdentity;
              }
            )
          ];

          # The realm archive's observed working set paged heavily under the
          # 2G/4G background slice. Give this one low-I/O-priority Borg lane
          # memory headroom without raising limits for every backup service.
          systemd.slices.borgdrain.sliceConfig = {
            CPUWeight = 3;
            IOWeight = 20;
            MemoryHigh = "6G";
            MemoryMax = "8G";
          };

          sinnix.runtime.units = {
            borgbackup-drain-coordinator = {
              unit = "borgbackup-drain-coordinator.service";
              resourceClass = "backup";
              notifyOnFailure = true;
              operatorRestart = false;
            };
            btrbk = {
              unit = "btrbk.service";
              resourceClass = "backup";
              captures = lib.optional (backupCfg.genomeRoot != null) {
                name = "genome-acquisition-inventory";
                path = genomeAcquisitionInventory;
                eventDriven = true;
                staleAfterSeconds = borgAcquisitionObservationMaxAgeSec;
              };
            };
            btrbk-timer = {
              unit = "btrbk.timer";
              notifyOnFailure = true;
              operatorRestart = false;
            };
            borgbackup-job-persist = {
              unit = "borgbackup-job-persist.service";
              resourceClass = "backup";
              notifyOnFailure = true;
              operatorRestart = false;
              captures = [
                {
                  name = "borg-persist-archive";
                  path = "${borgDrainStateRoot}/persist.latest-archived";
                  eventDriven = true;
                  livenessProbe = {
                    command = "${snapshotCoverage} freshness ${borgDrainStateRoot}/persist.latest-archived ${toString borgDataFreshnessMaxAgeSec}";
                    timeoutSeconds = 15;
                  };
                }
              ];
            };
            borgbackup-job-persist-hourly = {
              unit = "borgbackup-job-persist-hourly.service";
              resourceClass = "backup";
              resources = {
                IOSchedulingClass = "idle";
                Nice = 19;
              };
              notifyOnFailure = true;
              operatorRestart = false;
              captures = [
                {
                  name = "borg-persist-hourly-archive";
                  path = "${borgDrainStateRoot}/persist-hourly.last-success";
                  eventDriven = true;
                  staleAfterSeconds = borgHourlyMaxAgeSec;
                }
              ];
            };
            borgbackup-job-live-small = {
              unit = "borgbackup-job-live-small.service";
              resourceClass = "backup";
              resources = {
                IOSchedulingClass = "idle";
                Nice = 19;
              };
              notifyOnFailure = true;
              operatorRestart = false;
              captures = [
                {
                  name = "borg-live-small-archive";
                  path = "${borgDrainStateRoot}/live-small.last-success";
                  eventDriven = true;
                  staleAfterSeconds = borgHourlyMaxAgeSec;
                }
              ];
            };
            borgbackup-job-realm = {
              unit = "borgbackup-job-realm.service";
              resourceClass = "backup";
              resources = {
                Slice = "borgdrain.slice";
                # Let the file/chunk caches use the admitted memory budget
                # before reclaim forces them through swap.
                MemoryHigh = "6G";
                MemoryMax = "6G";
              };
              notifyOnFailure = true;
              operatorRestart = false;
              captures = [
                {
                  name = "borg-realm-archive";
                  path = "${borgDrainStateRoot}/realm.latest-archived";
                  eventDriven = true;
                  livenessProbe = {
                    command = "${snapshotCoverage} freshness ${borgDrainStateRoot}/realm.latest-archived ${toString borgDataFreshnessMaxAgeSec}";
                    timeoutSeconds = 15;
                  };
                }
              ];
            };
            borgbackup-job-genome = lib.mkIf (backupCfg.genomeRoot != null) {
              unit = "borgbackup-job-genome.service";
              resourceClass = "backup";
              resources = {
                Slice = "borgdrain.slice";
                MemoryHigh = "6G";
                MemoryMax = "6G";
              };
              notifyOnFailure = true;
              operatorRestart = false;
              captures = [
                {
                  name = "borg-genome-archive";
                  path = "${borgDrainStateRoot}/genome.latest-archived";
                  eventDriven = true;
                  livenessProbe = {
                    command = "${snapshotCoverage} acquisition-freshness ${genomeAcquisitionInventory} 'genome.*' ${borgDrainStateRoot}/genome.latest-archived ${genomeCoveragePolicy} ${toString borgDataFreshnessMaxAgeSec} --source ${lib.escapeShellArg (toString backupCfg.genomeRoot)} --max-observation-age ${toString borgAcquisitionObservationMaxAgeSec} --producer-unit btrbk.service";
                    timeoutSeconds = 15;
                  };
                }
              ];
            };
            # Declared only when the job exists: archives.nix builds this job
            # under the same predicate, and a surface whose unit is never
            # configured advertises an envelope nothing applies.
            borgbackup-job-sinex-blobs = lib.mkIf (sinexStorePaths != [ ]) {
              unit = "borgbackup-job-sinex-blobs.service";
              resourceClass = "backup";
              notifyOnFailure = true;
              operatorRestart = false;
              captures = [
                {
                  name = "borg-sinex-blobs-archive";
                  path = "${borgDrainStateRoot}/sinex-blobs.last-success";
                  eventDriven = true;
                  # The nightly coordinator invokes this lane after snapshot drains;
                  # retain the existing three-day freshness budget.
                  staleAfterSeconds = borgDailyArchiveMaxAgeSec;
                }
              ];
            };
            polylogue-sqlite-backup = {
              unit = "polylogue-sqlite-backup.service";
              resourceClass = "backup";
              notifyOnFailure = true;
            };
            borgbackup-job-polylogue-state = {
              unit = "borgbackup-job-polylogue-state.service";
              resourceClass = "backup";
              notifyOnFailure = true;
              operatorRestart = false;
              captures = [
                {
                  name = "borg-polylogue-state-archive";
                  path = "${borgDrainStateRoot}/polylogue-state.last-success";
                  eventDriven = true;
                  # Nightly coordinator, same three-day budget as sinex-blobs.
                  staleAfterSeconds = borgDailyArchiveMaxAgeSec;
                }
              ];
            };
            borgbackup-coverage-audit-realm = {
              unit = "borgbackup-coverage-audit-realm.service";
              resourceClass = "backup";
              notifyOnFailure = true;
              operatorRestart = false;
              captures = [
                {
                  name = "borg-realm-independent-coverage-audit";
                  path = realmCoverageAuditReceipt;
                  eventDriven = true;
                  staleAfterSeconds = 691200;
                  livenessProbe = {
                    command = "${snapshotCoverage} audit-status ${realmCoverageAuditReceipt} ${realmCoveragePolicy} 691200 --mode sampled";
                    timeoutSeconds = 10;
                  };
                }
              ];
            };
            borgbackup-verify = {
              unit = "borgbackup-verify.service";
              resourceClass = "backup";
              notifyOnFailure = true;
              operatorRestart = false;
              captures = [
                {
                  name = "borg-check";
                  path = "${config.sinnix.paths.machineRoot}/borg_drill.jsonl";
                  eventDriven = true;
                  # borgbackup-verify.timer runs weekly (604800s); budget 3x
                  # cadence so one missed/delayed run doesn't false-positive.
                  staleAfterSeconds = 1814400;
                }
                {
                  name = "borg-integrity-receipt";
                  path = borgIntegrityReceipt;
                  eventDriven = true;
                  # Same 3x-weekly-cadence budget as the borg-check lane above: the
                  # receipt only updates on a verify run.
                  staleAfterSeconds = 1814400;

                }
              ];
            };
            borgbackup-maintenance = {
              unit = "borgbackup-maintenance.service";
              resourceClass = "backup";
              notifyOnFailure = true;
              operatorRestart = false;
              captures = [
                {
                  name = "backup-maintenance";
                  path = "${borgDrainStateRoot}/maintenance.last-success";
                  eventDriven = true;
                  staleAfterSeconds = 172800;
                }
              ];
            };
            borgbackup-local-dumps = {
              unit = "borgbackup-local-dumps.service";
              resourceClass = "backup";
              notifyOnFailure = true;
              operatorRestart = false;
            };
            borgbackup-retention-plan = {
              unit = "borgbackup-retention-plan.service";
              resourceClass = "backup";
              operatorRestart = false;
            };
            borgbackup-capacity = {
              unit = "borgbackup-capacity.service";
              resourceClass = "backup";
              notifyOnFailure = true;
              captures = [
                {
                  name = "backup-capacity";
                  path = "${borgDrainStateRoot}/capacity.json";
                  eventDriven = true;
                  staleAfterSeconds = 86400;
                }
              ];
            };
            borgbackup-root-snapshots = {
              unit = "borgbackup-root-snapshots.service";
              resourceClass = "backup";
            };
            sinnix-borg-beads-check = {
              unit = "sinnix-borg-beads-check.service";
              resourceClass = "backup";
              captures = [
                {
                  name = "borg-beads-check";
                  path = beadsCheckLog;
                  eventDriven = true;
                  staleAfterSeconds = 1814400;
                }
              ];
            };
          };

          environment.systemPackages = [
            pkgs.btrbk
            pkgs.borgbackup
          ];

          environment.etc."btrbk/btrbk.conf".text = btrbkConfig;
          environment.etc."sinnix/backup.json".text = builtins.toJSON backupConfig;
        }

      ]
      ++ (import ./lib/backup/snapshots.nix {
        inherit
          snapshotCoverage
          genomeCoveragePolicy
          genomeAcquisitionInventory
          pkgs
          lib
          borgRepoRoot
          polylogueBackupRoot
          realmSnapshots
          persistSnapshots
          borgSnapshotBindRoot
          borgPersistSnapshotBind
          borgRealmSnapshotBind
          borgDrainStateRoot
          borgRepoPersistPath
          borgRepoRealmPath
          borgRepoRootSnapshotsPath
          borgRepoSinexBlobsPath
          borgRepoPolylogueStatePath
          borgCacheDir
          borgGlobalLock
          mkBackupJob
          genomeSnapshots
          ;
        genomeRoot = backupCfg.genomeRoot;
      })
      ++ (import ./lib/backup/archives.nix {
        inherit
          coordinatorPolicies
          pkgs
          lib
          realmRoot
          sinexStorePaths
          sinexBackupRepositories
          scriptPkgs
          username
          polylogueStateRoot
          polylogueBackupRoot
          paidVectorRoot
          polylogueDbNames
          polylogueDbExcludes
          borgDrainStateRoot
          borgRepoRealmPath
          borgRepoSinexBlobsPath
          borgRepoPolylogueStatePath
          borgRepoPersist
          borgRepoRealm
          borgRepoRootSnapshots
          borgRepoSinexBlobs
          borgRepoPolylogueState
          borgRepoLiveSmall
          borgPassphrasePath
          outerRealmMountUnit
          borgLockWaitSec
          borgCacheDir
          borgGlobalLock
          mkBackupJob
          mkBorgExcludeArgs
          mkBorgCommonScript
          ;
      })
      ++ (import ./lib/backup/acknowledgement.nix {
        inherit
          coordinatorPolicies
          config
          lib
          pkgs
          realmSnapshots
          persistSnapshots
          borgPersistSnapshotBind
          borgRealmSnapshotBind
          borgRepoPersistPath
          borgRepoRealmPath
          borgRepoRootSnapshotsPath
          borgRepoPersist
          borgRepoRealm
          borgRepoRootSnapshots
          borgPassphrasePath
          outerRealmMountUnit
          borgLockWaitSec
          borgCacheDir
          borgDrainStateRoot
          mkBackupJob
          mkBorgCommonScript
          mkSnapshotDrainScript
          snapshotCoverage
          persistExcludes
          realmExcludes
          persistNoncanonical
          realmNoncanonical
          username
          genomeSnapshots
          ;
        genomeRoot = backupCfg.genomeRoot;
      })
      ++ (import ./lib/backup/hourly.nix {
        inherit
          pkgs
          lib
          realmRoot
          username
          polylogueArchiveRoot
          sinexSpoolPaths
          borgRepoPersist
          borgRepoPersistPath
          borgRepoLiveSmall
          borgRepoLiveSmallPath
          borgPersistSnapshotBind
          borgDrainStateRoot
          borgCacheDir
          borgHourlyCacheDir
          borgLockWaitSec
          outerRealmMountUnit
          persistExcludes
          mkBackupJob
          mkBorgCommonScript
          mkBorgExcludeArgs
          ;
      })
      ++ (import ./lib/backup/genome.nix {
        inherit
          genomeExcludes
          pkgs
          lib
          genomeSnapshots
          borgRepoRealm
          borgRepoRealmPath
          outerRealmMountUnit
          mkBackupJob
          mkSnapshotDrainScript
          ;
        genomeRoot = backupCfg.genomeRoot;
        neoOuterRealm = config.sinnix.paths.neoOuterRealm;
      })
      ++ (import ./lib/backup/local-dumps.nix {
        inherit
          coordinatorPolicies
          pkgs
          lib
          realmRoot
          realmSnapshots
          realmCoveragePolicy
          snapshotCoverage
          borgDrainStateRoot
          borgRepoRealm
          outerRealmMountUnit
          scriptPkgs
          mkBackupJob
          mkBorgCommonScript
          ;
      })
      ++ (import ./lib/backup/verification.nix {
        inherit
          pkgs
          lib
          config
          sinexStorePaths
          sinexBackupRepositories
          scriptPkgs
          borgDrainStateRoot
          borgIntegrityReceipt
          realmCoverageAuditReceipt
          borgRepoPersist
          borgRepoRealm
          realmSnapshots
          realmCoveragePolicy
          snapshotCoverage
          borgRepoSinexBlobs
          borgPassphrasePath
          outerRealmMountUnit
          borgCacheDir
          protectedRealmArchivePaths
          mkBackupJob
          mkBorgCommonScript
          realmExcludes
          realmExcludeMatchesProtectedPath
          mkBeadsCheckScript
          ;
      })
    )
  );
}
