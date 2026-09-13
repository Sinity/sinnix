# Internal backup component. Public options and shared policy live in modules/backup.nix.
{
  pkgs,
  lib,
  sinexBlobRepositoryPath,
  scriptPkgs,
  username,
  polylogueStateRoot,
  polylogueBackupRoot,
  machineTelemetryBackupRoot,
  machineTelemetryBackupMarker,
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
[
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
          ${lib.escapeShellArg sinexBlobRepositoryPath}
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
      util-linux
    ];
    timer = {
      onCalendar = "*-*-* 05:55:00";
      randomizedDelaySec = "10min";
      persistent = true;
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

      ${mkBorgCommonScript borgRepoRealm}
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

  # Backup policy is indefinite lossless retention: no archive is deleted
  # because of its age, count or size. Compaction only reclaims segment
  # space that no archive references, so every archive ever written stays
  # addressable and restorable.
  (mkBackupJob "borgbackup-maintenance" {
    description = "Compact Borg backup repositories";
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

      ${borgStaleLockRecovery}

      maintain_repo() {
        repo="$1"
        if [ ! -e "''${repo#file://}/config" ]; then
          echo "Skipping uninitialized repo $repo"
          return
        fi

        acquire_borg_global_lock_or_skip "Borg maintenance"
        recover_stale_borg_locks "$repo"
        with_borg_lock borg compact --lock-wait ${toString borgLockWaitSec} "$repo"
      }

      maintain_repo ${lib.escapeShellArg borgRepoPersist}
      maintain_repo ${lib.escapeShellArg borgRepoRealm}
      maintain_repo ${lib.escapeShellArg borgRepoSinexBlobs}
      maintain_repo ${lib.escapeShellArg borgRepoRootSnapshots}
      maintain_repo ${lib.escapeShellArg borgRepoPolylogueState}
    '';
  })

]
