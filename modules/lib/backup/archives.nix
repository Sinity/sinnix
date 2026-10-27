# Internal backup component. Public options and shared policy live in modules/backup.nix.
{
  pkgs,
  lib,
  realmRoot,
  sinexStorePaths,
  scriptPkgs,
  username,
  polylogueStateRoot,
  polylogueBackupRoot,
  polylogueDbNames,
  polylogueDbExcludes,
  borgDrainStateRoot,
  borgRepoRealmPath,
  borgRepoSinexBlobsPath,
  borgRepoPolylogueStatePath,
  borgRepoPersist,
  borgRepoRealm,
  borgRepoRootSnapshots,
  borgRepoSinexBlobs,
  borgRepoPolylogueState,
  borgPassphrasePath,
  outerRealmMountUnit,
  borgLockWaitSec,
  borgCacheDir,
  borgGlobalLock,
  mkBackupJob,
  mkBorgExcludeArgs,
  borgStaleLockRecovery,
  mkBorgCommonScript,
}:
let
  maintenanceJob = {
    description = "Prune and compact Borg backup repositories";
    unit = {
      after = [ outerRealmMountUnit ];
      requires = [ outerRealmMountUnit ];
    };
    serviceConfig = {
      TimeoutStartSec = "8h";
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
      util-linux
    ];
    script = ''
      set -euo pipefail
      umask 077
      export BORG_CACHE_DIR=${lib.escapeShellArg borgCacheDir}
      dry_run="''${SINNIX_BORG_MAINTENANCE_DRY_RUN:-0}"
      marker=${lib.escapeShellArg "${borgDrainStateRoot}/maintenance.last-success"}
      now=$(date +%s)
      # Hourly attempts retry contention; a completed pass is due after 20h.
      if [ "$dry_run" = 0 ] && [ -f "$marker" ] && [ $((now - $(cat "$marker"))) -lt 72000 ]; then
        exit 0
      fi
      # Prune applies retention daily; compaction only returns freed space,
      # and at borg's 10% threshold it rewrote segments on every pass (1.17 TB
      # read and 320 GB written by 16 passes over 2026-10-18..10-27). Compact
      # weekly instead.
      compact_marker=${lib.escapeShellArg "${borgDrainStateRoot}/compact.last-success"}
      compact_due=1
      if [ -f "$compact_marker" ] && [ $((now - $(cat "$compact_marker"))) -lt 561600 ]; then
        compact_due=0
      fi
      exec 9>${lib.escapeShellArg borgGlobalLock}
      if ! flock -n 9; then
        echo "status=deferred reason=borg-lock-contention remains_due=true"
        exit 0
      fi
      export SINNIX_BORG_GLOBAL_LOCK_HELD=1
      with_borg_lock() { "$@"; }
      ${borgStaleLockRecovery}
      run_dir=${lib.escapeShellArg "${borgDrainStateRoot}/retention"}/$(date -u +%Y%m%dT%H%M%SZ)-$$
      install -d -m 0700 "$run_dir"
      if [ "$dry_run" = 1 ]; then
        prune_options=(--dry-run)
      else
        prune_options=(--stats)
      fi
      maintain_repo() {
        repo="$1"
        active="$2"
        shift 2
        if [ ! -e "''${repo#file://}/config" ]; then
          echo "Skipping uninitialized repo $repo"
          return
        fi
        if [ "$dry_run" = 0 ]; then recover_stale_borg_locks "$repo"; fi
        name=$(basename "''${repo#file://}")
        borg list --json --lock-wait ${toString borgLockWaitSec} "$repo" > "$run_dir/$name.before.json"
        IFS=' ' read -r -a active_series <<< "$active"
        for active_series_name in "''${active_series[@]}"; do
          borg prune --lock-wait ${toString borgLockWaitSec} --list "''${prune_options[@]}" \
            --glob-archives "$active_series_name" \
            --keep-within 2d --keep-daily 14 --keep-weekly 8 --keep-monthly 12 "$repo"
        done
        for series in "$@"; do
          # Explicit expiry makes even a stopped series eventually disappear.
          expire_options=()
          if [ "$dry_run" = 1 ]; then expire_options=(--dry-run); fi
          ${scriptPkgs.sinnix-borg-expire}/bin/sinnix-borg-expire "$repo" "$series" "''${expire_options[@]}"
          borg prune --lock-wait ${toString borgLockWaitSec} --list "''${prune_options[@]}" \
            --glob-archives "$series" --keep-monthly 6 "$repo"
        done
        if [ "$dry_run" = 0 ]; then
          if [ "$compact_due" = 1 ]; then
            borg compact --lock-wait ${toString borgLockWaitSec} --progress "$repo"
          fi
          borg list --json --lock-wait ${toString borgLockWaitSec} "$repo" > "$run_dir/$name.after.json"
        fi
      }
      maintain_repo ${lib.escapeShellArg borgRepoPersist} 'persist-*' 'sinnix-prime-persist-*'
      maintain_repo ${lib.escapeShellArg borgRepoRealm} 'realm-* genome-genome.*' 'sinnix-prime-realm-*' 'machine-telemetry-dumps-*'
      maintain_repo ${lib.escapeShellArg borgRepoSinexBlobs} 'sinex-blobs-*'
      maintain_repo ${lib.escapeShellArg borgRepoRootSnapshots} 'root-*'
      maintain_repo ${lib.escapeShellArg borgRepoPolylogueState} 'polylogue-state-*'
      if [ "$dry_run" = 0 ]; then
        date +%s > "$marker.tmp"
        mv "$marker.tmp" "$marker"
        if [ "$compact_due" = 1 ]; then
          date +%s > "$compact_marker.tmp"
          mv "$compact_marker.tmp" "$compact_marker"
        fi
      fi
    '';
  };
in
[
  # ─── Sinex content-store Borg job ───
  # The content stores live outside the /realm snapshot stream, so Borg reads
  # them in place. Stored files are never rewritten, which makes this safe
  # without a snapshot; `RequiresMountsFor` keeps the source mount
  # authoritative. The guard covers service AND timer: a timer whose service
  # does not exist is a failed start, not a backup.
  (lib.mkIf (sinexStorePaths != [ ]) (
    mkBackupJob "borgbackup-job-sinex-blobs" {
      description = "Back up the Sinex content stores into Borg";
      unit = {
        after = [
          "persist.mount"
          outerRealmMountUnit
        ];
        requires = [
          "persist.mount"
          outerRealmMountUnit
        ];
        unitConfig.RequiresMountsFor = sinexStorePaths;
      };
      serviceConfig.TimeoutStopSec = "15s";
      path = with pkgs; [
        borgbackup
        coreutils
        gnugrep
        util-linux
      ];
      timer = {
        onCalendar = "*-*-* 05:40:00";
        randomizedDelaySec = "10min";
        persistent = true;
      };
      script = ''
        set -euo pipefail
        ${mkBorgCommonScript borgRepoSinexBlobs}

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
          ${lib.escapeShellArgs sinexStorePaths}
        echo "sinex blob backup complete: $archive_name"

        # The borg-sinex-blobs-archive capture lane (this surface's
        # captures, above) gates freshness off this marker, same convention
        # as the btrbk drain jobs' "$label.last-success" (mkSnapshotDrainScript
        # above) -- without it, sinex-blobs had zero freshness gating despite
        # being on its own daily timer.
        install -d -m 0755 -o root -g root ${lib.escapeShellArg borgDrainStateRoot}
        marker=${lib.escapeShellArg "${borgDrainStateRoot}/sinex-blobs.last-success"}
        {
          printf 'archive=%s\n' "$archive_name"
          printf 'epoch=%s\n' "$(date +%s)"
        } | publish_backup_marker "$marker"
      '';
    }
  ))

  # ─── Polylogue nested-subvolume coverage (sinnix-3pvd) ───
  #
  # Two jobs cover state/polylogue, split the same way Sinex is split
  # between sinex-dump (logical dump of the live database) and
  # borgbackup-job-sinex-blobs (direct-path Borg of the content stores):
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
      # Not 04:15: the Polylogue Borg job below starts then and both read the
      # same state root.
      onCalendar = "*-*-* 01:30:00";
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

      done
    '';
  })

  # Direct-path borg covers the state root, except live SQLite files and the
  # append-only hook tree. SQLite is covered by the dump job above; hooks are
  # archived directly from a read-only state cut so writers can keep appending.
  # Failed provisional cuts remain in the private cache for owner recovery.
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
    serviceConfig = {
      TimeoutStartSec = "90min";
      TimeoutStopSec = "15s";
    };
    path = with pkgs; [
      borgbackup
      coreutils
      gnugrep
      util-linux
      btrfs-progs
    ];
    timer = {
      # Leave 105 minutes before the drain coordinator; a 90-minute service
      # deadline leaves time for Borg to stop and release its shared lock.
      # Do not catch up a missed wake near the drain window on late boot.
      onCalendar = "*-*-* 04:15:00";
      randomizedDelaySec = "5min";
      persistent = false;
    };
    script = ''
      set -euo pipefail
      ${mkBorgCommonScript borgRepoPolylogueState}

      install -d -m 0700 -o root -g root ${lib.escapeShellArg borgRepoPolylogueStatePath}
      recover_stale_borg_locks

      if [ ! -e ${lib.escapeShellArg "${borgRepoPolylogueStatePath}/config"} ]; then
        with_borg_lock borg init --encryption repokey-blake2 "$BORG_REPO"
      fi

      archive_name="polylogue-state-$(date -u +%Y%m%dT%H%M%SZ)"
      stage_root=${lib.escapeShellArg "${realmRoot}/state/cache/polylogue-backup-hooks"}
      install -d -m 0700 -o root -g root "$stage_root"
      install -d -m 0700 -o root -g root "$stage_root/cuts"
      echo "polylogue state backup phase: creating archive"
      with_borg_lock ${pkgs.python3}/bin/python3 ${./cut-polylogue-hooks.py} \
        ${lib.escapeShellArg polylogueStateRoot} "$stage_root/cuts" -- borg create \
        --compression auto,zstd,1 \
        --lock-wait ${toString borgLockWaitSec} \
        ${
          mkBorgExcludeArgs polylogueStateRoot (polylogueDbExcludes ++ [ ".salvage-internals-20261008" ])
        } \
        --exclude ${lib.escapeShellArg "${polylogueStateRoot}/hooks/**"} \
        "::$archive_name" \
        ${lib.escapeShellArg polylogueStateRoot}
      echo "polylogue state backup complete: $archive_name"

      install -d -m 0755 -o root -g root ${lib.escapeShellArg borgDrainStateRoot}
      marker=${lib.escapeShellArg "${borgDrainStateRoot}/polylogue-state.last-success"}
      {
        printf 'archive=%s\n' "$archive_name"
        printf 'epoch=%s\n' "$(date +%s)"
      } | publish_backup_marker "$marker"
    '';
  })

  # Active series retain frequent recent cuts; retired series retain monthly
  # milestones for at most a year, rather than an immortal independent quota.
  (mkBackupJob "borgbackup-maintenance" (
    maintenanceJob
    // {
      timer = {
        # After the nightly drain, with one retry for lock contention; a pass
        # is due every 20 hours, so the second attempt no-ops after a success.
        onCalendar = "*-*-* 03,04:50:00";
        persistent = true;
        randomizedDelaySec = "5min";
      };
    }
  ))
  (mkBackupJob "borgbackup-retention-plan" (
    maintenanceJob
    // {
      description = "Preview Borg retention changes without deleting archives";
      environment = maintenanceJob.environment // {
        SINNIX_BORG_MAINTENANCE_DRY_RUN = "1";
      };
    }
  ))
  (mkBackupJob "borgbackup-capacity" {
    description = "Record backup capacity and alert on shrinking headroom";
    unit = {
      after = [ outerRealmMountUnit ];
      requires = [ outerRealmMountUnit ];
    };
    serviceConfig.TimeoutStartSec = "30min";
    timer = {
      onCalendar = "*-*-* 0/6:45:00";
      persistent = true;
    };
    execStart = "${scriptPkgs.sinnix-backup-capacity}/bin/sinnix-backup-capacity --root ${lib.escapeShellArg (builtins.dirOf (builtins.dirOf borgRepoRealmPath))} --state ${lib.escapeShellArg "${borgDrainStateRoot}/capacity.json"}";
  })
]
