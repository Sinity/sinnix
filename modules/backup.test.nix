{ mountTmpfsRoots, baseTestConfig, ... }:
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
            builtins.match ".*volume /realm\n +snapshot_dir +\\.btrfs/snapshot\n +subvolume \\.\n +snapshot_preserve_min +6h\n +snapshot_preserve +24h.*" conf
            != null;
        message = "btrbk config must keep recent /realm snapshots in the .btrfs/snapshot layout";
      }
      {
        assertion =
          hasConf
          &&
            builtins.match ".*volume /persist\n +snapshot_dir +\\.btrfs/snapshot\n +subvolume \\.\n +snapshot_preserve_min +6h\n +snapshot_preserve +24h.*" conf
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
        assertion = persistJob.startAt == "*-*-* 02:17:00" && realmJob.startAt == "*-*-* 03:17:00";
        message = "Borg timers must run in overnight windows, not every four hours";
      }
      {
        assertion = btrbkTimer.Persistent == false;
        message = "btrbk timer must not catch up missed runs immediately after boot";
      }
      {
        assertion = btrbkTimer.OnCalendar == "*-*-* *:12/30:00";
        message = "btrbk timer must not run high-frequency snapshots on the busiest clock edges";
      }
      {
        assertion =
          btrbkService.IOWeight == 1
          && btrbkService.CPUWeight == 1
          && btrbkService.IOSchedulingClass == "idle"
          && btrbkService.Slice == "sinnix-maintenance.slice"
          && btrbkService.TimeoutStopSec == "15s";
        message = "btrbk must run in the bounded low-priority maintenance class";
      }
      {
        assertion =
          persistBorgService.IOWeight == 1
          && realmBorgService.IOWeight == 1
          && persistBorgService.CPUWeight == 1
          && realmBorgService.CPUWeight == 1
          && persistBorgService.IOSchedulingClass == "idle"
          && realmBorgService.IOSchedulingClass == "idle"
          && persistBorgService.Slice == "sinnix-maintenance.slice"
          && realmBorgService.Slice == "sinnix-maintenance.slice"
          && persistBorgService.TimeoutStopSec == "15s"
          && realmBorgService.TimeoutStopSec == "15s";
        message = "Borg backup jobs must run in the bounded low-priority maintenance class";
      }
      {
        assertion =
          borgCheckService.IOWeight == 1
          && borgCheckService.CPUWeight == 1
          && borgCheckService.IOSchedulingClass == "idle"
          && borgCheckService.Slice == "sinnix-maintenance.slice"
          && borgCheckService.TimeoutStopSec == "15s"
          &&
            builtins.match ".*sinnix-maintenance-gate.*borgbackup-check\\.service.*" borgCheckService.ExecCondition
            != null
          && !(borgCheckService ? IOReadBandwidthMax)
          && !(borgCheckService ? IOWriteBandwidthMax);
        message = "Borg integrity checks must stay low-priority with only the explicit maintenance-overlap gate";
      }
      {
        assertion =
          builtins.match ".*sinnix-maintenance-gate.*borgbackup-job-persist\\.service.*" persistBorgService.ExecCondition
          != null
          &&
            builtins.match ".*sinnix-maintenance-gate.*borgbackup-job-realm\\.service.*" realmBorgService.ExecCondition
            != null
          && builtins.match ".*sinnix-maintenance-gate.*btrbk\\.service.*" btrbkService.ExecCondition != null;
        message = "Borg and btrbk must skip rather than overlap another active maintenance unit";
      }
      {
        assertion =
          persistBorgService.MemoryHigh == "8G"
          && persistBorgService.MemoryMax == "20G"
          && realmBorgService.MemoryHigh == "8G"
          && realmBorgService.MemoryMax == "20G";
        message = "Borg backup jobs must have cgroup memory guardrails";
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
    ];
}
