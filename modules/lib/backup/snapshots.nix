# Internal backup component. Public options and shared policy live in modules/backup.nix.
{
  snapshotCoverage,
  genomeCoveragePolicy,
  genomeAcquisitionInventory,
  pkgs,
  lib,
  borgRepoRoot,
  polylogueBackupRoot,
  realmSnapshots,
  persistSnapshots,
  borgSnapshotBindRoot,
  borgPersistSnapshotBind,
  borgRealmSnapshotBind,
  borgDrainStateRoot,
  borgRepoPersistPath,
  borgRepoRealmPath,
  borgRepoRootSnapshotsPath,
  borgRepoSinexBlobsPath,
  borgRepoPolylogueStatePath,
  borgCacheDir,
  borgGlobalLock,
  mkBackupJob,
  genomeRoot,
  genomeSnapshots,
}:
[
  {
    system.activationScripts.borgRepositoryDirectories.text = ''
      ${pkgs.coreutils}/bin/install -d -m 0750 -o root -g users ${borgRepoRoot}
      ${pkgs.coreutils}/bin/install -d -m 0700 -o root -g root ${borgRepoPersistPath}
      ${pkgs.coreutils}/bin/install -d -m 0700 -o root -g root ${borgRepoRealmPath}
      ${pkgs.coreutils}/bin/install -d -m 0700 -o root -g root ${borgRepoRootSnapshotsPath}
      ${pkgs.coreutils}/bin/install -d -m 0700 -o root -g root ${borgRepoSinexBlobsPath}
      ${pkgs.coreutils}/bin/install -d -m 0700 -o root -g root ${borgRepoPolylogueStatePath}
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
      "d ${borgCacheDir} 0700 root root -"
      "d ${borgDrainStateRoot} 0750 root users -"
      # Exact metadata namespaces: migrate existing receipts before operator
      # probes run, without traversing private sources or changing file modes.
      "d ${borgDrainStateRoot}/realm.latest-archived.by-snapshot 0750 root users -"
      "d ${borgDrainStateRoot}/persist.latest-archived.by-snapshot 0750 root users -"
      "d ${borgDrainStateRoot}/genome.latest-archived.by-snapshot 0750 root users -"
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
    unit = {
      after = [
        "persist.mount"
        "realm.mount"
      ];
      unitConfig.RequiresMountsFor = lib.optional (genomeRoot != null) genomeRoot;
    };
    path = with pkgs; [
      coreutils
      btrfs-progs
      util-linux
    ];
    script = ''
      ${pkgs.btrbk}/bin/btrbk --quiet --preserve-snapshots run
      ${lib.optionalString (genomeRoot != null) ''
        # Every successful acquisition, including unchanged onchange sources,
        # publishes only immutable metadata for the unprivileged health reader.
        install -d -m 0750 -o root -g users ${lib.escapeShellArg borgDrainStateRoot}
        inventory=${lib.escapeShellArg genomeAcquisitionInventory}
        temporary=$(mktemp "$inventory.XXXXXXXX")
        trap 'rm -f -- "$temporary"' EXIT
        ${snapshotCoverage} observe-acquisitions ${lib.escapeShellArg genomeSnapshots} 'genome.*' ${genomeCoveragePolicy} \
          --source ${lib.escapeShellArg (toString genomeRoot)} > "$temporary"
        chmod 0644 "$temporary"
        sync -f "$temporary"
        mv -f "$temporary" "$inventory"
        sync -f ${lib.escapeShellArg borgDrainStateRoot}
        trap - EXIT
      ''}
    '';
    serviceConfig = {
      TimeoutStopSec = "15s";
      ExecStartPre = lib.optional (
        genomeRoot != null
      ) "${pkgs.coreutils}/bin/install -d -m 0750 ${genomeSnapshots}";
    };
    timer = {
      # Create one restore point per Borg drain window. Half-hourly snapshots
      # accumulated without bound when archive verification could not finish.
      onCalendar = "*-*-* 00,06,12,18:00:00";
      persistent = false;
    };
  })

]
