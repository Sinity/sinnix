# Internal backup component. Public options and shared policy live in modules/backup.nix.
{
  pkgs,
  lib,
  config,
  sinexBlobRepositoryPath,
  scriptPkgs,
  borgDrainStateRoot,
  borgIntegrityReceipt,
  realmCoverageAuditReceipt,
  realmSnapshots,
  realmCoveragePolicy,
  snapshotCoverage,
  btrfsImageRoot,
  btrfsImageMinBytes,
  borgRepoPersist,
  borgRepoRealm,
  borgRepoSinexBlobs,
  borgPassphrasePath,
  outerRealmMountUnit,
  borgCacheDir,
  protectedRealmArchivePaths,
  mkBackupJob,
  mkBorgCommonScript,
  realmExcludes,
  realmExcludeMatchesProtectedPath,
  mkSinexBeadsDrillScript,
}:
[
  {
    assertions =
      lib.optional (sinexBlobRepositoryPath != "") {
        assertion = lib.hasInfix sinexBlobRepositoryPath config.systemd.services.borgbackup-job-sinex-blobs.script;
        message = "Sinex CAS Borg backup must archive services.sinex.storage.blob.repositoryPath";
      }
      ++ [
        {
          assertion = lib.all (exclude: !realmExcludeMatchesProtectedPath exclude) realmExcludes;
          message = "The /realm Borg backup must not exclude a protected path: ${lib.concatStringsSep ", " protectedRealmArchivePaths}";
        }
      ];
  }

  # Weekly integrity checks verify repository segment CRCs, then advance
  # another partial check on persist and realm. The latter script retains its
  # historical "drill" name, but its scheduled default does not restore data.
  # These checks were merged into one unit from borgbackup-check.service and
  # sinnix-borg-drill.service (the separate Wed 04:00 timer was retired).
  (mkBackupJob "borgbackup-verify" {
    description = "Borg repository integrity checks with bounded partial passes";
    serviceConfig = {
      TimeoutStopSec = "15s";
      # The main checks total 3h; the no-argument partial-check script adds
      # 1h on persist and realm. Leave 30m for command and segment-boundary
      # overhead while ending before the next six-hour archive window.
      TimeoutStartSec = "4h30m";
    };
    environment = {
      BORG_PASSCOMMAND = "${pkgs.coreutils}/bin/cat ${borgPassphrasePath}";
      BORG_CACHE_DIR = borgCacheDir;
    };
    timer = {
      # This is after the morning audit and hook timer slots. Any operation
      # still running holds the shared lock, so this job skips instead of
      # blocking it. The 4h30m deadline ends before the 18:00 archive window.
      onCalendar = "Sun 13:00:00";
      persistent = false;
    };
    path = with pkgs; [
      borgbackup
      coreutils
      findutils
      gnugrep
      jq
      util-linux
    ];
    script = ''
      set -euo pipefail

      ${mkBorgCommonScript borgRepoPersist}
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
          | publish_backup_marker ${lib.escapeShellArg borgIntegrityReceipt}
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
      ${mkBorgCommonScript borgRepoRealm}
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

      # Additional partial repository checks (the historical
      # sinnix-borg-drill.service, with its own weekly timer, was merged here).
      # The no-argument default runs repository-only checks for persist and
      # realm; it does not restore or pass --verify-data. It shares the same
      # receipt path as the manual `sinnix borg-drill [--verify-data]` verb.
      # The repository checks above
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

  # The shared Borg lock keeps the selected acknowledged snapshot from being
  # pruned by a drain while this independent full comparison runs.
  (mkBackupJob "borgbackup-coverage-audit-realm" {
    description = "Independently compare one acknowledged realm snapshot with Borg";
    unit = {
      after = [ "realm.mount" outerRealmMountUnit ];
      requires = [ "realm.mount" outerRealmMountUnit ];
    };
    serviceConfig = {
      # The independent comparison yields before the next archive window.
      TimeoutStartSec = "5h";
      TimeoutStopSec = "15s";
    };
    timer = {
      # A missed lock window retries the next day; a successful comparison
      # makes the other daily wakes no-ops until its seven-day age expires.
      onCalendar = "*-*-* 06:35:00";
      persistent = false;
    };
    path = with pkgs; [ borgbackup btrfs-progs coreutils util-linux ];
    script = ''
      set -euo pipefail
      ${mkBorgCommonScript borgRepoRealm}
      if ${snapshotCoverage} audit-status ${lib.escapeShellArg realmCoverageAuditReceipt} \
        ${realmCoveragePolicy} 604800 >/dev/null 2>&1; then
        exit 0
      fi
      acquire_borg_global_lock_or_fail "realm independent full audit"
      install -d -m 0755 ${lib.escapeShellArg borgDrainStateRoot}
      audit="$(${snapshotCoverage} audit \
        ${lib.escapeShellArg "${borgDrainStateRoot}/realm.latest-archived"} \
        ${lib.escapeShellArg realmSnapshots} ${realmCoveragePolicy})"
      printf '%s\n' "$audit" | publish_backup_marker ${lib.escapeShellArg realmCoverageAuditReceipt}
      echo "backup_phase=independent_full_audit label=realm $(printf '%s' "$audit" | ${pkgs.jq}/bin/jq -r '"elapsed_seconds=\(.verification_seconds) source_hashed_bytes=\(.source_hashed_bytes) archive_content_verified_bytes=\(.archive_content_verified_bytes)"')"
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
    # Each filesystem gets its own 40-minute window. A hung first capture
    # cannot consume the other label's window or an interactive morning.
    # The backup class already applies idle I/O scheduling and bandwidth
    # limits. A successful image peaked at 2.2G in 2026-08 measurements.
    serviceConfig = {
      TimeoutStartSec = "85min";
      TimeoutStopSec = "15s";
      MemoryHigh = "3G";
      MemoryMax = "5G";
      MemorySwapMax = 0;
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

      # btrfs-image writes to "$out.tmp" and renames only on success, so a
      # run killed mid-capture leaves a multi-GB partial file that is not an
      # image of anything. Only that in-flight debris is swept; finished
      # images (no .tmp suffix) are kept indefinitely.
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
      # steady small-file writes). Retry short failures within a fixed window.
      capture_image() {
        label="$1"
        device="$2"
        out="${btrfsImageRoot}/$label-$stamp.btrfs-image"
        tmp="$out.tmp"
        attempt=1
        deadline=$(( $(date +%s) + 40 * 60 ))

        while [ "$attempt" -le 3 ]; do
          remaining=$(( deadline - $(date +%s) ))
          if [ "$remaining" -le 0 ]; then
            break
          fi
          rm -f "$tmp"
          echo "btrfs-metadata-image-backup: $label attempt $attempt started (budget ''${remaining}s)"
          if timeout --signal=TERM --kill-after=15s "''${remaining}s" btrfs-image -c 9 -t 1 "$device" "$tmp"; then
            # errexit is disabled inside a function whose caller is an `if`
            # condition, so nothing from here to the rename is covered by
            # `set -e`: a chmod or mv that failed (full or read-only
            # /outer-realm) used to fall through to `return 0` and the unit
            # reported a capture that was not on disk. Every step is checked
            # by hand, and the image is only "captured" once it is readable
            # at its final name.
            size="$(stat -c %s "$tmp" 2>/dev/null || echo 0)"
            if [ "$size" -ge ${toString btrfsImageMinBytes} ]; then
              if chmod 0600 "$tmp" && mv -- "$tmp" "$out"; then
                echo "btrfs-metadata-image-backup: $label captured $label-$stamp.btrfs-image ($size bytes)"
                return 0
              fi
              echo "btrfs-metadata-image-backup: $label could not be published to $out" >&2
            else
              echo "btrfs-metadata-image-backup: $label produced a degenerate image ($size bytes, floor ${toString btrfsImageMinBytes})" >&2
            fi
          else
            status="$?"
            echo "btrfs-metadata-image-backup: $label attempt $attempt exited $status (124 means deadline exceeded)" >&2
          fi
          attempt=$((attempt + 1))
          if [ "$attempt" -gt 3 ]; then
            break
          fi
          remaining=$(( deadline - $(date +%s) ))
          if [ "$remaining" -le 0 ]; then
            break
          fi
          delay=$((45 * (attempt - 1)))
          if [ "$delay" -gt "$remaining" ]; then
            delay="$remaining"
          fi
          sleep "$delay"
        done

        rm -f "$tmp"
        echo "btrfs-metadata-image-backup: $label failed after $((attempt - 1)) attempts within its 40-minute window; previous images retained" >&2
        return 1
      }

      # Per-label accounting: a combined exit code hides which target is
      # actually broken. persist goes first -- see the comment above.
      rc=0
      if ! capture_image persist /dev/disk/by-uuid/f4782d9f-aabe-408e-b18b-2f2baa9e9a02; then
        rc=1
      fi
      if ! capture_image realm /dev/disk/by-uuid/43701cf7-7880-4e0c-9725-b6e12d91898a; then
        rc=1
      fi

      exit "$rc"
    '';
  })

  # The realm archive covers Sinex's external Beads task store. The drill
  # extracts that store into scratch and reads a task and commit offline.
  #
  # Its failure notification comes from the renderer, not from a hand-wired
  # onFailure: the drill is deliberately not an observed surface (its
  # evidence is the drill log, not unit state), so runtime.nix's
  # surface-driven attachment skips it and mkScheduledJob's does not.
  (mkBackupJob "sinnix-borg-beads-drill" {
    description = "Restore drill for the external Sinex Beads task store";
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
]
