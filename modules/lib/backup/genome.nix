# The HDD genome subvolume is outside the Realm snapshot boundary.
{
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
let
  # Preserve inputs, supplied alignments, vendor files, source/WIP, manifests
  # and all analysis results. Only classified public resources and dependency
  # environments are waived; unfamiliar cache children remain covered.
  excluded = [
    "cache/reference"
    "cache/pgs_catalog"
    "cache/tools"
    "cache/pylibs"
    "cache/snpeff"
    "cache/gwas_sumstats"
    ".direnv"
  ];
in
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
        exclude = excluded;
        noncanonical = excluded;
      };
    }
  ))
]
