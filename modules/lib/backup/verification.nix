# Internal backup component. Public options and shared policy live in modules/backup.nix.
{
  pkgs,
  lib,
  config,
  sinexStorePaths,
  scriptPkgs,
  borgDrainStateRoot,
  borgIntegrityReceipt,
  realmCoverageAuditReceipt,
  realmSnapshots,
  realmCoveragePolicy,
  snapshotCoverage,
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
  mkSinexBeadsCheckScript,
}:
[
  {
    assertions =
      lib.optional (sinexStorePaths != [ ]) {
        assertion = lib.all (
          path: lib.hasInfix path config.systemd.services.borgbackup-job-sinex-blobs.script
        ) sinexStorePaths;
        message = "The sinex-blobs Borg job must archive every Sinex content store (services.sinex.storeDir and sinnix.services.sinex.retainedStores)";
      }
      ++ [
        {
          assertion = lib.all (exclude: !realmExcludeMatchesProtectedPath exclude) realmExcludes;
          message = "The /realm Borg backup must not exclude a protected path: ${lib.concatStringsSep ", " protectedRealmArchivePaths}";
        }
      ];
  }

  # Weekly integrity checks verify repository segment CRCs, then advance
  # another partial check on persist and realm (sinnix-borg-check), whose
  # scheduled default does not restore data.
  # These checks were merged into one unit from borgbackup-check.service and
  # sinnix-borg-check.service (the separate Wed 04:00 timer was retired).
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
      # later sinnix-borg-check failure (which is a separate concern, not part of
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
      # and starving the nightly drain.
      ${pkgs.borgbackup}/bin/borg check --repository-only --max-duration 1800 ${borgRepoPersist}
      ${pkgs.borgbackup}/bin/borg check --repository-only --max-duration 7200 ${borgRepoRealm}
      ${pkgs.borgbackup}/bin/borg check --repository-only --max-duration 1800 ${borgRepoSinexBlobs}

      trap - EXIT
      write_integrity_receipt completed

      # Additional partial repository checks (the historical
      # sinnix-borg-check.service, with its own weekly timer, was merged here).
      # The no-argument default runs repository-only checks for persist and
      # realm; it does not restore or pass --verify-data. It shares the same
      # receipt path as the manual `sinnix borg-check [--verify-data]` verb.
      # The repository checks above
      # release the global Borg lock here (by closing fd 9) before
      # invoking it: sinnix-borg-check does its own `exec 9>...; flock -n`
      # in a fresh process against the same lock file, which would
      # otherwise always see the lock as already held by this script and
      # skip -- a re-entrant flock is per-open-file-description, not
      # per-process-tree.
      exec 9>&-
      ${scriptPkgs.sinnix-borg-check}/bin/sinnix-borg-check
    '';
  })

  # Routine source coverage is metadata plus a bounded content sample. The
  # prior full-content receipt remains historical evidence, never overwritten
  # by this weaker proof. A snapshot-directory flock keeps the snapshot in place while create
  # and drain operations continue under their existing native Borg locks.
  (mkBackupJob "borgbackup-coverage-audit-realm" {
    description = "Compare acknowledged Realm metadata and a bounded content sample";
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
    serviceConfig = {
      # A sampled pass takes minutes (each Borg child is capped at 300 s,
      # content at 128 files and one GiB); the cap only frees the pinned
      # snapshot if a pass hangs.
      TimeoutStartSec = "2h";
      TimeoutStopSec = "15s";
    };
    path = with pkgs; [
      borgbackup
      btrfs-progs
      coreutils
      util-linux
    ];
    script = ''
      set -euo pipefail
      ${mkBorgCommonScript borgRepoRealm}
      if ${snapshotCoverage} audit-status ${lib.escapeShellArg realmCoverageAuditReceipt} \
        ${realmCoveragePolicy} 604800 --mode sampled >/dev/null 2>&1; then
        exit 0
      fi
      install -d -m 0755 ${lib.escapeShellArg borgDrainStateRoot}
      if ! acquire_borg_global_lock_or_fail "realm coverage selection"; then
        printf '{"status":"deferred","reason":"borg-lock-contention","epoch":%s}\n' "$(date +%s)" \
          | publish_backup_marker ${lib.escapeShellArg "${borgDrainStateRoot}/realm.independent-coverage-audit-attempt.json"}
        echo "backup_phase=independent_coverage_audit status=deferred reason=borg-lock-contention remains_due=true"
        exit 0
      fi
      export TMPDIR=${lib.escapeShellArg "${borgCacheDir}/coverage-scratch"}
      install -d -m 0700 "$TMPDIR"
      selection="$(mktemp "$TMPDIR/selection.XXXXXXXX")"
      trap 'rm -f -- "$selection"' EXIT
      if [ -f ${lib.escapeShellArg "${borgDrainStateRoot}/realm.latest-archived"} ]; then
        cp -- ${lib.escapeShellArg "${borgDrainStateRoot}/realm.latest-archived"} "$selection"
      else
        rm -f -- "$selection"
      fi
      readiness="$(${snapshotCoverage} audit-ready "$selection" ${realmCoveragePolicy})"
      if [ "$(printf '%s' "$readiness" | ${pkgs.jq}/bin/jq -r '.ready')" != true ]; then
        printf '%s' "$readiness" | ${pkgs.jq}/bin/jq --argjson epoch "$(date +%s)" '. + {status:"deferred",epoch:$epoch}' \
          | publish_backup_marker ${lib.escapeShellArg "${borgDrainStateRoot}/realm.independent-coverage-audit-attempt.json"}
        echo "backup_phase=independent_coverage_audit status=deferred remains_due=true"
        exit 0
      fi
      snapshot="$(printf '%s' "$readiness" | ${pkgs.jq}/bin/jq -r '.snapshot')"
      exec 8<${lib.escapeShellArg realmSnapshots}/"$snapshot"
      if ! flock -n -s 8; then
        echo "backup_phase=independent_coverage_audit status=deferred reason=snapshot-in-use remains_due=true"
        exit 0
      fi
      # The selected marker is immutable for this operation. FD 8 protects
      # its source from retirement; native Borg locking still protects archives.
      exec 9>&-
      audit="$(${snapshotCoverage} audit "$selection" \
        ${lib.escapeShellArg realmSnapshots} ${realmCoveragePolicy} \
        --mode sampled --sample-bytes 1073741824 --sample-files 128 \
        --previous-receipt ${lib.escapeShellArg realmCoverageAuditReceipt})"
      printf '%s\n' "$audit" | publish_backup_marker ${lib.escapeShellArg realmCoverageAuditReceipt}
      echo "backup_phase=independent_coverage_audit label=realm $(printf '%s' "$audit" | ${pkgs.jq}/bin/jq -r '"elapsed_seconds=\(.verification_seconds) sampled_files=\(.sampled_files) source_hashed_bytes=\(.source_hashed_bytes) archive_content_verified_bytes=\(.archive_content_verified_bytes) content_coverage=\(.content_coverage)"')"
    '';
  })

  # The realm archive covers Sinex's external Beads task store. This restore
  # check extracts that store into scratch and reads a task and commit offline.
  #
  # Its failure notification comes from the renderer, not from a hand-wired
  # onFailure: the check is deliberately not an observed surface (its
  # evidence is its log, not unit state), so runtime.nix's
  # surface-driven attachment skips it and mkScheduledJob's does not.
  (mkBackupJob "sinnix-borg-beads-check" {
    description = "Restore check for the external Sinex Beads task store";
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
      # integrity check on Sunday (borgbackup-verify).
      onCalendar = "Thu 05:00:00";
      persistent = true;
    };
    script = mkSinexBeadsCheckScript;
  })
]
