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
          && !(btrbkService ? IOWeight)
          && !(btrbkService ? CPUWeight)
          && !(btrbkService ? IOSchedulingClass)
          && !(btrbkService ? Slice)
          && !(btrbkService ? ExecCondition);
        message = "btrbk must use the plain maintenance baseline without cgroup policy";
      }
      {
        assertion =
          persistBorgService.TimeoutStopSec == "15s"
          && realmBorgService.TimeoutStopSec == "15s"
          && !(persistBorgService ? IOWeight)
          && !(realmBorgService ? IOWeight)
          && !(persistBorgService ? CPUWeight)
          && !(realmBorgService ? CPUWeight)
          && (!(persistBorgService ? IOSchedulingClass) || persistBorgService.IOSchedulingClass == null)
          && (!(realmBorgService ? IOSchedulingClass) || realmBorgService.IOSchedulingClass == null)
          && (!(persistBorgService ? CPUSchedulingPolicy) || persistBorgService.CPUSchedulingPolicy == null)
          && (!(realmBorgService ? CPUSchedulingPolicy) || realmBorgService.CPUSchedulingPolicy == null)
          && !(persistBorgService ? Slice)
          && !(realmBorgService ? Slice)
          && !(persistBorgService ? ExecCondition)
          && !(realmBorgService ? ExecCondition);
        message = "Borg backup jobs must use the plain maintenance baseline without cgroup policy";
      }
      {
        assertion =
          borgCheckService.TimeoutStopSec == "15s"
          && !(borgCheckService ? IOWeight)
          && !(borgCheckService ? CPUWeight)
          && !(borgCheckService ? IOSchedulingClass)
          && !(borgCheckService ? Slice)
          && !(borgCheckService ? ExecCondition)
          && !(borgCheckService ? IOReadBandwidthMax)
          && !(borgCheckService ? IOWriteBandwidthMax);
        message = "Borg integrity checks must use the plain maintenance baseline";
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
    ];
}
