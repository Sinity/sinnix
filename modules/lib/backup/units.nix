# Every backup unit and timer. Each runs one `sinnix-backup` command, which
# reads /etc/sinnix/backup.json; modules/backup.nix builds it.
{
  lib,
  pkgs,
  config,
  scriptPkgs,
  backupConfig,
  borgRepoRoot,
  genomeRoot,
  genomeSnapshots,
  dumpUnits,
  archiveUnits,
  finalUnits,
}:
let
  sinnixBackup = command: "${scriptPkgs.sinnix-backup}/bin/sinnix-backup ${command}";
  outerRealmMountUnit = "outer\\x2drealm.mount";
  # Ordered after, and requiring, these mounts and the backup disk.
  onBackupDisk =
    mounts:
    let
      units = mounts ++ [ outerRealmMountUnit ];
    in
    {
      after = units;
      requires = units;
    };
  timeouts = start: {
    TimeoutStartSec = start;
    TimeoutStopSec = "15s";
  };
  calendar = onCalendar: persistent: { inherit onCalendar persistent; };
  stateDirectory = backupConfig.state_directory;
  repositoryPath = name: backupConfig.repositories.${name}.path;
  inherit (backupConfig.jobs) polylogue;
  hourlyCacheDirectory = backupConfig.hourly_cache_directory;
  persistBind = backupConfig.sources.persist.bind_path;
  realmBind = backupConfig.sources.realm.bind_path;
  sinexStorePaths = backupConfig.jobs.sinex_store_paths;

  # Activation never restarts a job: a switch mid-run would abandon a bind
  # mount and a held Borg lock. Resources come from the unit's own surface.
  mkBackupJob =
    name:
    { description, ... }@job:
    lib.sinnix.mkScheduledJob
      {
        inherit config description;
        unitName = name;
        surface = config.sinnix.runtime.units.${name};
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

  maintenanceJob = {
    description = "Prune and compact Borg backup repositories";
    unit = onBackupDisk [ ];
    serviceConfig = timeouts "8h";
    execStart = sinnixBackup "maintain";
  };
in
[
  {
    system.activationScripts.borgRepositoryDirectories.text = ''
      ${pkgs.coreutils}/bin/install -d -m 0750 -o root -g users ${borgRepoRoot}
      ${pkgs.coreutils}/bin/install -d -m 0700 -o root -g root ${repositoryPath "persist"}
      ${pkgs.coreutils}/bin/install -d -m 0700 -o root -g root ${repositoryPath "realm"}
      ${pkgs.coreutils}/bin/install -d -m 0700 -o root -g root ${repositoryPath "root-snapshots"}
      ${pkgs.coreutils}/bin/install -d -m 0700 -o root -g root ${repositoryPath "sinex-blobs"}
      ${pkgs.coreutils}/bin/install -d -m 0700 -o root -g root ${repositoryPath "polylogue-state"}
    '';

    # The Borg cache survives reboots, so archives stay incremental.
    systemd.tmpfiles.rules = lib.mkAfter [
      "d ${backupConfig.sources.realm.snapshot_directory} 0750 root users -"
      # The operator-run Polylogue dump job cannot create this under root's db-dumps.
      "d ${polylogue.dump_root} 0700 sinity users -"
      "d ${backupConfig.sources.persist.snapshot_directory} 0750 root users -"
      "d ${builtins.dirOf persistBind} 0700 root root -"
      "d ${persistBind} 0700 root root -"
      "d ${realmBind} 0700 root root -"
      "d ${borgRepoRoot} 0750 root users -"
      "d ${repositoryPath "root-snapshots"} 0700 root root -"
      "d ${backupConfig.cache_directory} 0700 root root -"
      "d ${stateDirectory} 0750 root users -"
      # Exact record directories, created before the operator's probes run.
      "d ${stateDirectory}/realm.latest-archived.by-snapshot 0750 root users -"
      "d ${stateDirectory}/persist.latest-archived.by-snapshot 0750 root users -"
      "d ${stateDirectory}/genome.latest-archived.by-snapshot 0750 root users -"
      "f ${backupConfig.lock_path} 0600 root root -"
    ];
  }

  # After every snapshotted volume is mounted; the genome HDD mounts slowly.
  (mkBackupJob "btrbk" {
    description = "btrbk btrfs snapshot";
    unit = {
      after = [
        "persist.mount"
        "realm.mount"
      ];
      unitConfig.RequiresMountsFor = lib.optional (genomeRoot != null) genomeRoot;
    };
    execStart = sinnixBackup "take-snapshots";
    serviceConfig = {
      TimeoutStopSec = "15s";
      ExecStartPre = lib.optional (
        genomeRoot != null
      ) "${pkgs.coreutils}/bin/install -d -m 0750 ${genomeSnapshots}";
    };
    # One restore point per drain window.
    timer = calendar "*-*-* 00,06,12,18:00:00" false;
  })
  (mkBackupJob "borgbackup-job-persist" {
    description = "Drain /persist btrbk snapshots into Borg";
    unit = onBackupDisk [ "persist.mount" ];
    # A timeout keeps unarchived snapshots; the next wake resumes the queue.
    serviceConfig = timeouts "4h";
    execStart = sinnixBackup "drain persist";
  })
  (mkBackupJob "borgbackup-job-realm" {
    description = "Drain /realm btrbk snapshots into Borg";
    unit = onBackupDisk [ "realm.mount" ];
    serviceConfig = timeouts "24h";
    execStart = sinnixBackup "drain realm";
  })
  (lib.mkIf (genomeRoot != null) (
    mkBackupJob "borgbackup-job-genome" {
      description = "Archive verified genome snapshots from the HDD";
      unit = onBackupDisk [ ] // {
        unitConfig.RequiresMountsFor = [
          genomeRoot
          genomeSnapshots
        ];
      };
      serviceConfig = timeouts "24h" // {
        ExecStartPre = [ "${pkgs.coreutils}/bin/install -d -m 0750 ${genomeSnapshots}" ];
      };
      execStart = sinnixBackup "drain genome";
    }
  ))

  # Holds no Borg lock while a child runs; stopping it stops the children.
  (mkBackupJob "borgbackup-drain-coordinator" {
    description = "Run nightly dumps, snapshot archives and backup maintenance in sequence";
    unit.unitConfig.PropagatesStopTo = map (name: "${name}.service") (
      dumpUnits ++ [ "btrbk" ] ++ archiveUnits ++ finalUnits
    );
    # The children's budgets plus the dump and maintenance phases.
    serviceConfig = timeouts (if genomeRoot == null then "56h15m" else "80h15m");
    execStart = sinnixBackup "nightly";
    # The boot trigger also resumes a night interrupted after the calendar fired.
    timer = calendar "*-*-* 03:05:00" true // { onBootSec = "45min"; };
  })

  # Root snapshots have their own repository, so they never hold up /persist.
  (mkBackupJob "borgbackup-root-snapshots" {
    description = "Archive ephemeral root snapshots to borg";
    unit = {
      after = [
        "persist.mount"
        outerRealmMountUnit
      ];
      requires = [ outerRealmMountUnit ];
    };
    serviceConfig = timeouts "4h";
    execStart = sinnixBackup "root-snapshots";
  })

  # Retained Sinex stores are immutable, so Borg reads them in place.
  (lib.mkIf (sinexStorePaths != [ ]) (
    mkBackupJob "borgbackup-job-sinex-blobs" {
      description = "Back up retained Sinex predecessor stores into Borg";
      unit = onBackupDisk [ "persist.mount" ] // {
        unitConfig.RequiresMountsFor = sinexStorePaths;
      };
      serviceConfig = timeouts "6h";
      execStart = sinnixBackup "sinex-stores";
    }
  ))

  # Consistent dumps of Polylogue's live databases, as the operator.
  (mkBackupJob "polylogue-sqlite-backup" {
    description = "Back up Polylogue SQLite databases";
    unit = {
      after = [ "realm.mount" ];
      requires = [ "realm.mount" ];
      unitConfig.RequiresMountsFor = [
        polylogue.state_root
        polylogue.dump_root
      ];
    };
    user = polylogue.user;
    serviceConfig = {
      Group = "users";
      TimeoutStartSec = "30min";
    };
    execStart = sinnixBackup "polylogue-dumps";
  })

  # Polylogue state except the dumped databases, hooks from a read-only cut.
  (mkBackupJob "borgbackup-job-polylogue-state" {
    description = "Back up Polylogue state (blob CAS and non-live files) and the purchased vectors into Borg";
    unit = onBackupDisk [ "realm.mount" ] // {
      unitConfig.RequiresMountsFor = [
        polylogue.state_root
        polylogue.paid_vector_root
      ];
    };
    serviceConfig = timeouts "90min";
    execStart = sinnixBackup "polylogue-state";
  })
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
      unitConfig.RequiresMountsFor = [ hourlyCacheDirectory ];
    };
    serviceConfig = timeouts "45min";
    execStart = sinnixBackup "hourly-persist";
    timer = calendar "*-*-* *:17:00" false;
  })
  (mkBackupJob "borgbackup-job-live-small" {
    description = "Archive Polylogue's archive database, Beads and Sinex spools into Borg every hour";
    unit = onBackupDisk [ "realm.mount" ] // {
      unitConfig.RequiresMountsFor = [
        backupConfig.jobs.hourly.tasks_root
        hourlyCacheDirectory
      ];
    };
    serviceConfig = timeouts "45min";
    execStart = sinnixBackup "hourly-live";
    timer = calendar "*-*-* *:47:00" false;
  })
  (mkBackupJob "borgbackup-maintenance" maintenanceJob)
  (mkBackupJob "borgbackup-retention-plan" (
    maintenanceJob
    // {
      description = "Preview Borg retention changes without deleting archives";
      execStart = sinnixBackup "maintain --dry-run";
    }
  ))
  (mkBackupJob "borgbackup-capacity" {
    description = "Record backup capacity and forecast when the destination fills";
    unit = onBackupDisk [ ];
    serviceConfig.TimeoutStartSec = "30min";
    timer = calendar "*-*-* 0/6:45:00" true;
    execStart = "${scriptPkgs.sinnix-backup-capacity}/bin/sinnix-backup-capacity --root ${lib.escapeShellArg (builtins.dirOf (builtins.dirOf (repositoryPath "realm")))} --state ${lib.escapeShellArg "${stateDirectory}/capacity.json"} --compact-marker ${lib.escapeShellArg "${stateDirectory}/compact.last-success"}";
  })

  # Expires local dumps only after their archived copy restores.
  (mkBackupJob "borgbackup-local-dumps" {
    description = "Expire local daily dumps after complete matching Borg restores";
    unit = onBackupDisk [ ];
    serviceConfig.TimeoutStartSec = "2h";
    execStart = sinnixBackup "expire-dumps";
  })
  (mkBackupJob "borgbackup-verify" {
    description = "Borg repository integrity checks with bounded partial passes";
    # Checks, partial checks and overhead end before the 18:00 archive window.
    serviceConfig = timeouts "4h30m";
    execStart = sinnixBackup "check-repositories";
    timer = calendar "Sun 13:00:00" false;
  })
  (mkBackupJob "borgbackup-coverage-audit-realm" {
    description = "Compare acknowledged Realm metadata and a bounded content sample";
    unit = onBackupDisk [ "realm.mount" ];
    # A sampled pass takes minutes; the limit frees the pinned snapshot if one hangs.
    serviceConfig = timeouts "2h";
    execStart = sinnixBackup "audit-realm";
  })

  # Not an observed surface, so mkScheduledJob attaches the failure notice.
  (mkBackupJob "sinnix-borg-beads-check" {
    description = "Restore check for every Beads task store";
    unit = {
      reloadIfChanged = false;
      stopIfChanged = false;
    }
    // onBackupDisk [ ];
    serviceConfig = {
      PrivateTmp = true;
      # Up to three hours waiting for the Borg lock, then the restores.
      TimeoutStartSec = "4h";
    };
    execStart = sinnixBackup "check-beads-restore";
    # After the nightly run releases the lock, clear of Sunday's check.
    timer = calendar "Thu 12:00:00" true;
  })
]
