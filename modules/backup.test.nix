{
  lib,
  mountTmpfsRoots,
  baseTestConfig,
  ...
}:
{
  name = "backup-btrbk";
  modules = [
    mountTmpfsRoots
    baseTestConfig
    (
      { ... }:
      {
        networking.hostName = "backup-test";
      }
    )
  ];
  assertions =
    config:
    let
      hasConf = config.environment.etc ? "btrbk/btrbk.conf";
      conf = if hasConf then config.environment.etc."btrbk/btrbk.conf".text else "";
      btrbkService = config.systemd.services.btrbk.serviceConfig;
      btrbkTimer = config.systemd.timers.btrbk.timerConfig;
      realmBorgUnit = config.systemd.services.borgbackup-job-realm;
      persistBorgUnit = config.systemd.services.borgbackup-job-persist;
      realmBorgService = config.systemd.services.borgbackup-job-realm.serviceConfig;
      persistBorgService = config.systemd.services.borgbackup-job-persist.serviceConfig;
      realmBorgTimer = config.systemd.timers.borgbackup-job-realm.timerConfig;
      persistBorgTimer = config.systemd.timers.borgbackup-job-persist.timerConfig;
      realmBorgPath = config.systemd.paths.borgbackup-job-realm.pathConfig;
      persistBorgPath = config.systemd.paths.borgbackup-job-persist.pathConfig;
      borgCheckService = config.systemd.services.borgbackup-check.serviceConfig;
      borgCheckTimer = config.systemd.timers.borgbackup-check.timerConfig;
      borgMaintenanceService = config.systemd.services.borgbackup-maintenance;
      borgMaintenanceServiceConfig = borgMaintenanceService.serviceConfig;
      borgMaintenanceTimer = config.systemd.timers.borgbackup-maintenance.timerConfig;
      btrfsImageService = config.systemd.services.btrfs-metadata-image-backup;
      btrfsImageServiceConfig = btrfsImageService.serviceConfig;
      rootSnapshotService = config.systemd.services.borgbackup-root-snapshots;
      rootSnapshotServiceConfig = rootSnapshotService.serviceConfig;
      serviceRestartIfChanged =
        name: lib.attrByPath [ "systemd" "services" name "restartIfChanged" ] true config;
      hasBackgroundPriority =
        service:
        service.Nice == 10
        && service.CPUSchedulingPolicy == "idle"
        && service.IOSchedulingClass == "idle"
        && service.CPUWeight == 20
        && service.IOWeight == 20;
      hasTmpfilesRule =
        pattern:
        builtins.any (rule: builtins.match ".*${pattern}.*" rule != null) config.systemd.tmpfiles.rules;
    in
    [
      # Core service
      {
        assertion = config.systemd.services ? btrbk;
        message = "btrbk service must exist";
      }
      {
        assertion = config.systemd.timers ? btrbk;
        message = "btrbk timer must exist";
      }
      # Config deployed
      {
        assertion = hasConf;
        message = "btrbk config must be deployed to /etc";
      }
      {
        assertion = hasConf && builtins.match ".*volume /realm.*" conf != null;
        message = "btrbk config must include /realm volume";
      }
      {
        assertion = hasConf && builtins.match ".*snapshot_preserve_min   latest.*" conf != null;
        message = "btrbk config must keep a default latest snapshot floor";
      }
      {
        assertion =
          hasConf
          &&
            builtins.match ".*volume /realm\n +snapshot_dir +\\.btrfs/snapshot\n +subvolume \\.\n +snapshot_preserve_min +all.*" conf
            != null;
        message = "btrbk config must keep /realm snapshots until the Borg drain deletes them";
      }
      {
        assertion =
          hasConf
          &&
            builtins.match ".*volume /persist\n +snapshot_dir +\\.btrfs/snapshot\n +subvolume \\.\n +snapshot_preserve_min +all.*" conf
            != null;
        message = "btrbk config must keep /persist snapshots until the Borg drain deletes them";
      }
      {
        assertion =
          !(config.services.borgbackup.jobs ? realm) && !(config.services.borgbackup.jobs ? persist);
        message = "Borg snapshot drains must not use one-shot services.borgbackup.jobs latest-only wrappers";
      }
      {
        assertion =
          builtins.match ".*BORG_REPO=file:///outer-realm/backup/borg-realm-v2.*" realmBorgUnit.script != null
          &&
            builtins.match ".*BORG_REPO=file:///outer-realm/backup/borg-persist-v1.*" persistBorgUnit.script
            != null;
        message = "Borg drain scripts must target the encrypted repositories via file URI";
      }
      {
        assertion =
          builtins.match ".*mount --bind.*" realmBorgUnit.script != null
          && builtins.match ".*mount --bind.*" persistBorgUnit.script != null
          && builtins.match ".*borg create.*" realmBorgUnit.script != null
          && builtins.match ".*borg create.*" persistBorgUnit.script != null
          && builtins.match ".*--lock-wait 60.*" realmBorgUnit.script != null
          && builtins.match ".*--lock-wait 60.*" persistBorgUnit.script != null
          && builtins.match ".*--lock-wait 7200.*" realmBorgUnit.script == null
          && builtins.match ".*--lock-wait 7200.*" persistBorgUnit.script == null
          && builtins.match ".*--compression auto,zstd,1.*" realmBorgUnit.script != null
          && builtins.match ".*--compression auto,zstd,1.*" persistBorgUnit.script != null;
        message = "Borg drain scripts must bind-mount and archive snapshot contents";
      }
      {
        assertion =
          builtins.match ".*tail -n 1.*" realmBorgUnit.script != null
          && builtins.match ".*tail -n 1.*" persistBorgUnit.script != null
          && builtins.match ".*btrfs subvolume delete.*" realmBorgUnit.script != null
          && builtins.match ".*btrfs subvolume delete.*" persistBorgUnit.script != null
          && builtins.match ".*Last realm Borg drain.*seconds ago.*coalescing.*" realmBorgUnit.script != null
          &&
            builtins.match ".*Last persist Borg drain.*seconds ago.*coalescing.*" persistBorgUnit.script
            != null;
        message = "Borg drains must archive the newest snapshot and delete snapshots covered by it after throttling";
      }
      {
        assertion =
          realmBorgPath.PathChanged == "/realm/.btrfs/snapshot"
          && persistBorgPath.PathChanged == "/persist/.btrfs/snapshot"
          && realmBorgPath.Unit == "borgbackup-job-realm.service"
          && persistBorgPath.Unit == "borgbackup-job-persist.service";
        message = "Borg drains must path-activate when new snapshots appear";
      }
      {
        assertion = borgCheckTimer.Persistent == false;
        message = "Borg integrity checks must not catch up during system switches";
      }
      {
        assertion =
          persistBorgTimer.OnCalendar == "*-*-* *:20:00"
          && realmBorgTimer.OnCalendar == "*-*-* *:35:00"
          && persistBorgTimer.Persistent == false
          && realmBorgTimer.Persistent == false;
        message = "Borg drains must have staggered hourly backstop timers without catch-up";
      }
      {
        assertion =
          builtins.match ".*--exclude var/lib/sinex.*" persistBorgUnit.script != null
          && builtins.match ".*--exclude '\\*\\*/data/captures/polylogue'.*" realmBorgUnit.script != null
          && builtins.match ".*--exclude '\\*\\*/\\.Trash-1000'.*" realmBorgUnit.script != null;
        message = "Borg must exclude active Sinex runtime state, not obsolete capture paths";
      }
      {
        assertion = btrbkTimer.Persistent == false;
        message = "btrbk timer must not catch up missed runs immediately after boot";
      }
      {
        assertion = btrbkTimer.OnCalendar == "*-*-* *:00/15:00";
        message = "btrbk timer must keep the quarter-hour snapshot cadence";
      }
      {
        assertion =
          builtins.match ".*--preserve-snapshots.*" (builtins.toString btrbkService.ExecStart) != null;
        message = "btrbk service must preserve snapshots for Borg-backed deletion";
      }
      {
        assertion =
          btrbkService.TimeoutStopSec == "15s"
          && !serviceRestartIfChanged "btrbk"
          && hasBackgroundPriority btrbkService
          && !(btrbkService ? Slice)
          && !(btrbkService ? ExecCondition);
        message = "btrbk must yield CPU and I/O to interactive work";
      }
      {
        assertion =
          persistBorgService.TimeoutStopSec == "15s"
          && realmBorgService.TimeoutStopSec == "15s"
          && !serviceRestartIfChanged "borgbackup-job-persist"
          && !serviceRestartIfChanged "borgbackup-job-realm"
          && hasBackgroundPriority persistBorgService
          && hasBackgroundPriority realmBorgService
          && !(persistBorgService ? Slice)
          && !(realmBorgService ? Slice)
          && !(persistBorgService ? ExecCondition)
          && !(realmBorgService ? ExecCondition);
        message = "Borg backup jobs must yield CPU and I/O to interactive work";
      }
      {
        assertion =
          borgCheckService.TimeoutStopSec == "15s"
          && !serviceRestartIfChanged "borgbackup-check"
          && hasBackgroundPriority borgCheckService
          && !(borgCheckService ? Slice)
          && !(borgCheckService ? ExecCondition)
          && !(borgCheckService ? IOReadBandwidthMax)
          && !(borgCheckService ? IOWriteBandwidthMax);
        message = "Borg integrity checks must yield CPU and I/O to interactive work";
      }
      {
        assertion =
          borgMaintenanceServiceConfig.TimeoutStopSec == "15s"
          && !serviceRestartIfChanged "borgbackup-maintenance"
          && hasBackgroundPriority borgMaintenanceServiceConfig
          && borgMaintenanceTimer.Persistent == false
          && builtins.match ".*borg prune --lock-wait 60.*" borgMaintenanceService.script != null
          && builtins.match ".*borg compact --lock-wait 60.*" borgMaintenanceService.script != null
          && builtins.match ".*--lock-wait 7200.*" borgMaintenanceService.script == null
          &&
            builtins.match ".*borg prune.*--keep-within 7d.*--keep-daily 60.*--keep-weekly 26.*--keep-monthly 24.*--keep-yearly 5.*" borgMaintenanceService.script
            != null
          && builtins.match ".*borg compact.*" borgMaintenanceService.script != null;
        message = "Borg retention maintenance must keep broad history without running compaction on every drain";
      }
      {
        assertion =
          !(persistBorgService ? MemoryHigh)
          && !(persistBorgService ? MemoryMax)
          && !(realmBorgService ? MemoryHigh)
          && !(realmBorgService ? MemoryMax);
        message = "Borg backup jobs must not carry cgroup memory guardrails";
      }
      {
        assertion =
          !(persistBorgService ? IOReadBandwidthMax)
          && !(persistBorgService ? IOWriteBandwidthMax)
          && !(realmBorgService ? IOReadBandwidthMax)
          && !(realmBorgService ? IOWriteBandwidthMax);
        message = "Borg backup jobs must rely on scheduling and low weights, not hard bandwidth caps";
      }
      {
        assertion = builtins.any (
          rule: builtins.match ".*\\.btrfs/snapshot.*" rule != null
        ) config.systemd.tmpfiles.rules;
        message = "Snapshot directories must be created via tmpfiles";
      }
      {
        assertion = hasTmpfilesRule "/run/borgbackup-snapshot-inputs";
        message = "Borg snapshot bind-mount staging directories must be created via tmpfiles";
      }
      {
        assertion = config.system.activationScripts ? borgRepositoryDirectories;
        message = "Borg repository directories must be created during activation";
      }
      {
        assertion =
          (config.systemd.timers ? btrfs-metadata-image-backup)
          && builtins.elem "realm.mount" btrfsImageService.requires
          && builtins.elem "outer\\x2drealm.mount" btrfsImageService.requires
          && !btrfsImageService.restartIfChanged
          && hasBackgroundPriority btrfsImageServiceConfig
          &&
            builtins.match ".*btrfs-image -c 9.*/dev/disk/by-uuid/43701cf7-7880-4e0c-9725-b6e12d91898a.*" btrfsImageService.script
            != null
          &&
            builtins.match ".*btrfs-image -c 9.*/dev/disk/by-uuid/f4782d9f-aabe-408e-b18b-2f2baa9e9a02.*" btrfsImageService.script
            != null;
        message = "Btrfs metadata images must be captured off-disk for native recovery";
      }
      {
        assertion =
          !rootSnapshotService.restartIfChanged
          && hasBackgroundPriority rootSnapshotServiceConfig
          && builtins.match ".*btrfs subvolume show.*" rootSnapshotService.script != null
          && builtins.match ".*rm -rf --one-file-system.*" rootSnapshotService.script != null
          && builtins.match ".*--exclude \"\\$snap_dir/nix\".*" rootSnapshotService.script != null
          && builtins.match ".*--exclude \"\\$snap_dir/swap\".*" rootSnapshotService.script != null
          &&
            builtins.match ".*--exclude \"\\$snap_dir/home/\\*/\\.cache\".*" rootSnapshotService.script != null
          && builtins.match ".*--exclude \"\\$snap_dir/var/cache\".*" rootSnapshotService.script != null
          && builtins.match ".*--lock-wait 60.*" rootSnapshotService.script != null
          && builtins.match ".*--lock-wait 7200.*" rootSnapshotService.script == null;
        message = "Root snapshot archival must yield to interactive work and exclude mountpoint/cache payloads";
      }
    ];
}
