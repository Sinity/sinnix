# The HDD genome subvolume is outside the Realm snapshot boundary.
{
  genomeExcludes,
  pkgs,
  lib,
  genomeRoot,
  genomeSnapshots,
  neoOuterRealm,
  borgRepoRealm,
  borgRepoRealmPath,
  outerRealmMountUnit,
  mkBackupJob,
  mkSnapshotDrainScript,
}:
[
  (lib.mkIf (genomeRoot != null) {
    assertions = [
      {
        assertion = lib.hasPrefix "${neoOuterRealm}/" (toString genomeRoot);
        message = "The genome backup source must be a subvolume on neo-outer-realm.";
      }
    ];
  })
  (lib.mkIf (genomeRoot != null) (
    mkBackupJob "borgbackup-job-genome" {
      description = "Archive verified genome snapshots from the HDD";
      unit = {
        after = [ outerRealmMountUnit ];
        requires = [ outerRealmMountUnit ];
        unitConfig.RequiresMountsFor = [
          genomeRoot
          genomeSnapshots
        ];
      };
      serviceConfig = {
        TimeoutStartSec = "24h";
        TimeoutStopSec = "15s";
        ExecStartPre = [ "${pkgs.coreutils}/bin/install -d -m 0750 ${genomeSnapshots}" ];
      };
      path = with pkgs; [
        borgbackup
        btrfs-progs
        coreutils
        findutils
        gnugrep
        util-linux
      ];
      script = mkSnapshotDrainScript {
        label = "genome";
        repo = borgRepoRealm;
        repoPath = borgRepoRealmPath;
        snapshotDir = genomeSnapshots;
        snapshotGlob = "genome.*";
        bindTarget = "/run/borgbackup-snapshot-inputs/genome";
        archivePrefix = "genome";
        producerProof = true;
        exclude = genomeExcludes;
        noncanonical = genomeExcludes;
      };
    }
  ))
]
