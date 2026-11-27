# Backups: btrbk snapshots /realm and /persist, the initrd keeps the ephemeral
# root's states, and Borg archives them to /outer-realm. Nix declares policy,
# units and timers; `sinnix-backup` (pkgs/sinnix-backup) does the work.
{
  pkgs,
  lib,
  config,
  options,
  helpers,
  ...
}:
let
  inherit (config.sinnix.paths) realmRoot neoOuterRealm;
  sinexEnabled = options.services ? sinex && config.services.sinex.enable;
  # Stopped Sinex deployments; the running one has its own sinex-backup.service.
  sinexStorePaths = lib.optionals sinexEnabled config.sinnix.services.sinex.retainedStores;
  sinexRepositories = lib.filterAttrs (_: url: url != null) (
    lib.optionalAttrs sinexEnabled {
      sinex-core = config.services.sinex.backup.repo;
      sinex-keys = config.services.sinex.backup.keysRepo;
    }
  );
  sinexRepositoryNames = lib.attrNames sinexRepositories;
  borgRepoRoot = "${config.sinnix.paths.outerRealm}/backup";
  scriptPkgs = helpers.mkSinnixPackagesFor pkgs;
  username = config.sinnix.user.name;
  backupCfg = config.sinnix.backup;
  # Without archive backups the Borg units stay defined for manual starts,
  # and their freshness lanes go, so an unscheduled archive raises no alarm.
  archiveCaptures = captures: lib.optionals backupCfg.archive.enable captures;
  genomeSnapshots = "${neoOuterRealm}/.btrfs/genome-snapshots";

  # A nested subvolume outside the /realm snapshots, dumped and archived directly.
  polylogueStateRoot = config.sinnix.services.polylogue.dataDir;
  polylogueDbNames = [
    "source.db"
    "embeddings.db"
    "ops.db"
    "audit.db"
    "user.db"
  ];
  # The direct archive never reads the dumped databases or their WAL/SHM files.
  polylogueDbExcludes = lib.concatMap (name: [
    name
    "${name}-wal"
    "${name}-shm"
  ]) polylogueDbNames;
  polylogueArchiveRoot = config.sinnix.runtime.inventory.polylogue.archiveRoot;

  borgSnapshotBindRoot = "/run/borgbackup-snapshot-inputs";
  # Local /realm and /persist snapshots kept by count: two days at four cuts a
  # day. The count holds whether or not Borg has archived them, so a paused
  # backup cannot pin deleted data; the drain archives the newest it finds.
  localSnapshots = 8;
  borgDrainStateRoot = "/persist/root/.cache/borg-drain";
  repositoryUrls = lib.mapAttrs (_: directory: "file://${borgRepoRoot}/${directory}") {
    persist = "borg-persist-v1";
    realm = "borg-realm-v2";
    root-snapshots = "borg-root-snapshots-v1";
    sinex-blobs = "borg-sinex-blobs-v1";
    polylogue-state = "borg-polylogue-state-v1";
    live-small = "borg-live-small-v1";
  };
  # Borg caches are regenerable and kept off the worn root SSD.
  borgCacheDir = "${realmRoot}/state/cache/borg";
  # Declared Beads task stores; the restore check also finds others in state/tasks.
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
  # Lynchpin reads this file by path.
  beadsCheckLog = "${config.sinnix.paths.machineRoot}/borg_beads_drill.jsonl";
  # Paths under /realm no exclude pattern may cover, ancestors included.
  protectedRealmArchivePaths =
    lib.concatMap (store: [
      store.path
      "${store.path}/metadata.json"
      "${store.path}/config.yaml"
      "${store.path}/${store.database}"
    ]) beadsArchivePaths
    ++ [
      # Ranking domains: operator judgments nothing can recompute.
      "activity/shared/ranking"
      "library/model/control-vector"
    ];
  # A day between accepted cuts plus six hours of grace.
  borgDailyMaxAgeSec = 30 * 60 * 60;
  # Hourly jobs skip while the nightly run holds the lock.
  borgHourlyMaxAgeSec = 6 * 60 * 60;
  borgAcquisitionObservationMaxAgeSec = 3 * 6 * 60 * 60;
  genomeAcquisitionInventory = "${borgDrainStateRoot}/genome.acquisition-inventory.json";
  # A daily marker counts only while its policy hash matches these inputs.
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
        policy = realmCoverage;
      }
    );
  };

  # Borg matches excludes against the full path it walks, which starts with
  # the bind mount: qualify plain paths with it, keep fnmatch style (`pp:`
  # cannot glob), and pass `**` patterns through.
  borgExcludePatterns =
    root: exclude:
    let
      rootRelative = lib.removePrefix "/" root;
      qualify = pattern: if lib.hasPrefix "**" pattern then pattern else "${rootRelative}/${pattern}";
    in
    map qualify exclude;

  # One source's coverage policy; its JSON is hashed into every archive record.
  mkCoverage =
    label: exclusions:
    {
      noncanonical = map (e: e.path) (lib.filter (e: e.mayBeMissing) exclusions);
      chrome_extension_caches = label == "persist";
      borg_excludes = borgExcludePatterns "${borgSnapshotBindRoot}/${label}" (map (e: e.path) exclusions);
    }
    // lib.optionalAttrs (label != "persist") { producer_contract = "realm-borg-create-v2"; };

  # Exclusions, relative to the snapshot root. `mayBeMissing`: the coverage
  # check accepts the path's absence from an archive. docs/backups.md
  # ("Exclusions and why") gives the reason for each class.
  allowMissing = map (path: {
    inherit path;
    mayBeMissing = true;
  });
  refuseMissing = map (path: {
    inherit path;
    mayBeMissing = false;
  });
  chromeCacheRoot = "home/sinity/.config/chrome-ws";
  persistExclusions =
    refuseMissing [ "home/sinity/.local/share/Steam" ]
    # User and Borg caches.
    ++ allowMissing [
      "home/sinity/.cache/huggingface"
      "home/sinity/.cache/spotify"
      "root/.cache/borg"
      "home/sinity/.cache"
      # Package registries and virtualenvs, fetched again on demand.
      "home/sinity/.cargo/registry"
      "home/sinity/.cargo/git"
      "home/sinity/.npm/_cacache"
      "home/sinity/.hermes/hermes-agent/venv"
      "home/sinity/.hermes/hermes-agent/.venv"
      "home/sinity/.local/share/uv"
      # Agent CLI installs, reinstalled by the bootstrap.
      "home/sinity/.local/state/claude-code/npm"
      "home/sinity/.local/state/claude-code/npm-recovery"
      "home/sinity/.npm/_npx"
      "home/sinity/.local/share/nvim/mason"
      "home/sinity/.local/share/hyprland/logs"
      "var/lib/systemd/coredump"
    ]
    # Backed up by Sinex's own service tooling.
    ++ refuseMissing [ "var/lib/sinex" ]
    # Launch documents of queued jobs; results and logs stay covered.
    ++ allowMissing [ "home/sinity/.local/state/agentctl/inputs" ]
    # Chrome's regenerable caches.
    ++ allowMissing (
      map (path: "${chromeCacheRoot}/${path}") [
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
      ]
    )
    # Excused by `chrome_extension_caches` only under a Chrome extension ID.
    ++ refuseMissing (
      map (path: "${chromeCacheRoot}/Default/Storage/ext/*/def/${path}") [
        "DawnGraphiteCache"
        "DawnWebGPUCache"
        "GPUCache"
        "Shared Dictionary/cache"
      ]
    );

  realmExclusions = allowMissing (
    [
      # Steam's games, not its userdata beside them.
      "library/game/steam/steamapps"
      # Downloaded model weights; authored control vectors stay covered.
      "library/model/ollama"
      "library/model/gguf"
      "library/model/sherpa"
      "library/model/photoprism"
      "library/model/sd-checkpoints"
      "library/model/tts"
      # Earlier locations older snapshots hold, and the regenerable cache root.
      "library/games/steam/steamapps"
      "library/models"
      "state/cache"
      # Public genome reference downloads; raw reads stay covered.
      "health/genome/cache"
      # Container image layers and Codex releases, fetched again on demand.
      "state/containers"
      "state/codex/home/packages"
      # The filesystem index can be rebuilt. Its authored inputs stay covered.
      "state/fs-index/generations"
      # Scratch, agent checkouts, pytest caches and trash; inbox/ stays covered.
      "tmp"
      "worktree"
      "worktrees"
      ".pytest_cache"
      "project/.pytest_cache"
      ".Trash-1000"
      # Build and environment trees that hold only rebuildable content.
      "project/polylogue/repo/target"
      "project/polylogue-sinex-common/repo/target"
      "project/sinex/repo/target"
      "project/sinnix/repo/.venv"
      "project/sinity-lynchpin/repo/.venv"
      "project/yt-polisher/repo/.venv"
    ]
    # Polylogue rebuilds these index files from the stored archive and segments.
    ++ lib.concatMap (
      archive:
      map (name: lib.removePrefix "${realmRoot}/" "${archive}/${name}") [
        "index.db"
        "index.db-wal"
        "index.db-shm"
        "index-rebuild"
      ]
    ) ([ polylogueArchiveRoot ] ++ config.sinnix.services.polylogue.retainedArchives)
    # Stash's caches and media, the ComfyUI venv and downloaded embedding weights.
    ++ [
      "state/stashbox/analysis-cache"
      "state/stashbox/generated"
      "state/stashbox/gpu-venv"
      "state/comfyui/venv"
      "library/model/embedding"
      # Steam's runtimes and client package, downloaded again by the client.
      "library/game/steam/ubuntu12_32"
      "library/game/steam/ubuntu12_64"
      "library/game/steam/steamrt32"
      "library/game/steam/steamrt64"
      "library/game/steam/package"
    ]
  );

  # Public reference caches, downloaded tools and dependency environments.
  genomeExclusions = allowMissing [
    "cache/reference"
    "cache/pgs_catalog"
    "cache/tools"
    "cache/pylibs"
    "cache/snpeff"
    "cache/gwas_sumstats"
    ".direnv"
  ];

  realmExcludes = map (e: e.path) realmExclusions;
  persistCoverage = mkCoverage "persist" persistExclusions;
  realmCoverage = mkCoverage "realm" realmExclusions;
  genomeCoverage = mkCoverage "genome" genomeExclusions;
  # Left out of root archives; the same list is their coverage policy.
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
  realmExcludeMatchesProtectedPath = import ./lib/backup/protected-paths.nix {
    inherit lib;
    paths = protectedRealmArchivePaths;
  };

  # A disabled producer module contributes no unit to the nightly sequence.
  configuredUnits = lib.filter (
    name: builtins.hasAttr name config.systemd.services && config.systemd.services.${name}.enable
  );
  dumpUnits = configuredUnits (
    lib.optional config.sinnix.services.machine-telemetry.enable "machine-telemetry-sqlite-backup"
    ++ lib.optional config.sinnix.services.polylogue.enable "polylogue-sqlite-backup"
  );
  # Direct-path archives run before the drains, so a backlog cannot delay them.
  archiveUnits = configuredUnits (
    lib.optional config.sinnix.services.polylogue.enable "borgbackup-job-polylogue-state"
    ++ [
      "borgbackup-job-sinex-blobs"
      "borgbackup-job-realm"
      "borgbackup-job-genome"
      "borgbackup-job-persist"
      "sinex-backup"
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

  # Archive name patterns (space-separated) of one repository's series.
  keep = repository: active: retired: {
    inherit repository;
    active = lib.splitString " " active;
    retired = if retired == "" then [ ] else lib.splitString " " retired;
  };
  checkFor = repository: seconds: { inherit repository seconds; };
  # A unit's daily marker and the policy hash that keeps it fresh.
  dailyMarker = name: policy: [
    "${borgDrainStateRoot}/${name}.last-success"
    coordinatorPolicies.${policy}
  ];
  repository = _: url: {
    inherit url;
    path = lib.removePrefix "file://" url;
  };

  # The policy every `sinnix-backup` command reads from /etc/sinnix/backup.json.
  backupConfig = {
    state_directory = borgDrainStateRoot;
    # Archives, checks and manual Borg commands share this lock.
    lock_path = "/run/lock/sinnix-borg.lock";
    cache_directory = borgCacheDir;
    # The hourly jobs' cache is on the repository disk, idle between runs.
    hourly_cache_directory = "${borgRepoRoot}/borg-hourly-cache";
    passphrase_path = config.sinnix.secrets.paths."borg-passphrase";
    scratch_directory = "${realmRoot}/tmp/work";
    lock_wait_seconds = 60;
    repositories = lib.mapAttrs repository (repositoryUrls // sinexRepositories);
    sources = {
      persist = {
        repository = "persist";
        snapshot_directory = "/persist/.btrfs/snapshot";
        name_glob = "persist.*";
        bind_path = "${borgSnapshotBindRoot}/persist";
        archive_prefix = "persist";
        replacement_suffix = "-coverage-v2";
        coverage = persistCoverage;
        create_check = false;
        files_cache_suffix = null;
        local_snapshots = localSnapshots;
      };
      realm = {
        repository = "realm";
        snapshot_directory = "${realmRoot}/.btrfs/snapshot";
        name_glob = "realm.*";
        bind_path = "${borgSnapshotBindRoot}/realm";
        archive_prefix = "realm";
        replacement_suffix = "-coverage-v3";
        coverage = realmCoverage;
        create_check = true;
        files_cache_suffix = null;
        local_snapshots = localSnapshots;
      };
      # Relative to the top-level subvolume of jobs.root_snapshots.device.
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
        local_snapshots = null;
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
        # A separate files cache, so realm backlogs cannot age genome entries out.
        files_cache_suffix = "genome";
        local_snapshots = null;
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
      sinex_completion =
        if sinexEnabled then "${config.services.sinex.backup.artifactDir}/latest-complete.json" else null;
      daily_markers = {
        "borgbackup-job-polylogue-state.service" = dailyMarker "polylogue-state" "polylogue";
        "borgbackup-job-sinex-blobs.service" = dailyMarker "sinex-blobs" "sinex";
        "borgbackup-local-dumps.service" = dailyMarker "local-dumps" "localDumps";
      };
    };
    jobs = {
      freshness_seconds = borgDailyMaxAgeSec;
      sinex_store_paths = sinexStorePaths;
      polylogue = {
        user = username;
        state_root = polylogueStateRoot;
        dump_root = "${realmRoot}/state/db-dumps/polylogue";
        database_names = polylogueDbNames;
        state_excludes = polylogueDbExcludes ++ [ ".salvage-internals-20261008" ];
        hook_cut_directory = "${realmRoot}/state/cache/polylogue-backup-hooks";
        # The purchased embedding vectors; they never change and cost money to recompute.
        paid_vector_root = "${neoOuterRealm}/archive/polylogue/embeddings";
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
        # Producer spools: frames sinexd has not yet acknowledged.
        sinex_spools = lib.optionals sinexEnabled [
          "${config.services.sinex.stateDir}/spool"
          "${config.services.sinex.session.stateDir}/spool"
        ];
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
        record = "${borgDrainStateRoot}/realm.independent-coverage-audit.json";
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
        # Unit ordering cannot serialize manual Borg commands, so the check waits.
        lock_wait_seconds = 3 * 60 * 60;
        restore_parent = "${realmRoot}/tmp";
      };
      maintenance = {
        marker = "${borgDrainStateRoot}/maintenance.last-success";
        compact_marker = "${borgDrainStateRoot}/compact.last-success";
        retention_directory = "${borgDrainStateRoot}/retention";
        # Active series keep recent, daily, weekly and monthly points; retired ones expire.
        repositories = [
          (keep "persist" "persist-* hourly-persist-*" "sinnix-prime-persist-*")
          (keep "realm" "realm-* genome-genome.*" "sinnix-prime-realm-* machine-telemetry-dumps-*")
          (keep "sinex-blobs" "sinex-blobs-*" "")
        ]
        ++ map (repository: keep repository "sinex-core-*" "") sinexRepositoryNames
        ++ [
          (keep "root-snapshots" "root-*" "")
          (keep "polylogue-state" "polylogue-state-*" "")
          (keep "live-small" "live-small-* polylogue-archive-*" "")
        ];
      };
      integrity = {
        record = "${borgDrainStateRoot}/integrity-check.json";
        # --max-duration makes each weekly pass resume where the last stopped.
        repositories = [
          (checkFor "persist" 1800)
          (checkFor "realm" 7200)
          (checkFor "sinex-blobs" 1800)
        ]
        ++ map (repository: checkFor repository 900) sinexRepositoryNames;
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

  # A stable Borg host identity, so Borg recognizes its own abandoned locks.
  borgHostIdentity = ''
    if [ -z "''${BORG_HOST_ID:-}" ]; then
      borg_machine_id="$(cat /etc/machine-id)"
      if [[ ! "$borg_machine_id" =~ ^[0-9a-f]{32}$ ]]; then
        echo "Invalid machine identity; refusing to start Borg" >&2
        exit 1
      fi
      export BORG_HOST_ID="$(uname -n)@$borg_machine_id"
    fi
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

    # btrbk never deletes: `sinnix-backup take-snapshots` keeps the newest
    # local /realm and /persist snapshots by count, and the drains release
    # archived ones sooner; genome cuts go only after their checked archive.

    volume ${realmRoot}
      snapshot_dir   .btrfs/snapshot
      subvolume .
        snapshot_preserve_min   all

    volume /persist
      snapshot_dir   .btrfs/snapshot
      subvolume .
        snapshot_preserve_min   all

    # / is ephemeral; borgbackup-root-snapshots archives the initrd's root snapshots.

  ''
  + lib.optionalString (backupCfg.genomeRoot != null) ''
    volume ${neoOuterRealm}
      snapshot_dir .btrfs/genome-snapshots
      subvolume ${lib.removePrefix "${neoOuterRealm}/" (toString backupCfg.genomeRoot)}
          snapshot_name genome
        snapshot_preserve_min all
  '';

  backupUnit =
    name: surface:
    {
      unit = "${name}.service";
      resourceClass = "backup";
    }
    // surface;
  # A backup unit whose failure notifies and which the hub never restarts.
  watchedUnit = name: surface: backupUnit name ({ notifyOnFailure = true; } // surface);
  capture = name: path: staleAfterSeconds: {
    inherit name path staleAfterSeconds;
    eventDriven = true;
  };
  probe = command: timeoutSeconds: {
    livenessProbe = {
      command = "${scriptPkgs.sinnix-backup}/bin/sinnix-backup ${command}";
      inherit timeoutSeconds;
    };
  };
  markerCapture =
    label: capture "borg-${label}-archive" "${borgDrainStateRoot}/${label}.last-success";
  drainCapture =
    label: command:
    capture "borg-${label}-archive" "${borgDrainStateRoot}/${label}.latest-archived" null
    // probe command 15;
  hourlyResources = {
    IOSchedulingClass = "idle";
    Nice = 19;
  };
  drainResources = {
    Slice = "borgdrain.slice";
    # The file and chunk caches use the admitted memory before swap.
    MemoryHigh = "6G";
    MemoryMax = "6G";
    # A drain resumes on its next run, so under host OOM it goes before the
    # desktop and services, like an agentctl job (docs/resource-control.md).
    OOMScoreAdjust = 900;
  };
in
{
  options.sinnix.backup = {
    enable = (lib.mkEnableOption "workstation snapshot and archive backups") // {
      default = config.sinnix.machine.isDesktop;
    };
    archive.enable = lib.mkOption {
      type = lib.types.bool;
      default = true;
      description = ''
        Schedule the Borg archive units: the nightly drain coordinator (which
        starts the dumps, drains and the Sinex backup pair), the hourly jobs,
        capacity, verification and the Beads restore check. When false every
        unit stays defined and starts by hand, nothing starts Borg on its own,
        and the archive freshness lanes are dropped. btrbk snapshots and their
        deletion by count stay scheduled either way.
      '';
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
                path:
                lib.any (excluded: path == excluded || lib.hasPrefix "${excluded}/" path) realmCoverage.noncanonical
              ) (import ./lib/storage/scratch-roots.nix);
              message = "Realm scratch subvolumes must stay within named Borg-excluded roots.";
            }
            {
              assertion = lib.all (exclude: !realmExcludeMatchesProtectedPath exclude) realmExcludes;
              message = "The /realm Borg backup must not exclude a protected path: ${lib.concatStringsSep ", " protectedRealmArchivePaths}";
            }
            {
              assertion =
                backupCfg.genomeRoot == null || lib.hasPrefix "${neoOuterRealm}/" (toString backupCfg.genomeRoot);
              message = "The genome backup source must be a subvolume on neo-outer-realm.";
            }
          ];

          services.borgbackup.jobs = lib.mkMerge [
            (lib.mkIf (sinexEnabled && config.services.sinex.backup.repo != null) {
              sinex.preHook = lib.mkBefore borgHostIdentity;
            })
            (lib.mkIf (sinexEnabled && config.services.sinex.backup.keysRepo != null) {
              sinex-keys.preHook = lib.mkBefore borgHostIdentity;
            })
          ];

          # Memory headroom for the low-I/O-priority drains alone.
          systemd.slices.borgdrain.sliceConfig = {
            CPUWeight = 3;
            IOWeight = 20;
            MemoryHigh = "6G";
            MemoryMax = "8G";
          };

          sinnix.runtime.units = {
            borgbackup-drain-coordinator = watchedUnit "borgbackup-drain-coordinator" { };
            btrbk = backupUnit "btrbk" {
              captures = lib.optional (backupCfg.genomeRoot != null) (
                capture "genome-acquisition-inventory" genomeAcquisitionInventory
                  borgAcquisitionObservationMaxAgeSec
              );
            };
            btrbk-timer = {
              unit = "btrbk.timer";
              notifyOnFailure = true;
            };
            borgbackup-job-persist = watchedUnit "borgbackup-job-persist" {
              captures = archiveCaptures [ (drainCapture "persist" "freshness persist") ];
            };
            borgbackup-job-persist-hourly = watchedUnit "borgbackup-job-persist-hourly" {
              resources = hourlyResources;
              captures = archiveCaptures [ (markerCapture "persist-hourly" borgHourlyMaxAgeSec) ];
            };
            borgbackup-job-live-small = watchedUnit "borgbackup-job-live-small" {
              resources = hourlyResources;
              captures = archiveCaptures [ (markerCapture "live-small" borgHourlyMaxAgeSec) ];
            };
            borgbackup-job-realm = watchedUnit "borgbackup-job-realm" {
              resources = drainResources;
              captures = archiveCaptures [ (drainCapture "realm" "freshness realm") ];
            };
            borgbackup-job-genome = lib.mkIf (backupCfg.genomeRoot != null) (
              watchedUnit "borgbackup-job-genome" {
                resources = drainResources;
                captures = archiveCaptures [ (drainCapture "genome" "acquisition-freshness") ];
              }
            );
            # Declared only when units.nix builds the job.
            borgbackup-job-sinex-blobs = lib.mkIf (sinexStorePaths != [ ]) (
              watchedUnit "borgbackup-job-sinex-blobs" {
                captures = archiveCaptures [ (markerCapture "sinex-blobs" borgDailyMaxAgeSec) ];
              }
            );
            polylogue-sqlite-backup = watchedUnit "polylogue-sqlite-backup" { };
            borgbackup-job-polylogue-state = watchedUnit "borgbackup-job-polylogue-state" {
              captures = archiveCaptures [ (markerCapture "polylogue-state" borgDailyMaxAgeSec) ];
            };
            borgbackup-coverage-audit-realm = watchedUnit "borgbackup-coverage-audit-realm" {
              captures = archiveCaptures [
                (
                  capture "borg-realm-independent-coverage-audit" backupConfig.jobs.audit.record 691200
                  // probe "audit-status" 10
                )
              ];
            };
            # Three times the weekly cadence, so one late run is not stale.
            borgbackup-verify = watchedUnit "borgbackup-verify" {
              captures = archiveCaptures [
                (capture "borg-check" "${config.sinnix.paths.machineRoot}/borg_drill.jsonl" 1814400)
                (capture "borg-integrity-receipt" backupConfig.jobs.integrity.record 1814400)
              ];
            };
            borgbackup-maintenance = watchedUnit "borgbackup-maintenance" {
              captures = archiveCaptures [
                (capture "backup-maintenance" backupConfig.jobs.maintenance.marker 172800)
              ];
            };
            borgbackup-local-dumps = watchedUnit "borgbackup-local-dumps" { };
            borgbackup-retention-plan = backupUnit "borgbackup-retention-plan" { };
            borgbackup-capacity = watchedUnit "borgbackup-capacity" {
              captures = archiveCaptures [
                (capture "backup-capacity" "${borgDrainStateRoot}/capacity.json" 86400)
              ];
            };
            borgbackup-root-snapshots = backupUnit "borgbackup-root-snapshots" { };
            sinnix-borg-beads-check = backupUnit "sinnix-borg-beads-check" {
              captures = archiveCaptures [ (capture "borg-beads-check" beadsCheckLog 1814400) ];
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
      ++ import ./lib/backup/units.nix {
        inherit
          lib
          pkgs
          config
          scriptPkgs
          backupConfig
          borgRepoRoot
          genomeSnapshots
          dumpUnits
          archiveUnits
          finalUnits
          ;
        inherit (backupCfg) genomeRoot;
        archiveEnable = backupCfg.archive.enable;
      }
    )
  );
}
