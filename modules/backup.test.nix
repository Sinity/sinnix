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
      realmJob = config.services.borgbackup.jobs.realm;
      persistJob = config.services.borgbackup.jobs.persist;
      btrbkService = config.systemd.services.btrbk.serviceConfig;
      btrbkTimer = config.systemd.timers.btrbk.timerConfig;
      realmBorgService = config.systemd.services.borgbackup-job-realm.serviceConfig;
      persistBorgService = config.systemd.services.borgbackup-job-persist.serviceConfig;
      borgCheckService = config.systemd.services.borgbackup-check.serviceConfig;
      borgCheckTimer = config.systemd.timers.borgbackup-check.timerConfig;
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
        message = "btrbk config must disable the default preserve-all snapshot minimum";
      }
      {
        assertion =
          hasConf
          &&
            builtins.match ".*volume /realm\n +snapshot_dir +\\.btrfs/snapshot\n +subvolume \\.\n +snapshot_preserve_min +30m\n +snapshot_preserve +6h.*" conf
            != null;
        message = "btrbk config must keep recent /realm snapshots in the .btrfs/snapshot layout";
      }
      {
        assertion =
          hasConf
          &&
            builtins.match ".*volume /persist\n +snapshot_dir +\\.btrfs/snapshot\n +subvolume \\.\n +snapshot_preserve_min +30m\n +snapshot_preserve +6h.*" conf
            != null;
        message = "btrbk config must keep recent /persist snapshots in the .btrfs/snapshot layout";
      }
      {
        assertion = realmJob.repo == "file:///outer-realm/backup/borg-realm-v2";
        message = "Realm Borg job must target the v2 encrypted repository via file URI";
      }
      {
        assertion = persistJob.repo == "file:///outer-realm/backup/borg-persist-v1";
        message = "Persist Borg job must target the encrypted persist repository via file URI";
      }
      {
        assertion = realmJob.paths == [ "/run/borgbackup-snapshot-inputs/realm/./" ];
        message = "Realm Borg job must archive the bind-mounted snapshot contents";
      }
      {
        assertion = persistJob.paths == [ "/run/borgbackup-snapshot-inputs/persist/./" ];
        message = "Persist Borg job must archive the bind-mounted snapshot contents";
      }
      {
        assertion = realmJob.persistentTimer == false && persistJob.persistentTimer == false;
        message = "Borg timers must not catch up missed runs immediately after boot";
      }
      {
        assertion = borgCheckTimer.Persistent == false;
        message = "Borg integrity checks must not catch up during system switches";
      }
      {
        assertion =
          persistJob.startAt == [ "*-*-* 02,06,10,14,18,22:20:00" ]
          && realmJob.startAt == [ "*-*-* 03,07,11,15,19,23:20:00" ];
        message = "Borg timers must stay on the staggered four-hour cadence";
      }
      {
        assertion =
          builtins.elem "var/lib/sinex" persistJob.exclude
          && !(builtins.elem "**/data/captures/sinex/state" realmJob.exclude)
          && !(builtins.elem "**/data/captures/sinex/postgresql" realmJob.exclude);
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
        assertion = builtins.match ".*mount --bind.*" realmJob.preHook != null;
        message = "Realm Borg job must bind-mount the latest snapshot before backup";
      }
      {
        assertion = builtins.match ".*mount --bind.*" persistJob.preHook != null;
        message = "Persist Borg job must bind-mount the latest snapshot before backup";
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
          !rootSnapshotService.restartIfChanged && hasBackgroundPriority rootSnapshotServiceConfig;
        message = "Root snapshot archival must yield CPU and I/O to interactive work";
      }
    ];
}
