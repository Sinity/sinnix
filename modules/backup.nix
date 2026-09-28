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
  backupCfg = config.sinnix.backup;

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
  realmCoverageAuditReceipt = "${borgDrainStateRoot}/realm.independent-full-audit.json";

  # Borg Configuration
  borgRepoPersistPath = "${borgRepoRoot}/borg-persist-v1";
  borgRepoRealmPath = "${borgRepoRoot}/borg-realm-v2";
  borgRepoRootSnapshotsPath = "${borgRepoRoot}/borg-root-snapshots-v1";
  borgRepoSinexBlobsPath = "${borgRepoRoot}/borg-sinex-blobs-v1";
  borgRepoPolylogueStatePath = "${borgRepoRoot}/borg-polylogue-state-v1";
  btrfsImageRoot = "${borgRepoRoot}/btrfs-images";
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
  sinexTaskAuthority = config.sinnix.projects.entries.sinex.taskAuthority;
  sinexBeadsArchivePath =
    assert lib.assertMsg (
      sinexTaskAuthority != null
      && lib.hasPrefix "${realmRoot}/" sinexTaskAuthority.workspace
      && lib.hasPrefix "${sinexTaskAuthority.workspace}/" sinexTaskAuthority.database
    ) "The Sinex Beads drill requires a task authority and database inside /realm";
    lib.removePrefix "${realmRoot}/" sinexTaskAuthority.workspace;
  sinexBeadsDatabaseRelativePath = lib.removePrefix "${sinexTaskAuthority.workspace}/" sinexTaskAuthority.database;
  sinexBeadsDrillLog = "${config.sinnix.paths.machineRoot}/borg_beads_drill.jsonl";
  # Elicitation state (items, the append-only comparison log, the fitted
  # model): operator judgments that cannot be recomputed from anything.
  elicitStateArchivePath = "state/elicit";
  # Paths under /realm no exclude pattern may cover, ancestors included.
  protectedRealmArchivePaths = [
    sinexBeadsArchivePath
    "${sinexBeadsArchivePath}/metadata.json"
    "${sinexBeadsArchivePath}/config.yaml"
    "${sinexBeadsArchivePath}/${sinexBeadsDatabaseRelativePath}/sinex/.dolt"
    elicitStateArchivePath
  ];
  # A six-hour snapshot can take about an hour to archive after acquisition.
  # Keep data age distinct from the last-success wall clock.
  borgDataFreshnessMaxAgeSec = 8 * 60 * 60;
  # sinex-blobs runs on its own daily timer (05:40), independently of
  # the persist/realm snapshot drain, so it needs its own budget rather than
  # sharing the six-hour snapshot cadence: budget 3x cadence so one missed/delayed
  # run doesn't false-positive, same convention as the capture
  # staleAfterSeconds entries below.
  borgDailyArchiveMaxAgeSec = 3 * 24 * 60 * 60;
  # Every unit in this module is the same shape: a oneshot a timer wakes,
  # never restarted by activation (a switch mid-drain would abandon a bind
  # mount and a held Borg lock), inside the backup envelope. Only
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

  # Borg records every holder of an exclusive lock as an empty file inside the
  # lock directory, named "<hostid>.<pid>-<threadid>" (borg/locking.py,
  # ExclusiveLock.unique_name); lock.roster repeats the same triple as JSON.
  # That recorded pid is the identification which survives the wrapper: the
  # wrapped binary's comm is `.borg-wrapped`, so matching a process name finds
  # no Borg at all and breaks the lock under a live writer.
  #
  # Only the hostname ahead of the hostid is compared. The "@<node-id>" tail
  # is uuid.getnode(), which differs between Borg runs here -- a repository
  # lock held by borgbackup-job-realm recorded a random-fallback node id while
  # Borg on the same host otherwise records the NIC MAC -- so requiring the
  # whole hostid to match would make every holder look foreign and no stale
  # lock could ever be broken. That instability is also why Borg's own
  # stale-lock reaper leaves these locks behind for this function to clear.
  #
  # $BORG_REPO and $BORG_CACHE_DIR are the environment Borg itself reads, so
  # the guard and the Borg it guards always look at the same repository.
  borgStaleLockRecovery = ''
    # Echoes the first holder of the lock directory $1 that may still be
    # running, and nothing when the lock is provably abandoned.
    borg_lock_live_holder() {
      borg_holder_dir="$1"
      borg_local_host="$(uname -n)"
      for borg_holder_path in "$borg_holder_dir"/*; do
        [ -e "$borg_holder_path" ] || continue
        borg_holder="''${borg_holder_path##*/}"
        borg_holder_host_pid="''${borg_holder%-*}"
        borg_holder_pid="''${borg_holder_host_pid##*.}"
        borg_holder_host="''${borg_holder_host_pid%.*}"
        case "$borg_holder_pid" in
          "" | *[!0-9]*)
            printf '%s' "$borg_holder"
            return
            ;;
        esac
        case "$borg_holder_host" in
          "$borg_local_host" | "$borg_local_host".* | "$borg_local_host"@*) ;;
          *)
            printf '%s' "$borg_holder"
            return
            ;;
        esac
        if [ -e /proc/"$borg_holder_pid" ]; then
          printf '%s' "$borg_holder"
          return
        fi
      done
    }

    recover_stale_borg_locks() {
      repo="''${1-$BORG_REPO}"
      repo_path="''${repo#file://}"

      if [ ! -e "$repo_path/config" ]; then
        return
      fi

      # `borg break-lock` clears the repository lock and this host's cache
      # lock for that repository, so a live holder of either one forbids it,
      # whether or not that particular lock has aged past the threshold.
      borg_stale_locks=""
      for borg_lock_dir in \
        "$repo_path/lock.exclusive" \
        "$BORG_CACHE_DIR/lock.exclusive" \
        "$BORG_CACHE_DIR"/*/lock.exclusive; do
        [ -d "$borg_lock_dir" ] || continue
        borg_lock_holder="$(borg_lock_live_holder "$borg_lock_dir")"
        if [ -n "$borg_lock_holder" ]; then
          echo "Borg lock $borg_lock_dir for $repo is held by $borg_lock_holder; refusing break-lock" >&2
          return
        fi
        borg_lock_age=$(($(date +%s) - $(stat -c %Y "$borg_lock_dir")))
        if [ "$borg_lock_age" -gt ${toString (borgStaleLockMinutes * 60)} ]; then
          borg_stale_locks="$borg_stale_locks $borg_lock_dir"
        fi
      done

      if [ -z "$borg_stale_locks" ]; then
        return
      fi

      echo "Breaking stale Borg lock for $repo:$borg_stale_locks" >&2
      with_borg_lock borg break-lock "$repo"
    }
  '';

  mkBorgCommonScript = repo: ''
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
      marker="$1"
      marker_dir="$(dirname "$marker")"
      marker_base="$(basename "$marker")"
      temporary="$(mktemp "$marker_dir/.''${marker_base}.tmp.XXXXXX")"
      trap 'rm -f "$temporary"' RETURN
      cat > "$temporary" || return 1
      chmod 0644 "$temporary" || return 1
      sync -f "$temporary" || return 1
      mv -f "$temporary" "$marker" || return 1
      sync -f "$marker_dir" || return 1
      trap - RETURN
    }

    ${borgStaleLockRecovery}
  '';

  snapshotCoverage = "${pkgs.python3}/bin/python3 ${./lib/backup/snapshot-coverage.py}";

  mkCoveragePolicy =
    {
      label,
      bindTarget,
      exclude,
      noncanonical,
    }:
    pkgs.writeText "${label}-snapshot-coverage.json" (
      builtins.toJSON (
        {
          inherit noncanonical;
          chrome_extension_caches = label == "persist";
          borg_excludes = borgExcludePatterns bindTarget exclude;
        }
        // lib.optionalAttrs (label == "realm") {
          producer_contract = "realm-borg-create-v2";
        }
      )
    );

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
    }:
    let
      coveragePolicy = mkCoveragePolicy {
        inherit
          label
          bindTarget
          exclude
          noncanonical
          ;
      };
    in
    ''
      set -euo pipefail
      export LC_ALL=C
      ${mkBorgCommonScript repo}
      install -d -m 0755 -o root -g root ${lib.escapeShellArg borgDrainStateRoot}
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
      recover_stale_borg_locks
      if [ ! -e ${lib.escapeShellArg "${repoPath}/config"} ]; then
        with_borg_lock borg init --encryption repokey-blake2 "$BORG_REPO"
      fi

      marker=${lib.escapeShellArg "${borgDrainStateRoot}/${label}.last-success"}
      snapshot="$(${snapshotCoverage} select ${lib.escapeShellArg snapshotDir} ${lib.escapeShellArg snapshotGlob} "$latest_marker")"
      if [ -n "$snapshot" ]; then
        snapshot_path=${lib.escapeShellArg snapshotDir}/"$snapshot"
        archive_name=${lib.escapeShellArg archivePrefix}-"$snapshot"
        original_archive_name="$archive_name"
        snapshot_details="$(${snapshotCoverage} details "$snapshot_path")"
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
          if [ ${lib.escapeShellArg label} = realm ]; then
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
        if [ ${lib.escapeShellArg label} = realm ] && [ -f "$pending_receipt" ]; then
          if receipt_archive="$(${pkgs.jq}/bin/jq -er '.archive' "$pending_receipt" 2>/dev/null)" \
            && [[ "$receipt_archive" == "$original_archive_name" || "$receipt_archive" == "$original_archive_name"-* ]] \
            && printf '%s\n' "$archives" | grep -Fxq "$receipt_archive" \
            && producer_proof="$(${snapshotCoverage} verify-created ${lib.escapeShellArg bindTarget} \
              "$receipt_archive" "$snapshot_uuid" ${coveragePolicy} "$pending_receipt" 2>/dev/null)"; then
            archive_name="$receipt_archive"
          fi
        fi
        if [ ${lib.escapeShellArg label} = realm ] && [ -z "$producer_proof" ] \
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
        # Realm accepts only the observed zero-warning create or its matching
        # durable receipt; its independent full comparison has its own job.
        # Persist keeps its first/policy-change/weekly full comparison and
        # uses a producer proof on fresh creates between those checks.
        if [ ${lib.escapeShellArg label} = realm ]; then
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
        if [ "$(${snapshotCoverage} details "$snapshot_path")" != "$snapshot_details" ]; then
          echo "Snapshot identity changed; retaining $snapshot_path" >&2
          exit 1
        fi
        {
          printf 'archive=%s\n' "$archive_name"
          printf 'snapshot=%s\n' "$snapshot"
          printf 'generation=%s\n' "$snapshot_generation"
          printf 'subvolume_id=%s\n' "$snapshot_id"
          printf 'coverage=%s\n' "$proof"
          printf 'epoch=%s\n' "$(date +%s)"
        } | publish_backup_marker "$latest_marker"
        publish_backup_marker "$marker" < "$latest_marker"
      fi
      # A crash during deletion leaves the verified marker in place. Every
      # later wake resumes the remaining local prune, even with no new archive.
      if [ -f "$latest_marker" ]; then
        prune_plan="$(${snapshotCoverage} prune-plan -- ${lib.escapeShellArg snapshotDir} ${lib.escapeShellArg snapshotGlob} "$latest_marker" ${lib.escapeShellArg archivePrefix} ${lib.escapeShellArg replacementSuffix})"
        while IFS=$'\t' read -r old expected_uuid expected_generation expected_id; do
          [ -n "$old" ] || continue
          old_path=${lib.escapeShellArg snapshotDir}/"$old"
          actual_details="$(${snapshotCoverage} details "$old_path")"
          if [ "$actual_details" != "$(printf '%s\t%s\t%s' "$expected_uuid" "$expected_generation" "$expected_id")" ]; then
            echo "Snapshot identity changed; retaining $old_path" >&2
            exit 1
          fi
          btrfs subvolume delete "$old_path"
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
    "home/sinity/.local/state/claude-code/npm/.cargo/registry"
    "home/sinity/.local/share/nvim/mason"
    "home/sinity/.local/share/hyprland/logs"
    "var/lib/systemd/coredump"
    # Sinex runtime state is backed up through structured service tooling.
    "var/lib/sinex"
  ]
  ++ chromeCacheRoots
  ++ chromeExtensionCacheExcludes;

  realmExcludes = [
    # Re-acquirable media: Steam, model weights, and private project caches
    # regenerable members carry their own provenance. Precious-small media
    # (books, videos, substack, edu, music-audio-features, web-content)
    # deliberately stays in coverage.
    # steamapps, not library/games/steam: the games are 98G of the 103G and Steam
    # re-downloads them, but the remaining ~5G is client state that CONTAINS
    # library/games/steam/userdata -- Steam Cloud save files and game recordings, which
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
    # Model weights are re-acquirable, so the exact library/models root is
    # excluded and classified noncanonical. Tags in other realm subtrees do
    # not exclude them; their contents stay covered until explicitly classified.
    # Steam's exclusion names steamapps directly to retain userdata.
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
    # this is the same class as library/models and the caches above -- it simply
    # was not named, and had been replicating in full. Checked before
    # excluding: the whole 23G is overlay/ image layers, and volumes/ is
    # EMPTY -- these containers keep their data on bind mounts under
    # /realm/library and /realm/state, which stay in coverage. If a named
    # volume ever appears here, this exclusion starts dropping real state.
    "state/containers"
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
    "worktrees"
    ".pytest_cache"
    "project/.pytest_cache"
    # A directory name alone does not establish that its contents can be
    # recreated. Broad exclusions formerly matched source material under
    # build/, dist/, node_modules/, and other project-local names. The two
    # pytest roots above are classified separately; nested names stay covered.
    # Freedesktop trash at the realm root is one such exact root.
    ".Trash-1000"
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
      "home/sinity/.local/state/claude-code/npm/.cargo/registry"
      "home/sinity/.local/share/nvim/mason"
      "home/sinity/.local/share/hyprland/logs"
      "var/lib/systemd/coredump"
    ]
    ++ chromeCacheRoots
  );
  realmNoncanonical = lib.intersectLists realmExcludes [
    "library/games/steam/steamapps"
    "library/models"
    "state/cache"
    "health/genome/cache"
    "state/containers"
    "tmp"
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
  ];

  realmExcludeMatchesProtectedPath = import ./lib/backup/protected-paths.nix {
    inherit lib;
    paths = protectedRealmArchivePaths;
  };

  mkSinexBeadsDrillScript = ''
    set -euo pipefail

    archive_path=${lib.escapeShellArg sinexBeadsArchivePath}

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

    borg list --short "${borgRepoRealm}::''${archive}" "$archive_path" | grep -Fxq "$archive_path"

    restore_root="$(mktemp -d)"
    cleanup() {
      rm -rf "$restore_root"
    }
    trap cleanup EXIT

    (
      cd "$restore_root"
      borg extract "${borgRepoRealm}::''${archive}" "$archive_path"
    )

    beads_path="$restore_root/$archive_path"
    test -s "$beads_path/metadata.json"
    jq -e 'type == "object"' "$beads_path/metadata.json" >/dev/null
    test -s "$beads_path/config.yaml"
    database_path="$beads_path/${sinexBeadsDatabaseRelativePath}"
    test -d "$database_path/sinex/.dolt"

    # A restored server configuration can name a live port. Open the database
    # in a separate scratch data directory without that configuration.
    offline_root="$restore_root/offline"
    mkdir "$offline_root"
    mv "$database_path/sinex" "$offline_root/sinex"
    dolt_commit="$(${pkgs.dolt}/bin/dolt --data-dir "$offline_root" --use-db sinex sql \
      -q 'SELECT commit_hash FROM dolt_log LIMIT 1' -r json \
      | jq -er '.rows[0].commit_hash | select(test("^[0-9a-v]{32}$"))')"
    issue="$(${pkgs.dolt}/bin/dolt --data-dir "$offline_root" --use-db sinex sql \
      -q 'SELECT id, title FROM issues ORDER BY id LIMIT 1' -r json \
      | jq -cer '.rows[0] | select(.id != null and .id != "" and .title != null and .title != "")')"

    install -d -m 0755 ${lib.escapeShellArg (builtins.dirOf sinexBeadsDrillLog)}
    jq -nc \
      --arg type sinex_beads_restore_drill \
      --arg archive "$archive" \
      --arg authority_path "$archive_path" \
      --arg dolt_commit "$dolt_commit" \
      --argjson issue "$issue" \
      --arg ts "$(date -Iseconds)" \
      '{ts:$ts,type:$type,archive:$archive,authority_path:$authority_path,dolt_commit:$dolt_commit,issue:$issue,ok:true}' \
      | tee -a ${lib.escapeShellArg sinexBeadsDrillLog}
  '';

  # Persist and realm freshness probes read snapshot timestamps from their
  # latest-archived markers. The integrity probe below has its own deadline.
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
    # --preserve-snapshots, so only Borg drain jobs delete snapshots, after
    # the newest selected snapshot has a verified archive.

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
  options.sinnix.backup.enable = (lib.mkEnableOption "workstation snapshot and archive backups") // {
    default = config.sinnix.machine.isDesktop;
  };

  config = lib.mkIf backupCfg.enable (
    lib.mkMerge (
      [
        {
          # The realm archive's observed working set paged heavily under the
          # 2G/4G background slice. Give this one low-I/O-priority Borg lane
          # memory headroom without raising limits for every backup service.
          systemd.slices.borgdrain.sliceConfig = {
            CPUWeight = 3;
            IOWeight = 20;
            MemoryHigh = "6G";
            MemoryMax = "8G";
          };

          sinnix.runtime.dataStores = {
            # Backup coverage remains active for persisted Polylogue data even
            # when its daemon is disabled. The owning service supplies the
            # same higher-priority declarations when enabled.
            polylogue-inbox = lib.mkDefault {
              path = "${polylogueStateRoot}/inbox";
              class = "canonical";
            };
            polylogue-source = lib.mkDefault {
              path = "${polylogueStateRoot}/source.db";
              class = "canonical";
            };
            polylogue-user = lib.mkDefault {
              path = "${polylogueStateRoot}/user.db";
              class = "canonical";
            };
            polylogue-audit = lib.mkDefault {
              path = "${polylogueStateRoot}/audit.db";
              class = "canonical";
            };
            polylogue-ops = lib.mkDefault {
              path = "${polylogueStateRoot}/ops.db";
              class = "canonical";
            };
            polylogue-index = lib.mkDefault {
              path = "${polylogueStateRoot}/index.db";
              class = "derived";
              inputs = [
                "polylogue-inbox"
                "polylogue-source"
                "polylogue-user"
                "polylogue-audit"
                "polylogue-ops"
              ];
            };
            polylogue-embeddings = lib.mkDefault {
              path = "${polylogueStateRoot}/embeddings.db";
              class = "derived";
              inputs = [ "polylogue-source" ];
            };
            realm-source = {
              path = realmRoot;
              class = "canonical";
            };
            persist-source = {
              path = "/persist";
              class = "canonical";
            };
            realm-snapshots = {
              path = realmSnapshots;
              class = "exact-copy";
              source = "realm-source";
            };
            persist-snapshots = {
              path = persistSnapshots;
              class = "exact-copy";
              source = "persist-source";
            };
            borg-realm-archives = {
              # Historical canonical contents selected by the actual Borg
              # exclusions. This is not a full copy of /realm: nested dedicated
              # subvolumes have separate backup jobs, and every deletion needs
              # the per-snapshot coverage proof above.
              path = borgRepoRealmPath;
              class = "canonical";
              preservation = "indefinite";
              backup = "direct";
            };
            borg-persist-archives = {
              path = borgRepoPersistPath;
              class = "canonical";
              preservation = "indefinite";
              backup = "direct";
            };
            sinex-blob-repository = {
              path = sinexBlobRepositoryPath;
              class = "canonical";
            };
            borg-sinex-blob-archives = {
              path = borgRepoSinexBlobsPath;
              class = "exact-copy";
              source = "sinex-blob-repository";
              preservation = "indefinite";
              backup = "direct";
            };
            borg-root-archives = {
              path = borgRepoRootSnapshotsPath;
              # Each archive is the durable historical record after
              # rebuildable root paths are excluded from a pre-wipe snapshot.
              class = "canonical";
              backup = "direct";
            };
            borg-polylogue-state-archives = {
              # This repository preserves selected non-database state across
              # versions and is therefore a canonical historical source.
              path = borgRepoPolylogueStatePath;
              class = "canonical";
              backup = "direct";
            };
            polylogue-db-dumps = {
              path = polylogueBackupRoot;
              class = "exact-copy";
              inputs = [
                "polylogue-source"
                "polylogue-user"
                "polylogue-audit"
                "polylogue-ops"
                "polylogue-index"
                "polylogue-embeddings"
              ];
              preservation = "indefinite";
              backup = "direct";
            };
            machine-telemetry-dumps = {
              path = machineTelemetryBackupRoot;
              class = "exact-copy";
              source = "machine-telemetry";
              preservation = "indefinite";
              backup = "direct";
            };
          };

          sinnix.runtime.surfaces = {
            borgbackup-drain-coordinator = {
              unit = "borgbackup-drain-coordinator.service";
              resourceClass = "backup";
              observe = {
                enable = true;
                restartable = false;
              };
            };
            btrbk = {
              unit = "btrbk.service";
              resourceClass = "backup";
            };
            btrbk-timer = {
              unit = "btrbk.timer";
              kind = "timer";
              observe = {
                enable = true;
                restartable = false;
              };
            };
            borgbackup-job-persist = {
              unit = "borgbackup-job-persist.service";
              resourceClass = "backup";
              observe = {
                enable = true;
                restartable = false;
              };
              captures = [
                {
                  name = "borg-persist-archive";
                  path = "${borgDrainStateRoot}/persist.latest-archived";
                  eventDriven = true;
                  livenessProbe = {
                    command = "${snapshotCoverage} freshness ${borgDrainStateRoot}/persist.latest-archived ${toString borgDataFreshnessMaxAgeSec}";
                    timeoutSeconds = 15;
                  };
                  data = {
                    class = "derived";
                    inputs = [ "borg-persist-archives" ];
                  };
                }
              ];
            };
            borgbackup-job-realm = {
              unit = "borgbackup-job-realm.service";
              resourceClass = "backup";
              resources = {
                Slice = "borgdrain.slice";
                MemoryHigh = "4G";
                MemoryMax = "6G";
              };
              observe = {
                enable = true;
                restartable = false;
              };
              captures = [
                {
                  name = "borg-realm-archive";
                  path = "${borgDrainStateRoot}/realm.latest-archived";
                  eventDriven = true;
                  livenessProbe = {
                    command = "${snapshotCoverage} freshness ${borgDrainStateRoot}/realm.latest-archived ${toString borgDataFreshnessMaxAgeSec}";
                    timeoutSeconds = 15;
                  };
                  data = {
                    class = "derived";
                    inputs = [ "borg-realm-archives" ];
                  };
                }
              ];
            };
            # Declared only when the job exists: archives.nix builds this job
            # under the same predicate, and a surface whose unit is never
            # configured advertises an envelope nothing applies.
            borgbackup-job-sinex-blobs = lib.mkIf (sinexBlobRepositoryPath != "") {
              unit = "borgbackup-job-sinex-blobs.service";
              resourceClass = "backup";
              observe = {
                enable = true;
                restartable = false;
              };
              captures = [
                {
                  name = "borg-sinex-blobs-archive";
                  path = "${borgDrainStateRoot}/sinex-blobs.last-success";
                  eventDriven = true;
                  # sinex-blobs runs on its own daily 05:40 timer, independently of the
                  # persist/realm drain cadence, so it keeps the daily budget the
                  # retired borgbackup-status check used for it (3x cadence).
                  staleAfterSeconds = borgDailyArchiveMaxAgeSec;
                  data = {
                    class = "derived";
                    inputs = [ "borg-sinex-blob-archives" ];
                  };
                }
              ];
            };
            polylogue-sqlite-backup = {
              unit = "polylogue-sqlite-backup.service";
              resourceClass = "backup";
              observe.enable = true;
            };
            polylogue-sqlite-backup-timer = {
              unit = "polylogue-sqlite-backup.timer";
              kind = "timer";
            };
            borgbackup-job-polylogue-state = {
              unit = "borgbackup-job-polylogue-state.service";
              resourceClass = "backup";
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
                  data = {
                    class = "derived";
                    inputs = [ "borg-polylogue-state-archives" ];
                  };
                }
              ];
            };
            borgbackup-job-machine-telemetry-dumps = {
              unit = "borgbackup-job-machine-telemetry-dumps.service";
              resourceClass = "backup";
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
                  data = {
                    class = "derived";
                    inputs = [ "machine-telemetry-dumps" ];
                  };
                }
              ];
            };
            borgbackup-coverage-audit-realm = {
              unit = "borgbackup-coverage-audit-realm.service";
              resourceClass = "backup";
              observe = {
                enable = true;
                restartable = false;
              };
              captures = [
                {
                  name = "borg-realm-independent-full-audit";
                  path = realmCoverageAuditReceipt;
                  eventDriven = true;
                  staleAfterSeconds = 691200;
                  livenessProbe = {
                    command = "${snapshotCoverage} audit-status ${realmCoverageAuditReceipt} ${realmCoveragePolicy} 691200";
                    timeoutSeconds = 10;
                  };
                  data = {
                    class = "derived";
                    inputs = [ "borg-realm-archives" ];
                  };
                }
              ];
            };
            borgbackup-verify = {
              unit = "borgbackup-verify.service";
              resourceClass = "backup";
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
                  data = {
                    class = "derived";
                    inputs = [
                      "borg-realm-archives"
                      "borg-persist-archives"
                    ];
                  };
                }
              ];
            };
            borgbackup-maintenance = {
              unit = "borgbackup-maintenance.service";
              resourceClass = "backup";
              observe = {
                enable = true;
                restartable = false;
              };
            };
            btrfs-metadata-image-backup = {
              unit = "btrfs-metadata-image-backup.service";
              resourceClass = "backup";
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
              resourceClass = "backup";
            };
            sinnix-borg-beads-drill = {
              unit = "sinnix-borg-beads-drill.service";
              resourceClass = "backup";
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

      ]
      ++ (import ./lib/backup/snapshots.nix {
        inherit
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
          btrfsImageRoot
          borgCacheDir
          borgGlobalLock
          mkBackupJob
          ;
      })
      ++ (import ./lib/backup/archives.nix {
        inherit
          pkgs
          lib
          realmRoot
          sinexBlobRepositoryPath
          scriptPkgs
          username
          polylogueStateRoot
          polylogueBackupRoot
          machineTelemetryBackupRoot
          machineTelemetryBackupMarker
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
          borgPassphrasePath
          outerRealmMountUnit
          borgLockWaitSec
          borgCacheDir
          borgGlobalLock
          mkBackupJob
          mkBorgExcludeArgs
          borgStaleLockRecovery
          mkBorgCommonScript
          ;
      })
      ++ (import ./lib/backup/acknowledgement.nix {
        inherit
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
          mkBackupJob
          mkBorgCommonScript
          mkSnapshotDrainScript
          snapshotCoverage
          persistExcludes
          realmExcludes
          persistNoncanonical
          realmNoncanonical
          ;
      })
      ++ (import ./lib/backup/verification.nix {
        inherit
          pkgs
          lib
          config
          sinexBlobRepositoryPath
          scriptPkgs
          borgDrainStateRoot
          borgIntegrityReceipt
          realmCoverageAuditReceipt
          btrfsImageRoot
          btrfsImageMinBytes
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
          mkSinexBeadsDrillScript
          ;
      })
    )
  );
}
