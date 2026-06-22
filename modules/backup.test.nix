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
      btrbkConfig = config.environment.etc."btrbk/btrbk.conf".text;
      btrbkService = config.systemd.services.btrbk.serviceConfig;
      btrbkTimer = config.systemd.timers.btrbk.timerConfig;
      realmBorgService = config.systemd.services.borgbackup-job-realm.serviceConfig;
      persistBorgService = config.systemd.services.borgbackup-job-persist.serviceConfig;
      realmBorgTimer = config.systemd.timers.borgbackup-job-realm.timerConfig;
      persistBorgTimer = config.systemd.timers.borgbackup-job-persist.timerConfig;
      borgCheckService = config.systemd.services.borgbackup-check.serviceConfig;
      borgCheckTimer = config.systemd.timers.borgbackup-check.timerConfig;
      borgMaintenanceService = config.systemd.services.borgbackup-maintenance;
      borgMaintenanceServiceConfig = borgMaintenanceService.serviceConfig;
      borgMaintenanceTimer = config.systemd.timers.borgbackup-maintenance.timerConfig;
      borgStatusService = config.systemd.services.borgbackup-status;
      borgStatusServiceConfig = borgStatusService.serviceConfig;
      borgStatusTimer = config.systemd.timers.borgbackup-status.timerConfig;
      btrfsImageService = config.systemd.services.btrfs-metadata-image-backup;
      rootSnapshotService = config.systemd.services.borgbackup-root-snapshots;
      borgStatusScript = borgStatusService.script;
      realmBorgScript = config.systemd.services.borgbackup-job-realm.script;
      persistBorgScript = config.systemd.services.borgbackup-job-persist.script;
      preserveAllCount =
        builtins.length (
          builtins.filter (line: line == "    snapshot_preserve_min   all") (
            lib.splitString "\n" btrbkConfig
          )
        );
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
          !(builtins.hasAttr "borgbackup-job-realm" config.systemd.paths)
          && !(builtins.hasAttr "borgbackup-job-persist" config.systemd.paths);
        message = "Borg drains must not path-activate on every btrbk snapshot";
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
        assertion = preserveAllCount == 2;
        message = "btrbk must preserve all queued source snapshots until Borg drains them";
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
        assertion =
          !serviceRestartIfChanged "borgbackup-status"
          && borgStatusTimer.Persistent == true
          && borgStatusTimer.OnCalendar == "hourly"
          && borgStatusServiceConfig.TimeoutStartSec == "30s"
          && !(borgStatusServiceConfig ? ExecCondition);
        message = "Borg freshness and snapshot queue checks must run hourly and fail loudly";
      }
      {
        assertion =
          lib.hasInfix ".last-success" borgStatusService.script
          && !(lib.hasInfix "borg " borgStatusScript);
        message = "Borg freshness status must read local success markers instead of enumerating repositories";
      }
      {
        assertion =
          lib.hasInfix "pgrep -x borg" realmBorgScript
          && lib.hasInfix "pgrep -x borg" persistBorgScript
          && lib.hasInfix "flock /run/lock/sinnix-borg.lock" realmBorgScript;
        message = "Borg drains must serialize access and recover stale locks via Borg break-lock";
      }
      {
        assertion =
          !(lib.hasInfix "data/captures/asciinema" realmBorgScript)
          && !(lib.hasInfix "data/captures/audio" realmBorgScript)
          && !(lib.hasInfix "data/captures/polylogue" realmBorgScript)
          && !(lib.hasInfix "data/captures/syslog" realmBorgScript)
          && !(lib.hasInfix "data/captures/machine/below" realmBorgScript);
        message = "Realm Borg input must not exclude operator evidence captures as regenerable artifacts";
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
