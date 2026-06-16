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
      btrbkService = config.systemd.services.btrbk.serviceConfig;
      btrbkTimer = config.systemd.timers.btrbk.timerConfig;
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
      rootSnapshotService = config.systemd.services.borgbackup-root-snapshots;
      serviceRestartIfChanged =
        name: lib.attrByPath [ "systemd" "services" name "restartIfChanged" ] true config;
    in
    [
      # Config deployed
      {
        assertion = hasConf;
        message = "btrbk config must be deployed to /etc";
      }
      {
        assertion =
          !(config.services.borgbackup.jobs ? realm) && !(config.services.borgbackup.jobs ? persist);
        message = "Borg snapshot drains must not use one-shot services.borgbackup.jobs latest-only wrappers";
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
        assertion = persistBorgTimer.Persistent == false && realmBorgTimer.Persistent == false;
        message = "Borg drains must have staggered hourly backstop timers without catch-up";
      }
      {
        assertion = btrbkTimer.Persistent == false;
        message = "btrbk timer must not catch up missed runs immediately after boot";
      }
      {
        assertion = !serviceRestartIfChanged "btrbk" && !(btrbkService ? ExecCondition);
        message = "btrbk must yield CPU and I/O to interactive work";
      }
      {
        assertion =
          !serviceRestartIfChanged "borgbackup-job-persist"
          && !serviceRestartIfChanged "borgbackup-job-realm"
          && !(persistBorgService ? ExecCondition)
          && !(realmBorgService ? ExecCondition);
        message = "Borg backup jobs must yield CPU/I/O and stay within backup resource bounds";
      }
      {
        assertion = !serviceRestartIfChanged "borgbackup-check" && !(borgCheckService ? ExecCondition);
        message = "Borg integrity checks must yield CPU/I/O and stay within backup resource bounds";
      }
      {
        assertion =
          !serviceRestartIfChanged "borgbackup-maintenance"
          && borgMaintenanceTimer.Persistent == false
          && !(borgMaintenanceServiceConfig ? ExecCondition);
        message = "Borg retention maintenance must keep broad history without running compaction on every drain and within backup resource bounds";
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
          && !btrfsImageService.restartIfChanged;
        message = "Btrfs metadata images must be captured off-disk for native recovery";
      }
      {
        assertion = !rootSnapshotService.restartIfChanged;
        message = "Root snapshot archival must yield to interactive work and exclude mountpoint/cache payloads";
      }
    ];
}
