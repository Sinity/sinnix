# Local dump expiry is independent of source acquisition and archive admission.
{
  coordinatorPolicies,
  pkgs,
  lib,
  realmRoot,
  realmSnapshots,
  realmCoveragePolicy,
  snapshotCoverage,
  borgDrainStateRoot,
  borgRepoRealm,
  outerRealmMountUnit,
  scriptPkgs,
  mkBackupJob,
  mkBorgCommonScript,
}:
[
  (mkBackupJob "borgbackup-local-dumps" {
    description = "Expire local daily dumps after complete matching Borg restores";
    unit = {
      after = [ outerRealmMountUnit ];
      requires = [ outerRealmMountUnit ];
    };
    serviceConfig.TimeoutStartSec = "2h";
    path = with pkgs; [
      borgbackup
      coreutils
      gnused
      util-linux
      btrfs-progs
      jq
    ];
    script = ''
      set -euo pipefail
      ${mkBorgCommonScript borgRepoRealm}
      acquire_borg_global_lock_or_skip "local dump expiry"
      marker=${lib.escapeShellArg "${borgDrainStateRoot}/realm.latest-archived"}
      # The admitted immutable source must still qualify under current policy.
      ${snapshotCoverage} acknowledged --policy ${realmCoveragePolicy} -- \
        ${lib.escapeShellArg realmSnapshots} 'realm.*' "$marker" realm -coverage-v3 >/dev/null
      archive="$(sed -n 's/^archive=//p' "$marker")"
      proof="$(sed -n 's/^coverage=//p' "$marker")"
      ${scriptPkgs.sinnix-borg-prune-dumps}/bin/sinnix-borg-prune-dumps \
        --root ${lib.escapeShellArg "${realmRoot}/state/db-dumps"} \
        --archive "$archive" \
        --archive-id "$(printf '%s' "$proof" | jq -er .archive_id)" \
        --snapshot-uuid "$(printf '%s' "$proof" | jq -er .snapshot_uuid)" \
        --apply
      {
        printf 'epoch=%s\n' "$(date +%s)"
        printf 'policy_sha256=%s\n' ${lib.escapeShellArg coordinatorPolicies.localDumps}
      } | publish_backup_marker ${lib.escapeShellArg "${borgDrainStateRoot}/local-dumps.last-success"}
    '';
  })
]
