# Comprehensive Unified Backup Strategy
#
# 1. btrbk: Local snapshots for instant rollbacks (block-level, zero I/O overhead)
# 2. Borg: Off-disk incremental backups (file-level, with exclusions, deduplicated)
#
# Drive           Label            Mount            Purpose
# ────────────────────────────────────────────────────────────────────────────
# /dev/nvme0n1p3  SSD_4TB          /realm           Source: projects, data
# /dev/sdb2       root_btrfs       /persist         Source: system & home state
# /dev/sda1       outer-realm      /outer-realm     Target: Borg & btrbk archives
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
  # Sinex publishes this path into every generated runtime/maintenance unit as
  # SINEX_CONTENT_STORE_PATH. Borg must consume the same evaluated topology,
  # rather than reconstructing a backing-subvolume path that can drift after a
  # storage move.
  sinexBlobRepositoryPath = lib.optionalString (
    options.services ? sinex
  ) config.services.sinex.storage.blob.repositoryPath;
  borgRepoRoot = "${config.sinnix.paths.outerRealm}/backup";
  scriptPkgs = helpers.mkSinnixPackagesFor pkgs;
  username = config.sinnix.user.name;

  # state/polylogue is a nested btrfs subvolume (sinnix-3pvd): btrbk snapshots
  # `subvolume .` of /realm, which does not cross subvolume boundaries, so
  # this tree archives as an empty directory under the normal realm coverage.
  # Pulling it into btrbk directly was tried and reverted (commits 9c2c068d,
  # a99f2f7b) because a snapshot forces copy-on-write on the daemon's
  # nodatacow SQLite files on their next write. The fix is the same shape
  # sinex-postgres-dump and machine-telemetry-sqlite-backup already use: a
  # logical dump/direct-path copy on a timer, landing in a plain directory
  # that IS covered by ordinary realm snapshot+borg. polylogued is currently
  # parked (acknowledged.down in modules/services/polylogue.nix) so these
  # jobs run against a quiescent tree today; both are written to work
  # unattended whenever ingestion resumes.
  polylogueStateRoot = config.sinnix.services.polylogue.dataDir;
  polylogueBackupRoot = "${realmRoot}/state/db-dumps/polylogue";
  machineTelemetryBackupRoot = "${realmRoot}/state/db-dumps/machine-telemetry";
  machineTelemetryBackupMarker = "${borgDrainStateRoot}/machine-telemetry-dumps.last-success";
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

  # Snapshot directories
  realmSnapshots = "${realmRoot}/.btrfs/snapshot";
  persistSnapshots = "/persist/.btrfs/snapshot";
  borgSnapshotBindRoot = "/run/borgbackup-snapshot-inputs";
  borgPersistSnapshotBind = "${borgSnapshotBindRoot}/persist";
  borgRealmSnapshotBind = "${borgSnapshotBindRoot}/realm";
  borgDrainStateRoot = "/persist/root/.cache/borg-drain";
  borgIntegrityReceipt = "${borgDrainStateRoot}/integrity-check.json";

  # Borg Configuration
  borgRepoPersistPath = "${borgRepoRoot}/borg-persist-v1";
  borgRepoRealmPath = "${borgRepoRoot}/borg-realm-v2";
  borgRepoRootSnapshotsPath = "${borgRepoRoot}/borg-root-snapshots-v1";
  borgRepoSinexBlobsPath = "${borgRepoRoot}/borg-sinex-blobs-v1";
  borgRepoPolylogueStatePath = "${borgRepoRoot}/borg-polylogue-state-v1";
  btrfsImageRoot = "${borgRepoRoot}/btrfs-images";
  btrfsImageRetentionDays = 30;
  # Never let the age rule take a label below this many images, however long
  # its captures have been failing.
  btrfsImageKeepMinimum = 2;
  # Real images run 0.8-3.9 GB. A floor three orders of magnitude below the
  # smallest observed one only rejects a stub, never a small-but-real capture.
  btrfsImageMinBytes = 64 * 1024 * 1024;
  borgRepoPersist = "file://${borgRepoPersistPath}";
  borgRepoRealm = "file://${borgRepoRealmPath}";
  borgRepoRootSnapshots = "file://${borgRepoRootSnapshotsPath}";
  borgRepoSinexBlobs = "file://${borgRepoSinexBlobsPath}";
  borgRepoPolylogueState = "file://${borgRepoPolylogueStatePath}";
  borgPassphrasePath = config.sinnix.secrets.paths."borg-passphrase";
  outerRealmMountUnit = "outer\\x2drealm.mount";
  borgLockWaitSec = 60;
  borgCacheDir = "/persist/root/.cache/borg";
  borgStaleLockMinutes = 120;
  borgGlobalLock = "/run/lock/sinnix-borg.lock";
  sinexProjectPath = "${realmRoot}/project/sinex";
  sinexBeadsDoltArchivePath = "project/sinex/.beads/dolt";
  sinexBeadsIssuesArchivePath = "project/sinex/.beads/issues.jsonl";
  sinexBeadsDrillLog = "${config.sinnix.paths.machineRoot}/borg_beads_drill.jsonl";
  sinexBeadsArchivePaths = [
    sinexBeadsDoltArchivePath
    sinexBeadsIssuesArchivePath
  ];
  borgArchiveMaxAgeSec = 6 * 60 * 60;
  borgSnapshotQueueMaxAgeSec = 6 * 60 * 60;
  # sinex-blobs runs on its own daily timer (05:40), not the 4h-floor
  # persist/realm drain cadence, so it needs its own budget rather than
  # sharing borgArchiveMaxAgeSec: budget 3x cadence so one missed/delayed
  # run doesn't false-positive, same convention as the capture
  # staleAfterSeconds entries below.
  borgDailyArchiveMaxAgeSec = 3 * 24 * 60 * 60;
  borgDrainMinIntervalSec = 4 * 60 * 60;
  # Every unit in this module is the same shape: a oneshot a timer wakes,
  # never restarted by activation (a switch mid-drain would abandon a bind
  # mount and a held Borg lock), inside the backup-maintenance envelope. Only
  # the first two are stated here -- the envelope comes from the unit's own
  # registered surface, which mkScheduledJob resolves by unit lookup. A
  # module-local serviceConfig helper used to recompute exactly that lookup
  # per unit; the class was never declared twice, only applied twice.
  mkBackupJob =
    name:
    { description, ... }@job:
    lib.sinnix.mkScheduledJob
      {
        inherit config description;
        unitName = name;
        surface = config.sinnix.runtime.surfaces.${name};
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
  # run/borgbackup-snapshot-inputs/realm/cache/... (borg strips the leading
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
  # library/media/Steam 103G, stashbox caches 84G, genome cache 285G, container layers
  # 23G) had been replicating into a 1.9T repository.
  #
  # Reproduced and fixed in a throwaway repo before landing: `--exclude cache`
  # left cache/sub/f in the archive, while the same pattern qualified with the
  # source path removed it.
  #
  # Qualified patterns stay in the default fnmatch style rather than becoming
  # `pp:` path prefixes, and that is load-bearing rather than incidental: `pp:`
  # is a LITERAL prefix with no globbing, and the persist list contains
  # wildcard entries (`.config/chrome-ws/*Cache*`). Measured both ways -- `pp:`
  # left the GPUCache directory in the archive, plain fnmatch excluded it, and
  # both handled a literal directory correctly. fnmatch also matches "from the
  # start of the full path to just before a path separator", so a qualified
  # directory covers everything beneath it.
  #
  # `**/...` patterns pass through unchanged: they are deliberately
  # match-anywhere and qualifying them would defeat that.
  mkBorgExcludeArgs =
    root: exclude:
    let
      rootRelative = lib.removePrefix "/" root;
      qualify = pattern: if lib.hasPrefix "**" pattern then pattern else "${rootRelative}/${pattern}";
    in
    lib.concatMapStringsSep " " (pattern: "--exclude ${lib.escapeShellArg (qualify pattern)}") exclude;

  borgRetentionArgs = [
    "--keep-within"
    "7d"
    "--keep-daily"
    "60"
    "--keep-weekly"
    "26"
    "--keep-monthly"
    "24"
    "--keep-yearly"
    "5"
  ];

  mkBorgRetentionArgs = lib.concatMapStringsSep " " lib.escapeShellArg borgRetentionArgs;

  mkBorgCommonScript = repo: repoPath: ''
    export BORG_REPO=${lib.escapeShellArg repo}
    export BORG_PASSCOMMAND=${lib.escapeShellArg "${pkgs.coreutils}/bin/cat ${borgPassphrasePath}"}
    export BORG_CACHE_DIR=${lib.escapeShellArg borgCacheDir}

    with_borg_lock() {
      if [ "''${SINNIX_BORG_GLOBAL_LOCK_HELD:-0}" = 1 ]; then
        "$@"
      else
        flock ${lib.escapeShellArg borgGlobalLock} "$@"
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

    recover_stale_borg_locks() {
      if [ ! -e ${lib.escapeShellArg "${repoPath}/config"} ]; then
        return
      fi

      stale_lock="$(
        find ${lib.escapeShellArg repoPath} \
          -maxdepth 2 -type d -name lock.exclusive \
          -mmin +${toString borgStaleLockMinutes} -print -quit 2>/dev/null || true
      )"
      if [ -z "$stale_lock" ]; then
        if ! find ${lib.escapeShellArg borgCacheDir} \
          -maxdepth 2 -type d -name lock.exclusive \
          -mmin +${toString borgStaleLockMinutes} -print -quit 2>/dev/null | grep -q .; then
          return
        fi
        stale_lock="stale Borg cache lock"
      fi

      if pgrep -x borg >/dev/null 2>&1; then
        echo "Stale-looking Borg lock remains for ${repo}, but a Borg process is alive; refusing break-lock" >&2
        return
      fi

      echo "Breaking stale Borg lock for ${repo}: $stale_lock" >&2
      with_borg_lock borg break-lock ${lib.escapeShellArg repo}
    }
  '';

  mkSnapshotDrainScript =
    {
      label,
      repo,
      repoPath,
      snapshotDir,
      snapshotGlob,
      bindTarget,
      archivePrefix,
      minIntervalSec,
      exclude,
    }:
    ''
      set -euo pipefail
      shopt -s nullglob

      ${mkBorgCommonScript repo repoPath}

      # 0755, not 0700: the reducer health sweep runs as the operator and
      # watches the marker files here as capture lanes; timestamps are not
      # secrets, and an unreadable lane reads as stale forever.
      install -d -m 0755 -o root -g root ${lib.escapeShellArg borgDrainStateRoot}

      # The coalescing gate runs FIRST, before the global Borg lock. A wake
      # inside the min-interval window has no work to do, so it must cost a
      # single stat -- not a lock acquisition that contends with whatever real
      # Borg operation is running. This is what makes a frequent retry timer
      # free: see the drain timers for why the retry granularity matters.
      stamp=${lib.escapeShellArg "${borgDrainStateRoot}/${label}.stamp"}
      now="$(date +%s)"
      if [ -e "$stamp" ]; then
        last="$(stat -c %Y "$stamp")"
        age=$((now - last))
        if [ "$age" -lt ${toString minIntervalSec} ]; then
          echo "Last ${label} Borg drain was $age seconds ago; keeping snapshots queued for coalescing"
          exit 0
        fi
      fi

      acquire_borg_global_lock_or_skip "${label} Borg drain"

      cleanup_snapshot_bind_mount() {
        if mountpoint -q ${lib.escapeShellArg bindTarget}; then
          umount ${lib.escapeShellArg bindTarget}
        fi
      }
      cleanup_snapshot_bind_mount || true

      install -d -m 0700 -o root -g root ${lib.escapeShellArg repoPath}
      install -d -m 0700 -o root -g root ${lib.escapeShellArg bindTarget}

      recover_stale_borg_locks

      if [ ! -e ${lib.escapeShellArg "${repoPath}/config"} ]; then
        with_borg_lock borg init --encryption repokey-blake2 "$BORG_REPO"
      fi

      trap cleanup_snapshot_bind_mount EXIT

      snapshot="$(
        find ${lib.escapeShellArg snapshotDir} -maxdepth 1 -mindepth 1 -type d -name ${lib.escapeShellArg snapshotGlob} -printf '%f\n' \
          | sort \
          | tail -n 1
      )"

      if [ -z "$snapshot" ]; then
        exit 0
      fi

      snapshot_path=${lib.escapeShellArg snapshotDir}/"$snapshot"
      archive_name=${lib.escapeShellArg archivePrefix}-"$snapshot"

      if with_borg_lock borg list --short --glob-archives "$archive_name" "$BORG_REPO" | grep -Fxq "$archive_name"; then
        echo "Archive $archive_name already exists"
      else

        cleanup_snapshot_bind_mount || true
        mount --bind "$snapshot_path" ${lib.escapeShellArg bindTarget}

        # Membership by property, not by path. The exclude list below is a
        # safety net for things that do not self-describe; these two flags are
        # the primary mechanism, and they evaluate a directory borg has never
        # seen before.
        #
        # --exclude-caches honours CACHEDIR.TAG (bford.info/cachedir/spec.html),
        # which cargo, uv, ruff, pytest and mypy already write unprompted --
        # 94 directories under /realm carry one today, and the path list was
        # missing several of them purely because of what they were named
        # (.lynchpin/cache is not .cache; .sinex/trybuild-target is not target;
        # data/self/genome/cache was 285G of exactly this).
        #
        # .nobackup is sinnix's marker for regenerable-but-not-a-cache:
        # scratch trees where CACHEDIR.TAG would be a lie about what the
        # directory is.
        #
        # Untagged means backed up. A new dataset is therefore over-preserved
        # rather than silently lost, which is the correct direction for the
        # failure to point.
        if with_borg_lock borg create \
          --compression auto,zstd,1 \
          --lock-wait ${toString borgLockWaitSec} \
          --exclude-caches \
          --exclude-if-present .nobackup \
          ${mkBorgExcludeArgs bindTarget exclude} \
          "::$archive_name" ${lib.escapeShellArg "${bindTarget}/./"}; then
          cleanup_snapshot_bind_mount
        else
          echo "borg create failed for ${label} snapshot $snapshot; subvolume kept on disk" >&2
          exit 1
        fi
      fi

      find ${lib.escapeShellArg snapshotDir} -maxdepth 1 -mindepth 1 -type d -name ${lib.escapeShellArg snapshotGlob} -printf '%f\n' \
        | sort \
        | while IFS= read -r queued_snapshot; do
          if [[ "$queued_snapshot" > "$snapshot" ]]; then
            continue
          fi
          echo "Deleting ${label} snapshot $queued_snapshot covered by $archive_name"
          btrfs subvolume delete ${lib.escapeShellArg snapshotDir}/"$queued_snapshot"
        done

      # Retention pruning and compaction are deliberately batched in
      # borgbackup-maintenance.service. Running compaction on every path wake
      # would turn "continuous" backups into repeated HDD churn.
      marker=${lib.escapeShellArg "${borgDrainStateRoot}/${label}.last-success"}
      {
        printf 'archive=%s\n' "$archive_name"
        printf 'snapshot=%s\n' "$snapshot"
        printf 'epoch=%s\n' "$(date +%s)"
      } > "$marker.tmp"
      mv "$marker.tmp" "$marker"
      touch "$stamp"
    '';

  persistExcludes = [
    # Archive-relative patterns: paths start from the /persist snapshot root.
    "home/sinity/.local/share/Steam"
    "home/sinity/.cache/huggingface"
    "home/sinity/.cache/spotify"
    "root/.cache/borg"
    "home/sinity/.config/chrome-ws/Default/Service Worker"
    "home/sinity/.config/chrome-ws/Default/GPUCache"
    "home/sinity/.config/chrome-ws/*Cache*"
    "home/sinity/.config/chrome-ws/*cache*"
    # User caches are regenerable and currently large enough to dominate
    # backup churn if included.
    "home/sinity/.cache"
    # Pure regenerable caches and logs, multi-GB each.
    "home/sinity/.npm/_cacache"
    "home/sinity/.local/share/nvim/mason"
    "home/sinity/.local/share/hyprland/logs"
    "var/lib/systemd/coredump"
    # Sinex runtime state is backed up through structured service tooling.
    "var/lib/sinex"
  ];

  realmExcludes = [
    # Re-acquirable media: Steam and model weights re-download, and stashbox
    # regenerable members carry their own provenance. Precious-small media
    # (books, videos, substack, edu, music-audio-features, web-content)
    # deliberately stays in coverage.
    # steamapps, not library/media/Steam: the games are 98G of the 103G and Steam
    # re-downloads them, but the remaining ~5G is client state that CONTAINS
    # library/media/Steam/userdata -- Steam Cloud save files and game recordings, which
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
    # media/model and the four media/stashbox/* caches used to be listed here
    # too. They are dropped, not repointed: each now carries a CACHEDIR.TAG
    # (commit 2dfa8ae6), and --exclude-caches below already excludes them by
    # that property regardless of where they live -- which is the whole
    # point of a property-based marker surviving the media/ -> library/media/
    # move for free. Steam has no such marker (games do not self-tag as
    # caches), so it is the one entry still named by path, repointed to its
    # new location.
    "library/media/Steam/steamapps"
    # Top-level regenerable-cache root (sinex cargo/dev caches via the
    # /var/cache/sinex bind, nix-build) — pure churn, never backup material.
    "cache"
    # 285G of public reference downloads: GRCh38 reference (156G), PGS Catalog
    # (101G), kraken2, dbSNP, snpEff, GWAS sumstats. Re-acquirable from their
    # upstreams exactly like media/model, and matched by neither "cache"
    # (top-level only) nor "**/.cache" (dot-prefixed only), so it had been
    # replicating into borg-realm-v2 in full. The irreplaceable half of that
    # tree — genotype/, holding the 70G of raw FASTQ reads that cannot be
    # regenerated without re-sequencing — stays in coverage deliberately.
    "data/self/genome/cache"
    # 23G of podman OCI layers (the graphroot set in services/ml-containers.nix,
    # deliberately on /realm rather than the wear-limited root). Images are
    # re-pullable by digest and the modules that use them pin those digests, so
    # this is the same class as library/models and the caches above -- it simply
    # was not named, and had been replicating in full. Checked before
    # excluding: the whole 23G is overlay/ image layers, and volumes/ is
    # EMPTY -- these containers keep their data on bind mounts under
    # /realm/library and /realm/state, which stay in coverage. If a named
    # volume ever appears here, this exclusion starts dropping real state.
    "state/containers"
    "**/inbox/monero"
    "**/node_modules"
    "**/target"
    "**/.venv"
    "**/.direnv"
    "**/.ruff_cache"
    "**/.pytest_cache"
    "**/.cache"
    "**/build"
    "**/dist"
    "**/*.pyc"
    "**/.Trash-1000"
  ];

  # Borg excludes are glob patterns relative to /realm. Test both an item and
  # its ancestors: excluding .beads or project/sinex excludes its children
  # even when the protected item itself does not match the pattern directly.
  borgGlobToRegex =
    pattern:
    let
      globStarPlaceholder = "__SINNIX_BORG_GLOBSTAR__";
      withGlobStarPlaceholder = lib.replaceStrings [ "**" ] [ globStarPlaceholder ] pattern;
      escaped =
        lib.replaceStrings
          [
            "\\"
            "."
            "+"
            "("
            ")"
            "["
            "]"
            "{"
            "}"
            "^"
            "$"
            "|"
          ]
          [
            "\\\\"
            "\\."
            "\\+"
            "\\("
            "\\)"
            "\\["
            "\\]"
            "\\{"
            "\\}"
            "\\^"
            "\\$"
            "\\|"
          ]
          withGlobStarPlaceholder;
      withSingleStar = lib.replaceStrings [ "*" ] [ "[^/]*" ] escaped;
      withQuestion = lib.replaceStrings [ "?" ] [ "[^/]" ] withSingleStar;
    in
    "^${lib.replaceStrings [ globStarPlaceholder ] [ ".*" ] withQuestion}$";
  protectedPathAndAncestors =
    path:
    let
      parts = lib.splitString "/" path;
    in
    lib.genList (index: lib.concatStringsSep "/" (lib.take (index + 1) parts)) (builtins.length parts);
  realmExcludeMatchesProtectedPath =
    exclude:
    lib.any (
      path:
      lib.any (candidate: builtins.match (borgGlobToRegex exclude) candidate != null) (
        protectedPathAndAncestors path
      )
    ) sinexBeadsArchivePaths;

  mkSinexBeadsDrillScript = ''
    set -euo pipefail

    archive_paths=(
      ${lib.escapeShellArg sinexBeadsDoltArchivePath}
      ${lib.escapeShellArg sinexBeadsIssuesArchivePath}
    )

    exec 9>${lib.escapeShellArg borgGlobalLock}
    if ! flock -n 9; then
      echo "another Borg operation is active; skipping Beads restore drill" >&2
      exit 0
    fi

    mapfile -t archives < <(borg list --short --glob-archives 'realm-*' ${lib.escapeShellArg borgRepoRealm} | sort)
    if [ "''${#archives[@]}" -eq 0 ]; then
      echo "no realm Borg archive is available for the Sinex Beads restore drill" >&2
      exit 1
    fi
    archive="''${archives[$(( ''${#archives[@]} - 1 ))]}"

    for archive_path in "''${archive_paths[@]}"; do
      borg list --short "${borgRepoRealm}::''${archive}" "$archive_path" | grep -Fxq "$archive_path"
    done

    restore_root="$(mktemp -d)"
    cleanup() {
      rm -rf "$restore_root"
    }
    trap cleanup EXIT

    (
      cd "$restore_root"
      borg extract "${borgRepoRealm}::''${archive}" "''${archive_paths[@]}"
    )

    issues_path="$restore_root/${sinexBeadsIssuesArchivePath}"
    dolt_path="$restore_root/${sinexBeadsDoltArchivePath}"
    test -s "$issues_path"
    jq -e -s 'length > 0' "$issues_path" >/dev/null
    test -d "$dolt_path/.dolt"

    source_git_head="$(${pkgs.git}/bin/git -c safe.directory=${lib.escapeShellArg sinexProjectPath} -C ${lib.escapeShellArg sinexProjectPath} rev-parse HEAD)"
    dolt_commit="$(${pkgs.dolt}/bin/dolt --data-dir "$dolt_path" --use-db sinex sql \
      -q 'SELECT commit_hash FROM dolt_log LIMIT 1' -r json \
      | jq -er '.rows[0].commit_hash // empty')"

    install -d -m 0755 ${lib.escapeShellArg (builtins.dirOf sinexBeadsDrillLog)}
    jq -nc \
      --arg type sinex_beads_restore_drill \
      --arg archive "$archive" \
      --arg source_git_head "$source_git_head" \
      --arg dolt_commit "$dolt_commit" \
      --arg issues_jsonl_sha256 "$(sha256sum "$issues_path" | cut -d ' ' -f 1)" \
      --arg ts "$(date -Iseconds)" \
      '{ts:$ts,type:$type,archive:$archive,source_git_head:$source_git_head,dolt_commit:$dolt_commit,issues_jsonl_sha256:$issues_jsonl_sha256,ok:true}' \
      | tee -a ${lib.escapeShellArg sinexBeadsDrillLog}
  '';

  # Freshness for the three archive markers (persist/realm/sinex-blobs) and
  # the integrity receipt is now expressed as capture lanes on their owning
  # surfaces (staleAfterSeconds against the marker/receipt file). What a
  # plain staleness check cannot see -- a stalled snapshot queue, an
  # integrity run stuck past its own deadline -- goes through the reducer's
  # livenessProbe exit-code contract instead (0 = fine, 1 = confirmed
  # problem, anything else = the probe itself could not tell, never read as
  # healthy). These two probe scripts implement that; the borgbackup-status
  # oneshot + hourly timer that used to run this logic as a bespoke unit
  # (writing borg_status.jsonl, zero consumers outside itself) is retired.
  mkSnapshotQueueProbeScript = ''
    now="$(${pkgs.coreutils}/bin/date +%s)"

    oldest_epoch() {
      dir="$1"
      glob="$2"
      ${pkgs.findutils}/bin/find "$dir" -maxdepth 1 -mindepth 1 -type d -name "$glob" -printf '%f\n' 2>/dev/null \
        | ${pkgs.coreutils}/bin/sort \
        | ${pkgs.coreutils}/bin/head -n 1 \
        | ${pkgs.gnused}/bin/sed -E 's/^[^.]+\.([0-9]{8})T([0-9]{6})([+-][0-9]{4})$/\1 \2 \3/' \
        | while IFS=' ' read -r day time tz; do
            [ -n "$day" ] || continue
            ${pkgs.coreutils}/bin/date -d "''${day:0:4}-''${day:4:2}-''${day:6:2} ''${time:0:2}:''${time:2:2}:''${time:4:2} $tz" +%s
          done
    }

    # Returns 0 (empty or within budget), 1 (over budget -- drain stalled),
    # or 2 (snapshots present but their age could not be determined: a
    # broken probe, never read as healthy).
    check_one() {
      dir="$1"
      glob="$2"
      count="$(${pkgs.findutils}/bin/find "$dir" -maxdepth 1 -mindepth 1 -type d -name "$glob" 2>/dev/null | ${pkgs.coreutils}/bin/wc -l)"
      [ "$count" -eq 0 ] && return 0
      oldest="$(oldest_epoch "$dir" "$glob")"
      [ -z "$oldest" ] && return 2
      age=$((now - oldest))
      [ "$age" -gt ${toString borgSnapshotQueueMaxAgeSec} ] && return 1
      return 0
    }

    check_one ${lib.escapeShellArg persistSnapshots} 'persist.*'
    persist_rc=$?
    check_one ${lib.escapeShellArg realmSnapshots} 'realm.*'
    realm_rc=$?

    if [ "$persist_rc" -eq 2 ] || [ "$realm_rc" -eq 2 ]; then
      exit 3
    fi
    if [ "$persist_rc" -eq 1 ] || [ "$realm_rc" -eq 1 ]; then
      exit 1
    fi
    exit 0
  '';

  mkIntegrityStuckProbeScript = ''
    receipt=${lib.escapeShellArg borgIntegrityReceipt}
    # No receipt yet is the capture lane's own staleness check to make (or,
    # before the first weekly run, its calm not-yet-run state) -- this probe
    # answers one narrower question, whether an IN-PROGRESS run has overrun
    # its own deadline.
    [ -s "$receipt" ] || exit 0
    now="$(${pkgs.coreutils}/bin/date +%s)"
    result="$(${pkgs.jq}/bin/jq -r --argjson now "$now" \
      'if (.state == "running") and ($now > (.deadline_epoch // 0)) then "stuck" else "ok" end' \
      "$receipt" 2>/dev/null)" || exit 3
    [ "$result" = stuck ] && exit 1
    exit 0
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
    # --preserve-snapshots, so snapshots are deleted only by Borg drain jobs
    # after the matching archive exists.

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

  '';

in
{
  config = lib.mkMerge [
    {
      sinnix.runtime.surfaces = {
        btrbk = {
          unit = "btrbk.service";
          resourceClass = "backup-maintenance";
        };
        btrbk-timer = {
          unit = "btrbk.timer";
          kind = "timer";
          resourceClass = "backup-maintenance";
          observe = {
            enable = true;
            restartable = false;
          };
        };
        borgbackup-job-persist = {
          unit = "borgbackup-job-persist.service";
          resourceClass = "backup-maintenance";
          observe = {
            enable = true;
            restartable = false;
          };
          captures = [
            {
              name = "borg-persist-archive";
              path = "${borgDrainStateRoot}/persist.last-success";
              eventDriven = true;
              # Same budget the retired borgbackup-status "persist"
              # archive_freshness check used: 3x the 4h drain floor.
              staleAfterSeconds = borgArchiveMaxAgeSec;
            }
          ];
        };
        borgbackup-job-realm = {
          unit = "borgbackup-job-realm.service";
          resourceClass = "backup-maintenance";
          observe = {
            enable = true;
            restartable = false;
          };
          captures = [
            {
              name = "borg-realm-archive";
              path = "${borgDrainStateRoot}/realm.last-success";
              eventDriven = true;
              staleAfterSeconds = borgArchiveMaxAgeSec;
            }
            {
              # The btrbk snapshot queue (persist AND realm, both checked by
              # the probe below) has no owning unit of its own -- it is a
              # property of the drain state this job and borgbackup-job-persist
              # share. Landed here rather than split across both surfaces,
              # since realm is the heavier of the two volumes and the one that
              # has actually stalled before (drains contend for one global
              # Borg lock, so a stall on either queue means the same lock
              # contention regardless of which volume's job reports it).
              #
              # `path` is deliberately the small drain-state directory (a
              # handful of marker/stamp files), NOT the snapshot directories
              # themselves: those are full btrfs subvolume trees (potentially
              # many GB / millions of files each), and the sweep's
              # newest_mtime does a plain os.walk over every capture path on a
              # 60s clock -- pointing it at a live snapshot tree would re-stat
              # the entire /realm or /persist dataset every minute. No
              # staleAfterSeconds: the drain-state directory always holds a
              # file once the first drain has ever succeeded, so plain
              # presence is enough; the real freshness question here is
              # answered by the probe below, not by this path's mtime.
              name = "borg-snapshot-queue";
              path = borgDrainStateRoot;
              eventDriven = true;
              livenessProbe = {
                command = mkSnapshotQueueProbeScript;
                timeoutSeconds = 15;
              };
            }
          ];
        };
        borgbackup-job-sinex-blobs = {
          unit = "borgbackup-job-sinex-blobs.service";
          resourceClass = "backup-maintenance";
          observe = {
            enable = true;
            restartable = false;
          };
          captures = [
            {
              name = "borg-sinex-blobs-archive";
              path = "${borgDrainStateRoot}/sinex-blobs.last-success";
              eventDriven = true;
              # sinex-blobs runs on its own daily 05:40 timer, not the 4h-floor
              # persist/realm drain cadence, so it keeps the daily budget the
              # retired borgbackup-status check used for it (3x cadence).
              staleAfterSeconds = borgDailyArchiveMaxAgeSec;
            }
          ];
        };
        polylogue-sqlite-backup = {
          unit = "polylogue-sqlite-backup.service";
          resourceClass = "backup-maintenance";
          observe.enable = true;
        };
        polylogue-sqlite-backup-timer = {
          unit = "polylogue-sqlite-backup.timer";
          kind = "timer";
          resourceClass = "backup-maintenance";
        };
        borgbackup-job-polylogue-state = {
          unit = "borgbackup-job-polylogue-state.service";
          resourceClass = "backup-maintenance";
          observe = {
            enable = true;
            restartable = false;
          };
          captures = [
            {
              name = "borg-polylogue-state-archive";
              path = "${borgDrainStateRoot}/polylogue-state.last-success";
              eventDriven = true;
              # Daily timer, same budget convention as sinex-blobs: 3x cadence.
              staleAfterSeconds = borgDailyArchiveMaxAgeSec;
            }
          ];
        };
        borgbackup-job-machine-telemetry-dumps = {
          unit = "borgbackup-job-machine-telemetry-dumps.service";
          resourceClass = "backup-maintenance";
          observe = {
            enable = true;
            restartable = false;
          };
          captures = [
            {
              name = "borg-machine-telemetry-dumps";
              path = machineTelemetryBackupMarker;
              eventDriven = true;
              # The direct-path job runs daily; a 3x cadence budget leaves
              # room for one delayed HDD run without masking a stalled job.
              staleAfterSeconds = borgDailyArchiveMaxAgeSec;
            }
          ];
        };
        borgbackup-verify = {
          unit = "borgbackup-verify.service";
          resourceClass = "backup-maintenance";
          observe = {
            enable = true;
            restartable = false;
          };
          captures = [
            {
              name = "borg-drill";
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
              # Same 3x-weekly-cadence budget as the drill lane above: the
              # receipt only updates on a verify run.
              staleAfterSeconds = 1814400;
              # Staleness alone reads a run stuck mid-check (state=="running"
              # well past its own deadline_epoch, the case the retired
              # borgbackup-status integrity-state machinery covered) as merely
              # "not yet stale" until the weekly budget itself expires --
              # days later. The probe answers that narrower question directly.
              # completed/failed states exit 0 here: a failed run already
              # fires OnFailure from the unit itself.
              livenessProbe = {
                command = mkIntegrityStuckProbeScript;
                timeoutSeconds = 10;
              };
            }
          ];
        };
        borgbackup-maintenance = {
          unit = "borgbackup-maintenance.service";
          resourceClass = "backup-maintenance";
          observe = {
            enable = true;
            restartable = false;
          };
        };
        btrfs-metadata-image-backup = {
          unit = "btrfs-metadata-image-backup.service";
          resourceClass = "backup-maintenance";
          # Was unset (default false), which meant the auto-attached OnFailure
          # hook (modules/runtime.nix, gated on observe.enable) was NEVER
          # wired for this unit -- it failed with status=1/FAILURE on
          # 2026-08-16 and nothing surfaced it. Not a restart candidate: a
          # failed capture is retried by the retry loop inside the script
          # itself and by next Sunday's timer, not by systemd Restart=.
          observe = {
            enable = true;
            restartable = false;
          };
        };
        borgbackup-root-snapshots = {
          unit = "borgbackup-root-snapshots.service";
          resourceClass = "backup-maintenance";
        };
        sinnix-borg-beads-drill = {
          unit = "sinnix-borg-beads-drill.service";
          resourceClass = "backup-maintenance";
          captures = [
            {
              name = "borg-beads-drill";
              path = sinexBeadsDrillLog;
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

      # btrbk configuration
      environment.etc."btrbk/btrbk.conf".text = btrbkConfig;
    }

    # ─── Borg Snapshot Drainers ───
    #
    # btrbk is the producer. Borg is the durability gate. Local snapshots are
    # never deleted by btrbk rotation; a snapshot leaves disk only after this
    # drain has either found or created the matching Borg archive.
    #
    # Backups are scheduled bulk I/O and must stay below interactive work;
    # unthrottled they saturate /realm enough to visibly stall the desktop.
    #
    # The drain timers are RETRY granularity, not work cadence: how often a
    # drain actually copies anything is set by borgDrainMinIntervalSec (4h),
    # and a wake inside that window exits after one stat without touching the
    # Borg lock. What the timer period buys is recovery margin. A drain that
    # loses the global lock race skips outright and waits for its next wake,
    # while the health budget (borgArchiveMaxAgeSec / borgSnapshotQueueMaxAgeSec,
    # 6h) starts counting from the last SUCCESS -- so the 4h floor leaves only
    # ~2h of slack. At the old hourly period two consecutive lock races spent
    # most of it and a third breached the budget; at 20 minutes, six retries
    # fit in the same slack. Both stay off btrbk's :00/:30 wakes and off each
    # other so the two drains never race for the lock they now rarely take.
    (mkBackupJob "borgbackup-job-persist" {
      description = "Drain /persist btrbk snapshots into Borg";
      unit = {
        after = [
          "persist.mount"
          outerRealmMountUnit
        ];
        requires = [
          "persist.mount"
          outerRealmMountUnit
        ];
      };
      serviceConfig.TimeoutStopSec = "15s";
      path = with pkgs; [
        borgbackup
        btrfs-progs
        coreutils
        findutils
        gnugrep
        procps
        util-linux
      ];
      script = mkSnapshotDrainScript {
        label = "persist";
        repo = borgRepoPersist;
        repoPath = borgRepoPersistPath;
        snapshotDir = persistSnapshots;
        snapshotGlob = "persist.*";
        bindTarget = borgPersistSnapshotBind;
        archivePrefix = "persist";
        minIntervalSec = borgDrainMinIntervalSec;
        exclude = persistExcludes;
      };
      timer = {
        onCalendar = "*-*-* *:05,25,45:00";
        persistent = false;
      };
    })

    (mkBackupJob "borgbackup-job-realm" {
      description = "Drain /realm btrbk snapshots into Borg";
      unit = {
        after = [
          "realm.mount"
          outerRealmMountUnit
        ];
        requires = [
          "realm.mount"
          outerRealmMountUnit
        ];
      };
      serviceConfig.TimeoutStopSec = "15s";
      path = with pkgs; [
        borgbackup
        btrfs-progs
        coreutils
        findutils
        gnugrep
        procps
        util-linux
      ];
      script = mkSnapshotDrainScript {
        label = "realm";
        repo = borgRepoRealm;
        repoPath = borgRepoRealmPath;
        snapshotDir = realmSnapshots;
        snapshotGlob = "realm.*";
        bindTarget = borgRealmSnapshotBind;
        archivePrefix = "realm";
        minIntervalSec = borgDrainMinIntervalSec;
        exclude = realmExcludes;
      };
      timer = {
        onCalendar = "*-*-* *:15,35,55:00";
        persistent = false;
      };
    })

    # ─── Sinex blob-repository Borg job ───
    # A CAS lives outside the /realm snapshot stream, so Borg reads the live
    # evaluated content-store path. Immutable objects make this safe without a
    # snapshot; `RequiresMountsFor` keeps the source mount authoritative. The
    # guard covers service AND timer: a timer whose service does not exist is
    # a failed start, not a backup.
    (lib.mkIf (sinexBlobRepositoryPath != "") (
      mkBackupJob "borgbackup-job-sinex-blobs" {
        description = "Back up sinex blob repository into Borg";
        unit = {
          after = [
            "persist.mount"
            outerRealmMountUnit
          ];
          requires = [
            "persist.mount"
            outerRealmMountUnit
          ];
          unitConfig.RequiresMountsFor = [ sinexBlobRepositoryPath ];
        };
        serviceConfig.TimeoutStopSec = "15s";
        path = with pkgs; [
          borgbackup
          coreutils
          gnugrep
          procps
          util-linux
        ];
        timer = {
          onCalendar = "*-*-* 05:40:00";
          randomizedDelaySec = "10min";
          persistent = true;
        };
        script = ''
          set -euo pipefail
          ${mkBorgCommonScript borgRepoSinexBlobs borgRepoSinexBlobsPath}

          install -d -m 0700 -o root -g root ${lib.escapeShellArg borgRepoSinexBlobsPath}
          recover_stale_borg_locks

          if [ ! -e ${lib.escapeShellArg "${borgRepoSinexBlobsPath}/config"} ]; then
            with_borg_lock borg init --encryption repokey-blake2 "$BORG_REPO"
          fi

          archive_name="sinex-blobs-$(date -u +%Y%m%dT%H%M%SZ)"
          with_borg_lock borg create \
            --compression auto,zstd,1 \
            --lock-wait ${toString borgLockWaitSec} \
            "::$archive_name" \
            ${lib.escapeShellArg sinexBlobRepositoryPath}
          echo "sinex blob backup complete: $archive_name"

          # The borg-sinex-blobs-archive capture lane (this surface's
          # captures, above) gates freshness off this marker, same convention
          # as the btrbk drain jobs' "$label.last-success" (mkSnapshotDrainScript
          # above) -- without it, sinex-blobs had zero freshness gating despite
          # being on a daily timer just like persist/realm are on their 4h floor.
          install -d -m 0755 -o root -g root ${lib.escapeShellArg borgDrainStateRoot}
          marker=${lib.escapeShellArg "${borgDrainStateRoot}/sinex-blobs.last-success"}
          {
            printf 'archive=%s\n' "$archive_name"
            printf 'epoch=%s\n' "$(date +%s)"
          } > "$marker.tmp"
          mv "$marker.tmp" "$marker"
        '';
      }
    ))

    # ─── Polylogue nested-subvolume coverage (sinnix-3pvd) ───
    #
    # Two jobs cover state/polylogue, split the same way sinex is split
    # between sinex-postgres-dump (logical dump of the live DB) and
    # borgbackup-job-sinex-blobs (direct-path borg of the immutable CAS):
    # sqlite-safe dumps for the live databases, and a direct-path borg job
    # for everything else (blob/ CAS, hooks/, browser-capture/, inbox/, and
    # the retired/historical db siblings that are no longer written).
    (mkBackupJob "polylogue-sqlite-backup" {
      description = "Back up Polylogue SQLite databases";
      unit = {
        after = [
          "realm.mount"
        ];
        requires = [
          "realm.mount"
        ];
        unitConfig.RequiresMountsFor = [
          polylogueStateRoot
          polylogueBackupRoot
        ];
      };
      user = username;
      serviceConfig = {
        Group = "users";
        TimeoutStartSec = "30min";
      };
      path = [
        pkgs.coreutils
        pkgs.findutils
        pkgs.gawk
        scriptPkgs.sinnix-sqlite-backup
      ];
      timer = {
        onCalendar = "*-*-* 04:15:00";
        randomizedDelaySec = "20min";
        persistent = true;
      };
      script = ''
        set -euo pipefail

        umask 077
        install -d -m 0700 -o ${lib.escapeShellArg username} -g users ${lib.escapeShellArg polylogueBackupRoot}

        stamp="$(date -u +%Y%m%dT%H%M%SZ)"

        for name in ${lib.escapeShellArgs polylogueDbNames}; do
          src=${lib.escapeShellArg polylogueStateRoot}/"$name"
          [ -e "$src" ] || continue
          base="''${name%.db}"
          final=${lib.escapeShellArg polylogueBackupRoot}/"$base-$stamp".db.zst

          sinnix-sqlite-backup "$src" "$final"

          # Retention is a judgment call, not a measurement: polylogued is
          # parked (near-zero churn today), and the largest db (source.db,
          # 1.8G raw) compresses to a fraction of that, so 5 generations per
          # db is cheap. Widen once real write-rate data exists after the
          # daemon un-parks.
          find ${lib.escapeShellArg polylogueBackupRoot} \
            -maxdepth 1 \
            -type f \
            -name "$base"'-*.db.zst' \
            -printf '%T@ %p\n' \
            | sort -rn \
            | awk 'NR > 5 { print substr($0, index($0, $2)) }' \
            | xargs -r rm -f
        done
      '';
    })

    # Direct-path borg over the live state root, same reasoning as
    # borgbackup-job-sinex-blobs: excluded files are the live databases
    # (torn-copy risk, covered by the dump job above instead); everything
    # else here is either immutable CAS or currently-static, so a plain
    # file-level copy is safe without a btrfs snapshot.
    (mkBackupJob "borgbackup-job-polylogue-state" {
      description = "Back up Polylogue state (blob CAS and non-live files) into Borg";
      unit = {
        after = [
          "realm.mount"
          outerRealmMountUnit
        ];
        requires = [
          "realm.mount"
          outerRealmMountUnit
        ];
        unitConfig.RequiresMountsFor = [ polylogueStateRoot ];
      };
      serviceConfig.TimeoutStopSec = "15s";
      path = with pkgs; [
        borgbackup
        coreutils
        gnugrep
        procps
        util-linux
      ];
      timer = {
        onCalendar = "*-*-* 05:55:00";
        randomizedDelaySec = "10min";
        persistent = true;
      };
      script = ''
        set -euo pipefail
        ${mkBorgCommonScript borgRepoPolylogueState borgRepoPolylogueStatePath}

        install -d -m 0700 -o root -g root ${lib.escapeShellArg borgRepoPolylogueStatePath}
        recover_stale_borg_locks

        if [ ! -e ${lib.escapeShellArg "${borgRepoPolylogueStatePath}/config"} ]; then
          with_borg_lock borg init --encryption repokey-blake2 "$BORG_REPO"
        fi

        archive_name="polylogue-state-$(date -u +%Y%m%dT%H%M%SZ)"
        with_borg_lock borg create \
          --compression auto,zstd,1 \
          --lock-wait ${toString borgLockWaitSec} \
          ${mkBorgExcludeArgs polylogueStateRoot polylogueDbExcludes} \
          "::$archive_name" \
          ${lib.escapeShellArg polylogueStateRoot}
        echo "polylogue state backup complete: $archive_name"

        install -d -m 0755 -o root -g root ${lib.escapeShellArg borgDrainStateRoot}
        marker=${lib.escapeShellArg "${borgDrainStateRoot}/polylogue-state.last-success"}
        {
          printf 'archive=%s\n' "$archive_name"
          printf 'epoch=%s\n' "$(date +%s)"
        } > "$marker.tmp"
        mv "$marker.tmp" "$marker"
      '';
    })

    # Direct-path Borg coverage for the machine telemetry SQLite dump stream.
    # The live database is dumped by machine-telemetry-sqlite-backup; this job
    # archives every resulting compressed dump without deleting or pruning any
    # source snapshot. It also restores one archived dump through stdout and
    # runs zstd's frame test before publishing the freshness marker, so a
    # successful marker means both archive creation and a real restore probe
    # succeeded.
    (mkBackupJob "borgbackup-job-machine-telemetry-dumps" {
      description = "Back up and restore-check machine telemetry SQLite dumps";
      unit = {
        after = [
          "realm.mount"
          outerRealmMountUnit
        ];
        requires = [
          "realm.mount"
          outerRealmMountUnit
        ];
        unitConfig.RequiresMountsFor = [ machineTelemetryBackupRoot ];
      };
      serviceConfig = {
        # This is a Type=oneshot service, so TimeoutStartSec bounds the full
        # Borg process lifetime. The dump set can be large on the HDD; keep
        # the measured 12-hour allowance used by the weekly restore path.
        TimeoutStartSec = "12h";
        TimeoutStopSec = "15s";
      };
      environment = {
        BORG_PASSCOMMAND = "${pkgs.coreutils}/bin/cat ${borgPassphrasePath}";
        BORG_CACHE_DIR = borgCacheDir;
      };
      path = with pkgs; [
        borgbackup
        coreutils
        findutils
        gnugrep
        jq
        procps
        util-linux
        zstd
      ];
      timer = {
        onCalendar = "*-*-* 06:15:00";
        randomizedDelaySec = "30min";
        persistent = true;
      };
      script = ''
        set -euo pipefail

        ${mkBorgCommonScript borgRepoRealm borgRepoRealmPath}
        install -d -m 0755 -o root -g root ${lib.escapeShellArg borgDrainStateRoot}
        recover_stale_borg_locks
        if [ ! -e ${lib.escapeShellArg "${borgRepoRealmPath}/config"} ]; then
          with_borg_lock borg init --encryption repokey-blake2 "$BORG_REPO"
        fi

        source_count="$(${pkgs.findutils}/bin/find ${lib.escapeShellArg machineTelemetryBackupRoot} -maxdepth 1 -type f -name 'telemetry-*.sqlite.zst' -printf 'x\n' | ${pkgs.coreutils}/bin/wc -l)"
        if [ "$source_count" -eq 0 ]; then
          echo "no machine telemetry SQLite dump is available; refusing a false-success marker" >&2
          exit 1
        fi

        archive_name="machine-telemetry-dumps-$(date -u +%Y%m%dT%H%M%SZ)"
        with_borg_lock borg create \
          --compression auto,zstd,1 \
          --lock-wait ${toString borgLockWaitSec} \
          --exclude-caches \
          --exclude-if-present .nobackup \
          "::$archive_name" \
          ${lib.escapeShellArg "${machineTelemetryBackupRoot}/./"}

        # `borg list --short` prints directories without a trailing slash, so
        # the archive root `.` would be sampled and its stdout extract is
        # empty. Probe the newest dump by name.
        sample_path="$(with_borg_lock borg list --short "::$archive_name" | ${pkgs.gnugrep}/bin/grep -E '\.sqlite\.zst$' | ${pkgs.coreutils}/bin/sort | ${pkgs.coreutils}/bin/tail -n 1)"
        if [ -z "$sample_path" ]; then
          echo "machine telemetry Borg archive contains no dump file" >&2
          exit 1
        fi
        with_borg_lock borg extract --stdout "::$archive_name" "$sample_path" | ${pkgs.zstd}/bin/zstd -t

        {
          printf 'archive=%s\n' "$archive_name"
          printf 'source_count=%s\n' "$source_count"
          printf 'sample_path=%s\n' "$sample_path"
          printf 'epoch=%s\n' "$(date +%s)"
        } > ${lib.escapeShellArg machineTelemetryBackupMarker}.tmp
        mv ${lib.escapeShellArg machineTelemetryBackupMarker}.tmp ${lib.escapeShellArg machineTelemetryBackupMarker}
      '';
    })

    {
      assertions =
        lib.optional (sinexBlobRepositoryPath != "") {
          assertion = lib.hasInfix sinexBlobRepositoryPath config.systemd.services.borgbackup-job-sinex-blobs.script;
          message = "Sinex CAS Borg backup must archive services.sinex.storage.blob.repositoryPath";
        }
        ++ [
          {
            assertion = lib.all (exclude: !realmExcludeMatchesProtectedPath exclude) realmExcludes;
            message = "The /realm Borg backup must not exclude Sinex .beads/dolt or .beads/issues.jsonl";
          }
        ];
    }

    # Weekly integrity check — verify repo metadata and detect bit rot on the
    # HDD, then run the bounded restore drill in the same window. Merged into
    # one unit (was borgbackup-check.service + sinnix-borg-drill.service,
    # sinnix-borg-drill.timer Wed 04:00 retired) so the two weekly borg-heavy
    # jobs no longer contend for the HDD on separate schedules.
    (mkBackupJob "borgbackup-verify" {
      description = "Borg backup integrity check and bounded restore drill";
      serviceConfig = {
        TimeoutStopSec = "15s";
        # Repository checks are capped at 3h (1800+7200+1800s) by their own
        # --max-duration budgets; the drill's borg check --verify-data on a
        # multi-GB archive can take tens of minutes more on HDD. 12h total,
        # matching the retired sinnix-borg-drill.service's own allowance.
        TimeoutStartSec = "12h";
      };
      environment = {
        BORG_PASSCOMMAND = "${pkgs.coreutils}/bin/cat ${borgPassphrasePath}";
        BORG_CACHE_DIR = borgCacheDir;
      };
      timer = {
        onCalendar = "Sun 06:17:00";
        persistent = false;
      };
      path = with pkgs; [
        borgbackup
        coreutils
        findutils
        gnugrep
        jq
        procps
        util-linux
      ];
      script = ''
        set -euo pipefail

        ${mkBorgCommonScript borgRepoPersist borgRepoPersistPath}
        acquire_borg_global_lock_or_skip "Borg repository check"
        run_id="''${INVOCATION_ID:-borg-check-$(date +%s)}"
        write_integrity_receipt() {
          state="$1"
          install -d -m 0755 ${lib.escapeShellArg borgDrainStateRoot}
          jq -cn \
            --arg operation_kind integrity_check \
            --arg run_id "$run_id" \
            --argjson expected_jobs '["persist","realm","sinex-blobs"]' \
            --argjson start_epoch "$start_epoch" \
            --argjson deadline_epoch "$deadline_epoch" \
            --arg state "$state" \
            --arg ts "$(date -Iseconds)" \
            '{operation_kind:$operation_kind,run_id:$run_id,expected_jobs:$expected_jobs,start_epoch:$start_epoch,deadline_epoch:$deadline_epoch,state:$state,updated_at:$ts}' \
            > ${lib.escapeShellArg borgIntegrityReceipt}.tmp
          mv ${lib.escapeShellArg borgIntegrityReceipt}.tmp ${lib.escapeShellArg borgIntegrityReceipt}
        }
        start_epoch="$(date +%s)"
        deadline_epoch=$((start_epoch + 3 * 3600))
        receipt_failure_trap() {
          rc="$?"
          write_integrity_receipt failed
          exit "$rc"
        }
        # Armed BEFORE the first receipt write: when jq was missing from this
        # unit's path, the "running" write died with 127 before the trap
        # existed, so no receipt was written at all -- not even a failed one.
        # The freshness check reading this receipt then reported it missing
        # and went red for two weeks while the backups themselves were fine.
        # The trap only ever writes "failed" -- "completed" is
        # written explicitly once the repository checks below succeed, so a
        # later drill failure (which is a separate concern, not part of
        # expected_jobs) does not retroactively flip a completed integrity
        # check back to failed.
        trap receipt_failure_trap EXIT
        write_integrity_receipt running
        recover_stale_borg_locks
        ${mkBorgCommonScript borgRepoRealm borgRepoRealmPath}
        recover_stale_borg_locks

        # --max-duration makes the repository check INCREMENTAL: each run
        # verifies segments for at most the budget and records progress in
        # the repo, so successive weekly runs cycle through the full
        # repository without ever monopolizing the repo lock for a whole day
        # and starving the hourly drains.
        ${pkgs.borgbackup}/bin/borg check --repository-only --max-duration 1800 ${borgRepoPersist}
        ${pkgs.borgbackup}/bin/borg check --repository-only --max-duration 7200 ${borgRepoRealm}
        ${pkgs.borgbackup}/bin/borg check --repository-only --max-duration 1800 ${borgRepoSinexBlobs}

        trap - EXIT
        write_integrity_receipt completed

        # Bounded restore drill (was sinnix-borg-drill.service, its own
        # weekly timer). Runs the same packaged script the manual
        # `sinnix borg-drill [--verify-data]` verb uses, so borg_drill.jsonl
        # receipts land exactly as before. The repository checks above
        # release the global Borg lock here (by closing fd 9) before
        # invoking it: the drill script does its own `exec 9>...; flock -n`
        # in a fresh process against the same lock file, which would
        # otherwise always see the lock as already held by this script and
        # skip -- a re-entrant flock is per-open-file-description, not
        # per-process-tree.
        exec 9>&-
        ${scriptPkgs.sinnix-borg-drill}/bin/sinnix-borg-drill
      '';
    })

    (mkBackupJob "borgbackup-maintenance" {
      description = "Prune and compact Borg backup repositories";
      unit = {
        after = [
          outerRealmMountUnit
        ];
        requires = [
          outerRealmMountUnit
        ];
      };
      serviceConfig.TimeoutStopSec = "15s";
      environment = {
        BORG_PASSCOMMAND = "${pkgs.coreutils}/bin/cat ${borgPassphrasePath}";
        BORG_CACHE_DIR = borgCacheDir;
      };
      path = with pkgs; [
        borgbackup
        coreutils
        findutils
        gnugrep
        procps
        util-linux
      ];
      timer = {
        onCalendar = "*-*-* 04:50:00";
        persistent = false;
        randomizedDelaySec = "45min";
      };
      script = ''
        set -euo pipefail

        export BORG_CACHE_DIR=${lib.escapeShellArg borgCacheDir}

        with_borg_lock() {
          if [ "''${SINNIX_BORG_GLOBAL_LOCK_HELD:-0}" = 1 ]; then
            "$@"
          else
            flock ${lib.escapeShellArg borgGlobalLock} "$@"
          fi
        }

        acquire_borg_global_lock_or_skip() {
          if [ "''${SINNIX_BORG_GLOBAL_LOCK_HELD:-0}" = 1 ]; then
            return
          fi
          reason="$1"
          exec 9>${lib.escapeShellArg borgGlobalLock}
          if ! flock -n 9; then
            echo "Another Borg operation is active; skipping $reason"
            exit 0
          fi
          export SINNIX_BORG_GLOBAL_LOCK_HELD=1
        }

        recover_stale_borg_locks() {
          repo="$1"
          repo_path="''${repo#file://}"

          stale_lock="$(
            find "$repo_path" \
              -maxdepth 2 -type d -name lock.exclusive \
              -mmin +${toString borgStaleLockMinutes} -print -quit 2>/dev/null || true
          )"
          if [ -z "$stale_lock" ]; then
            if ! find ${lib.escapeShellArg borgCacheDir} \
              -maxdepth 2 -type d -name lock.exclusive \
              -mmin +${toString borgStaleLockMinutes} -print -quit 2>/dev/null | grep -q .; then
              return
            fi
            stale_lock="stale Borg cache lock"
          fi

          if pgrep -x borg >/dev/null 2>&1; then
            echo "Stale-looking Borg lock remains for $repo, but a Borg process is alive; refusing break-lock" >&2
            return
          fi

          echo "Breaking stale Borg lock for $repo: $stale_lock" >&2
          with_borg_lock borg break-lock "$repo"
        }

        maintain_repo() {
          repo="$1"
          if [ ! -e "''${repo#file://}/config" ]; then
            echo "Skipping uninitialized repo $repo"
            return
          fi

          acquire_borg_global_lock_or_skip "Borg maintenance"
          recover_stale_borg_locks "$repo"
          with_borg_lock borg prune --lock-wait ${toString borgLockWaitSec} ${mkBorgRetentionArgs} "$repo"
          with_borg_lock borg compact --lock-wait ${toString borgLockWaitSec} "$repo"
        }

        maintain_repo ${lib.escapeShellArg borgRepoPersist}
        maintain_repo ${lib.escapeShellArg borgRepoRealm}
        maintain_repo ${lib.escapeShellArg borgRepoSinexBlobs}
        maintain_repo ${lib.escapeShellArg borgRepoRootSnapshots}
        maintain_repo ${lib.escapeShellArg borgRepoPolylogueState}
      '';
    })

    # Borg is file-level recovery. Keep compact Btrfs metadata images off the
    # source filesystems so a future tree/chunk/extent repair has native
    # metadata evidence instead of only a file archive.
    (mkBackupJob "btrfs-metadata-image-backup" {
      description = "Capture Btrfs metadata images for realm and persist";
      unit = {
        after = [
          "persist.mount"
          "realm.mount"
          outerRealmMountUnit
        ];
        requires = [
          "persist.mount"
          "realm.mount"
          outerRealmMountUnit
        ];
      };
      # backup-maintenance sizes MemoryHigh=2G around borg, but a btrfs-image
      # walk of the root filesystem peaked at 2.2G on a run that SUCCEEDED
      # (measured 2026-08-18), so the class default sits below this job's
      # working set and every attempt spends its whole length in cgroup
      # reclaim. Right-sized on the unit rather than in the class, which no
      # other backup job needs raised. Deliberately NOT claimed as the cause
      # of the persist failures: seven controlled captures that day produced
      # both successes and failures with and against the cap, so the transid
      # race below is genuinely probabilistic. This removes one pressure
      # source that is otherwise present on every single run.
      serviceConfig = {
        TimeoutStopSec = "15s";
        MemoryHigh = "6G";
        MemoryMax = "8G";
      };
      path = with pkgs; [
        btrfs-progs
        coreutils
        findutils
      ];
      timer = {
        onCalendar = "Sun 00:12:00";
        persistent = false;
        randomizedDelaySec = "2h";
      };
      script = ''
        set -euo pipefail

        stamp="$(date -u +%Y%m%dT%H%M%SZ)"
        install -d -m 0700 -o root -g root "${btrfsImageRoot}"

        # btrfs-image writes to "$out.tmp" and renames only on success, and
        # the 30-day prune below matches finished images only, so a dead run
        # leaves multi-GB orphans indefinitely.
        find "${btrfsImageRoot}" -type f -name '*.btrfs-image.tmp' -mtime +1 -delete

        # btrfs-image walks a MOUNTED, actively-written filesystem: there is
        # no consistent-view mode for one, and a tree block whose generation
        # advances between the parent-pointer read and the child read aborts
        # the walk with "parent transid verify failed" / "child eb corrupted".
        # That is a race against concurrent writes, not on-disk damage (the
        # device error counters stay at zero throughout), so it is worth
        # retrying rather than failing the run -- a quieter moment succeeds.
        #
        # A snapshot cannot route around this (sinnix-0dyg): btrfs-image's
        # own usage text is "source is the btrfs device" -- it reads the
        # whole filesystem's chunk/root/extent trees off the block device,
        # not a mounted path or a subvolume, so a read-only snapshot of
        # persist does not exist as an addressable source for it. The race
        # is against the SHARED device, and a snapshot subvolume lives on
        # that same device.
        #
        # Confirmed 2026-08-16 that off-peak scheduling alone is not
        # sufficient: the SCHEDULED Sun 00:12 run (not the ad-hoc daytime
        # test run in this bead's earlier notes) produced realm-20260815T233745Z
        # but no matching persist image -- both labels share one $stamp, so
        # persist genuinely failed inside that same quiet-hour invocation.
        # Telemetry for that window (block_device_sample) rules out raw
        # write volume as the discriminator: nvme0n1p3 (realm) saw ~6x
        # persist's write rate in the same window and still succeeded, so
        # persist's smaller size buys it nothing here. The mitigation below
        # is retry-shape tuning, per the bead's own fallback: capture persist
        # FIRST (while the window is freshest, before realm's variable-length
        # capture pushes persist's attempts toward the next btrbk :00/:30
        # snapshot-creation boundary -- a bigger single generation-bump than
        # steady small-file writes), and widen the retry budget.
        capture_image() {
          label="$1"
          device="$2"
          out="${btrfsImageRoot}/$label-$stamp.btrfs-image"
          tmp="$out.tmp"
          attempt=1

          while [ "$attempt" -le 5 ]; do
            rm -f "$tmp"
            if btrfs-image -c 9 "$device" "$tmp"; then
              # errexit is disabled inside a function whose caller is an `if`
              # condition, so nothing from here to the rename is covered by
              # `set -e`: a chmod or mv that failed (full or read-only
              # /outer-realm) used to fall through to `return 0` and the unit
              # reported a capture that was not on disk. Every step is checked
              # by hand, and the image is only "captured" once it is readable
              # at its final name.
              if chmod 0600 "$tmp" && mv -- "$tmp" "$out"; then
                size="$(stat -c %s "$out" 2>/dev/null || echo 0)"
                if [ "$size" -ge ${toString btrfsImageMinBytes} ]; then
                  echo "btrfs-metadata-image-backup: $label captured $label-$stamp.btrfs-image ($size bytes)"
                  return 0
                fi
                echo "btrfs-metadata-image-backup: $label produced a degenerate image ($size bytes, floor ${toString btrfsImageMinBytes})" >&2
                rm -f -- "$out"
              else
                echo "btrfs-metadata-image-backup: $label could not be published to $out" >&2
              fi
            fi
            echo "btrfs-metadata-image-backup: $label attempt $attempt failed (live-filesystem race or real error)" >&2
            attempt=$((attempt + 1))
            if [ "$attempt" -gt 5 ]; then
              break
            fi
            # Deliberately not a fixed interval: a constant 60s could
            # resonate with another periodic writer on the same cadence.
            # 45/90/135/180s spreads retries across a wider span of the
            # window instead.
            sleep $((45 * (attempt - 1)))
          done

          rm -f "$tmp"
          echo "btrfs-metadata-image-backup: $label failed after 5 attempts" >&2
          return 1
        }

        # Retention is a consequence of a successful capture, never a
        # scheduled event of its own. The prune used to be one unconditional
        # sweep of the whole directory at the end of the run, which meant a
        # label that had just failed still had its history aged out: persist
        # last captured 2026-08-01 while its 2026-07-18 predecessor was
        # already past the age rule, so the next few runs would have deleted
        # persist's images one at a time while every capture kept failing,
        # ending at zero images for a filesystem the unit exists to protect.
        # A producer does not delete its own last evidence, so the sweep is
        # per-label, gated on that label landing a fresh image in THIS run,
        # and floored at the newest ${toString btrfsImageKeepMinimum}
        # regardless of age.
        prune_label() {
          label="$1"
          kept=0
          # Names carry a basic-format UTC stamp, so a reverse lexical sort is
          # a newest-first chronological sort.
          for name in $(find "${btrfsImageRoot}" -maxdepth 1 -type f \
            -name "$label-*.btrfs-image" -printf '%f\n' | sort -r); do
            kept=$((kept + 1))
            if [ "$kept" -le ${toString btrfsImageKeepMinimum} ]; then
              continue
            fi
            find "${btrfsImageRoot}/$name" -maxdepth 0 \
              -mtime +${toString btrfsImageRetentionDays} -delete
          done
        }

        # Per-label accounting: a combined exit code hides which target is
        # actually broken. persist goes first -- see the comment above.
        rc=0
        if capture_image persist /dev/disk/by-uuid/f4782d9f-aabe-408e-b18b-2f2baa9e9a02; then
          prune_label persist
        else
          rc=1
        fi
        if capture_image realm /dev/disk/by-uuid/43701cf7-7880-4e0c-9725-b6e12d91898a; then
          prune_label realm
        else
          rc=1
        fi

        exit "$rc"
      '';
    })

    {
      system.activationScripts.borgRepositoryDirectories.text = ''
        ${pkgs.coreutils}/bin/install -d -m 0750 -o root -g users ${borgRepoRoot}
        ${pkgs.coreutils}/bin/install -d -m 0700 -o root -g root ${borgRepoPersistPath}
        ${pkgs.coreutils}/bin/install -d -m 0700 -o root -g root ${borgRepoRealmPath}
        ${pkgs.coreutils}/bin/install -d -m 0700 -o root -g root ${borgRepoRootSnapshotsPath}
        ${pkgs.coreutils}/bin/install -d -m 0700 -o root -g root ${borgRepoSinexBlobsPath}
        ${pkgs.coreutils}/bin/install -d -m 0700 -o root -g root ${borgRepoPolylogueStatePath}
        ${pkgs.coreutils}/bin/install -d -m 0700 -o root -g root ${btrfsImageRoot}
      '';

      # Borg chunk cache must survive reboots. / is ephemeral, so the default
      # ~/.cache/borg is lost on every boot, forcing a full re-read + re-chunk
      # of every file (616GB read for 2.4GB written — a 256:1 waste).
      # Persist it under /persist so backups are truly incremental.
      systemd.tmpfiles.rules = lib.mkAfter [
        "d ${realmSnapshots} 0750 root users -"
        # polylogue-sqlite-backup runs as the operator while db-dumps' parent
        # is root:root -- pre-create its subdir or the first run dies on mkdir
        # (exactly how it announced itself, 2026-08-18).
        "d ${polylogueBackupRoot} 0700 sinity users -"
        "d ${persistSnapshots} 0750 root users -"
        "d ${borgSnapshotBindRoot} 0700 root root -"
        "d ${borgPersistSnapshotBind} 0700 root root -"
        "d ${borgRealmSnapshotBind} 0700 root root -"
        "d ${borgRepoRoot} 0750 root users -"
        "d ${borgRepoRootSnapshotsPath} 0700 root root -"
        "d ${btrfsImageRoot} 0700 root root -"
        "d ${borgCacheDir} 0700 root root -"
        "d ${borgDrainStateRoot} 0700 root root -"
        "f ${borgGlobalLock} 0600 root root -"
      ];
    }

    # btrbk is invoked as one unit against /etc/btrbk/btrbk.conf, not through
    # nixpkgs' services.btrbk instance generator, so this is a plain job
    # declaration and not an override of an upstream-rendered unit.
    # Depends on all snapshotted volumes being mounted. neo-outer-realm is an
    # HDD (slow spin-up) with nofail — without this, btrbk races the mount on boot.
    (mkBackupJob "btrbk" {
      description = "btrbk btrfs snapshot";
      unit.after = [
        "persist.mount"
        "realm.mount"
      ];
      execStart = "${pkgs.btrbk}/bin/btrbk --quiet --preserve-snapshots run";
      serviceConfig.TimeoutStopSec = "15s";
      timer = {
        onCalendar = "*-*-* *:00/30:00";
        persistent = false;
      };
    })

    # Root snapshot archival: the initrd saves pre-wipe / states to
    # .snapshots/root.TIMESTAMP (btrfs subvolumes) on every boot. Archive them
    # to a dedicated borg repo so slow root-drain work never blocks the normal
    # /persist backup lock, then delete only after the archive exists.
    (mkBackupJob "borgbackup-root-snapshots" {
      description = "Archive ephemeral root snapshots to borg";
      unit = {
        after = [
          "persist.mount"
          outerRealmMountUnit
        ];
        requires = [ outerRealmMountUnit ];
      };
      serviceConfig.TimeoutStopSec = "15s";
      environment = {
        BORG_PASSCOMMAND = "${pkgs.coreutils}/bin/cat ${borgPassphrasePath}";
        BORG_REPO = borgRepoRootSnapshots;
        BORG_CACHE_DIR = borgCacheDir;
      };
      timer = {
        onBootSec = "45min";
        onCalendar = "daily";
        persistent = true;
        randomizedDelaySec = 1800;
      };
      path = with pkgs; [
        btrfs-progs
        borgbackup
        coreutils
        findutils
        gnugrep
        procps
        util-linux
      ];
      script = ''
        ${mkBorgCommonScript borgRepoRootSnapshots borgRepoRootSnapshotsPath}
        acquire_borg_global_lock_or_skip "root snapshot Borg drain"
        recover_stale_borg_locks

        PERSIST_DEV="/dev/disk/by-uuid/f4782d9f-aabe-408e-b18b-2f2baa9e9a02"
        TMP_ROOT=$(mktemp -d)
        cleanup() {
          umount "$TMP_ROOT" 2>/dev/null || true
          rm -rf "$TMP_ROOT"
        }
        trap cleanup EXIT

        mount -o subvol=/ "$PERSIST_DEV" "$TMP_ROOT"

        if [ ! -e "${borgRepoRootSnapshotsPath}/config" ]; then
          install -d -m 0700 -o root -g root "${borgRepoRootSnapshotsPath}"
          with_borg_lock borg init --encryption repokey-blake2 "$BORG_REPO"
        fi

        delete_archived_snapshot() {
          snap_dir="$1"
          if btrfs subvolume show "$snap_dir" >/dev/null 2>&1; then
            btrfs subvolume delete "$snap_dir"
          else
            rm -rf --one-file-system "$snap_dir"
          fi
        }

        backed_up=0
        for snap_dir in "$TMP_ROOT"/.snapshots/root.*; do
          [ -d "$snap_dir" ] || continue
          snap_name=$(basename "$snap_dir")
          archive_name="root-$snap_name"

          if with_borg_lock borg list --short --glob-archives "$archive_name" "$BORG_REPO" | grep -Fxq "$archive_name"; then
            echo "Archive $archive_name already exists; deleting archived snapshot $snap_name"
            delete_archived_snapshot "$snap_dir"
            backed_up=$((backed_up + 1))
            continue
          fi

          if with_borg_lock borg create \
            --compression auto,zstd,1 \
            --lock-wait ${toString borgLockWaitSec} \
            --exclude "$snap_dir/dev" \
            --exclude "$snap_dir/home/*/.cache" \
            --exclude "$snap_dir/mnt" \
            --exclude "$snap_dir/neo-outer-realm" \
            --exclude "$snap_dir/nix" \
            --exclude "$snap_dir/outer-realm" \
            --exclude "$snap_dir/persist" \
            --exclude "$snap_dir/proc" \
            --exclude "$snap_dir/realm" \
            --exclude "$snap_dir/root/.cache" \
            --exclude "$snap_dir/run" \
            --exclude "$snap_dir/swap" \
            --exclude "$snap_dir/sys" \
            --exclude "$snap_dir/tmp" \
            --exclude "$snap_dir/var/cache" \
            "::$archive_name" "$snap_dir"; then
            delete_archived_snapshot "$snap_dir"
            backed_up=$((backed_up + 1))
          else
            echo "borg create failed for $snap_name; subvolume kept on disk" >&2
          fi
        done

        # Retention pruning and compaction are batched by
        # borgbackup-maintenance.service.
      '';
    })

    # The realm archive is the production authority for Sinex's checkout,
    # including the mutable Beads Dolt directory and tracked JSONL export.
    # This drill lists both exact paths, extracts them into an ephemeral
    # directory, validates their formats, and records archive/source commits.
    #
    # Its failure notification comes from the renderer, not from a hand-wired
    # onFailure: the drill is deliberately not an observed surface (its
    # evidence is the drill log, not unit state), so runtime.nix's
    # surface-driven attachment skips it and mkScheduledJob's does not.
    (mkBackupJob "sinnix-borg-beads-drill" {
      description = "Restore drill for Sinex Beads Dolt and issues JSONL";
      unit = {
        reloadIfChanged = false;
        stopIfChanged = false;
        after = [ outerRealmMountUnit ];
        requires = [ outerRealmMountUnit ];
      };
      environment = {
        BORG_PASSCOMMAND = "${pkgs.coreutils}/bin/cat ${borgPassphrasePath}";
        BORG_CACHE_DIR = borgCacheDir;
      };
      path = with pkgs; [
        borgbackup
        coreutils
        dolt
        git
        gnugrep
        jq
        util-linux
      ];
      serviceConfig = {
        PrivateTmp = true;
        TimeoutStartSec = "30min";
      };
      timer = {
        # Follow the regular realm archive and stay clear of the repository
        # integrity check and restore drill on Sunday (borgbackup-verify).
        onCalendar = "Thu 05:00:00";
        persistent = true;
      };
      script = mkSinexBeadsDrillScript;
    })
  ];
}
