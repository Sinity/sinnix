# Internal backup component. Public options and shared policy live in modules/backup.nix.
#
# Hourly archives of small, high-value live state. The nightly coordinator
# drains btrbk snapshots once a day, so a lost disk used to cost up to a day
# of the stores below; these two jobs bring that to about an hour.
#
# - borgbackup-job-persist-hourly: a read-only snapshot of /persist (the worn
#   root SSD) archived into the persist repository as `hourly-persist-*`. It
#   binds the snapshot at the drain's own source path, with its archive layout
#   and file-cache flags, so cache entries match. Its Borg cache lives on
#   /realm so hourly cache commits (about 570 MB each) never land on the root
#   SSD; the first run seeds that cache from the drain's.
# - borgbackup-job-live-small: Polylogue's authored tables (a consistent
#   read-transaction dump of archive.db), the Beads task databases (old and
#   new layouts alike: the whole tasks tree minus copied migration backups),
#   and the Sinex producer spools. The Sinex PostgreSQL dump stays daily: it
#   writes 2.7 GB over about 4.5 minutes, too heavy for every hour; the
#   spools hold what the producers have not yet had acknowledged.
#
# Both take the global Borg lock without waiting and skip an hour when another
# Borg operation holds it. Their series are pruned by borgbackup-maintenance
# as active series (keep-within 2d, then daily, weekly, monthly), so only
# hourly intermediates older than two days expire.
{
  pkgs,
  lib,
  realmRoot,
  username,
  sinexSpoolPaths,
  borgRepoPersist,
  borgRepoPersistPath,
  borgRepoLiveSmall,
  borgRepoLiveSmallPath,
  borgPersistSnapshotBind,
  borgDrainStateRoot,
  borgCacheDir,
  borgHourlyCacheDir,
  borgLockWaitSec,
  outerRealmMountUnit,
  persistExcludes,
  mkBackupJob,
  mkBorgCommonScript,
  mkBorgExcludeArgs,
}:
let
  persistHourlyCut = "/persist/.btrfs/borg-hourly-cut";
  polylogueArchiveDb = "${realmRoot}/state/polylogue-live/data/polylogue/archive.db";
  # Every authored or operator-requested record in the standalone archive
  # (the rewrite's store/schema: notes carry assertions, judgments and saved
  # queries; settings, kept results, excisions, the request log and chat
  # actions are authored too). Inputs, revisions and extents are captured
  # bytes covered by the daily realm job.
  polylogueAuthoredTables = [
    "note"
    "note_target"
    "note_relation"
    "setting"
    "kept_result"
    "excision"
    "client_request"
    "chat_action"
    "chat_action_attachment"
    "chat_action_event"
  ];
  tasksRoot = "${realmRoot}/state/tasks";
  tasksExcludes = [
    "migration-backups"
    "**/dolt-server.log"
  ];

  hourlyCommon = repo: ''
    ${mkBorgCommonScript repo}
    export BORG_CACHE_DIR=${lib.escapeShellArg borgHourlyCacheDir}
    install -d -m 0700 -o root -g root ${lib.escapeShellArg borgHourlyCacheDir}
    install -d -m 0750 -o root -g users ${lib.escapeShellArg borgDrainStateRoot}
    started=$(date +%s)
  '';

  publishHourlyMarker = label: ''
    finished=$(date +%s)
    {
      printf 'archive=%s\n' "$archive_name"
      printf 'epoch=%s\n' "$finished"
      printf 'elapsed_seconds=%s\n' "$((finished - started))"
    } | publish_backup_marker ${lib.escapeShellArg "${borgDrainStateRoot}/${label}.last-success"}
    echo "backup_phase=done label=${label} archive=$archive_name elapsed_seconds=$((finished - started))"
  '';

  hourlyServiceConfig = {
    TimeoutStartSec = "45min";
    TimeoutStopSec = "15s";
  };
in
[
  (mkBackupJob "borgbackup-job-persist-hourly" {
    description = "Archive a /persist snapshot into Borg every hour";
    unit = {
      after = [
        "persist.mount"
        "realm.mount"
        outerRealmMountUnit
      ];
      requires = [
        "persist.mount"
        outerRealmMountUnit
      ];
      unitConfig.RequiresMountsFor = [ borgHourlyCacheDir ];
    };
    serviceConfig = hourlyServiceConfig;
    path = with pkgs; [
      borgbackup
      btrfs-progs
      coreutils
      gnugrep
      util-linux
    ];
    timer = {
      onCalendar = "*-*-* *:17:00";
      persistent = false;
    };
    script = ''
      set -euo pipefail
      ${hourlyCommon borgRepoPersist}
      acquire_borg_global_lock_or_skip "hourly persist archive"
      if [ ! -e ${lib.escapeShellArg "${borgRepoPersistPath}/config"} ]; then
        echo "persist repository is not initialized; the nightly drain creates it" >&2
        exit 1
      fi

      cut=${lib.escapeShellArg persistHourlyCut}
      bind=${lib.escapeShellArg borgPersistSnapshotBind}
      release_cut() {
        if mountpoint -q "$bind"; then umount "$bind"; fi
        if [ -d "$cut" ]; then btrfs -q subvolume delete "$cut"; fi
      }
      release_cut
      trap release_cut EXIT

      # Seed this cache from the drain's once, so the first hourly run does
      # not re-read and re-chunk all of /persist or rebuild 200+ archive
      # indexes from the target disk.
      repo_id="$(grep -m1 '^id = ' ${lib.escapeShellArg "${borgRepoPersistPath}/config"} | cut -d' ' -f3)"
      if [ -n "$repo_id" ] && [ ! -e "$BORG_CACHE_DIR/$repo_id" ] && [ -d ${lib.escapeShellArg borgCacheDir}/"$repo_id" ]; then
        cp -a ${lib.escapeShellArg borgCacheDir}/"$repo_id" "$BORG_CACHE_DIR/.seed-$repo_id"
        mv "$BORG_CACHE_DIR/.seed-$repo_id" "$BORG_CACHE_DIR/$repo_id"
      fi

      install -d -m 0700 -o root -g root "$bind"
      btrfs -q subvolume snapshot -r /persist "$cut"
      mount --bind "$cut" "$bind"

      archive_name="hourly-persist-$(date -u +%Y%m%dT%H%M%SZ)"
      BORG_EXIT_CODES=modern borg create \
        --files-cache ctime,size,inode --files-changed ctime \
        --compression auto,zstd,1 \
        --lock-wait ${toString borgLockWaitSec} \
        --stats \
        ${mkBorgExcludeArgs borgPersistSnapshotBind persistExcludes} \
        "::$archive_name" "$bind/./"
      ${publishHourlyMarker "persist-hourly"}
    '';
  })

  (mkBackupJob "borgbackup-job-live-small" {
    description = "Archive Polylogue authored records, Beads and Sinex spools into Borg every hour";
    unit = {
      after = [
        "realm.mount"
        outerRealmMountUnit
      ];
      requires = [
        "realm.mount"
        outerRealmMountUnit
      ];
      unitConfig.RequiresMountsFor = [
        tasksRoot
        borgHourlyCacheDir
      ];
    };
    serviceConfig = hourlyServiceConfig // {
      RuntimeDirectory = "borg-live-small";
      RuntimeDirectoryMode = "0711";
    };
    path = with pkgs; [
      borgbackup
      coreutils
      gnugrep
      sqlite
      util-linux
    ];
    timer = {
      onCalendar = "*-*-* *:47:00";
      persistent = false;
    };
    script = ''
      set -euo pipefail
      ${hourlyCommon borgRepoLiveSmall}
      acquire_borg_global_lock_or_skip "hourly live-small archive"
      install -d -m 0700 -o root -g root ${lib.escapeShellArg borgRepoLiveSmallPath}
      recover_stale_borg_locks
      if [ ! -e ${lib.escapeShellArg "${borgRepoLiveSmallPath}/config"} ]; then
        with_borg_lock borg init --encryption repokey-blake2 "$BORG_REPO"
      fi

      # One read transaction gives a consistent cut while the daemon writes.
      # It runs as the archive's owner so no root-owned WAL files appear. The
      # dump lands in this unit's tmpfs runtime directory, never on a disk.
      stage="$RUNTIME_DIRECTORY/polylogue"
      install -d -m 0700 -o ${lib.escapeShellArg username} -g users "$stage"
      sources=()
      if [ -e ${lib.escapeShellArg polylogueArchiveDb} ]; then
        runuser -u ${lib.escapeShellArg username} -- \
          sqlite3 -readonly -bail ${lib.escapeShellArg polylogueArchiveDb} \
          ".output $stage/authored.sql" \
          ".dump ${lib.concatStringsSep " " polylogueAuthoredTables}"
        test -s "$stage/authored.sql"
        sources+=("$stage")
      fi
      sources+=(${lib.escapeShellArg tasksRoot})
      for spool in ${lib.escapeShellArgs sinexSpoolPaths}; do
        [ -d "$spool" ] && sources+=("$spool")
      done

      # Dolt servers and spool producers write while Borg reads. Dolt's table
      # files are immutable, its manifest is replaced atomically and its
      # journal is append-only, so a changing file is a journal or spool tail
      # the next hour takes. Only that warning (status 100) is accepted.
      archive_name="live-small-$(date -u +%Y%m%dT%H%M%SZ)"
      create_status=0
      BORG_EXIT_CODES=modern borg create \
        --compression auto,zstd,3 \
        --lock-wait ${toString borgLockWaitSec} \
        --stats \
        ${mkBorgExcludeArgs tasksRoot tasksExcludes} \
        "::$archive_name" "''${sources[@]}" || create_status=$?
      if [ "$create_status" -eq 100 ]; then
        echo "live-small: accepted files that changed while read (Dolt journals and spools)"
      elif [ "$create_status" -ne 0 ]; then
        exit "$create_status"
      fi
      ${publishHourlyMarker "live-small"}
    '';
  })
]
