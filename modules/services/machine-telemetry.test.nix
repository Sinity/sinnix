{
  lib,
  mkServiceTest,
  inputs,
  ...
}:
mkServiceTest {
  name = "services-machine-telemetry";
  service = "machine-telemetry";
  assertions =
    config:
    let
      service = config.systemd.services.machine-telemetry.serviceConfig;
      backupService = config.systemd.services.machine-telemetry-sqlite-backup;
      backupTimer = config.systemd.timers.machine-telemetry-sqlite-backup.timerConfig;
      dbScaffold = config.systemd.services.machine-telemetry-db-scaffold;
      dbScaffoldScript = dbScaffold.script;
      # The collector body was extracted from this .nix into pkgs/machine-telemetry/collector.py.
      # Substring assertions need both files concatenated to keep covering the same surface.
      source =
        builtins.readFile (inputs.self + "/modules/services/machine-telemetry.nix")
        + builtins.readFile (inputs.self + "/pkgs/machine-telemetry/collector.py");
      hasTmpfilesRule =
        pattern:
        builtins.any (rule: builtins.match ".*${pattern}.*" rule != null) config.systemd.tmpfiles.rules;
    in
    [
      {
        assertion =
          lib.hasInfix "/bin/machine-telemetry" service.ExecStart
          && lib.hasInfix "/realm/db/machine-telemetry/telemetry.sqlite" service.ExecStart
          && lib.hasInfix "/realm/data/captures/machine/manifest.json" service.ExecStart
          && lib.hasInfix "telemetry.sqlite" service.ExecStart;
        message = "machine-telemetry must write the canonical machine telemetry SQLite stream";
      }
      {
        assertion =
          dbScaffold.before == [ "machine-telemetry.service" ]
          && dbScaffold.requires == [ "realm.mount" ]
          && lib.hasInfix "btrfs subvolume create /realm/db/machine-telemetry" dbScaffoldScript
          && lib.hasInfix "chattr +C /realm/db/machine-telemetry" dbScaffoldScript
          && lib.hasInfix "PRAGMA wal_checkpoint(TRUNCATE)" dbScaffoldScript
          && lib.hasInfix "cp --reflink=never" dbScaffoldScript
          && lib.hasInfix "telemetry.sqlite-wal" dbScaffoldScript
          && lib.hasInfix "telemetry.sqlite-shm" dbScaffoldScript
          && lib.hasInfix "ln -s /realm/db/machine-telemetry/telemetry.sqlite /realm/data/captures/machine/telemetry.sqlite" dbScaffoldScript;
        message = "machine-telemetry SQLite must live in a nodatacow DB subvolume while preserving the legacy capture-path symlink";
      }
      {
        assertion =
          service.Slice == "system-critical.slice"
          && service.Nice == -5
          && service.IOSchedulingClass == "best-effort";
        message = "machine-telemetry must use the observability runtime class";
      }
      {
        assertion =
          lib.hasInfix "CPU RAPL package/core watts" source
          && lib.hasInfix "latency_oversleep_ms" source
          && lib.hasInfix "fan.hwmon_unavailable" source
          && lib.hasInfix "service_state" source
          && lib.hasInfix "block_device_sample" source
          && lib.hasInfix "service_cgroup_io_sample" source
          && lib.hasInfix "service_cgroup_pressure_sample" source
          && lib.hasInfix "process_io_delta_sample" source
          && lib.hasInfix "/proc\") / pid / \"io\"" source
          && lib.hasInfix "/proc/diskstats" source
          && lib.hasInfix "/sys/fs/cgroup" source
          && lib.hasInfix "--machine=" source;
        message = "machine-telemetry must capture power, latency, missing fan gaps, service state, block device counters, service cgroup I/O counters, service cgroup pressure counters, and bounded process I/O deltas";
      }
      {
        assertion = hasTmpfilesRule "/realm/data/captures/machine";
        message = "machine-telemetry capture root must be created via tmpfiles";
      }
      {
        assertion =
          builtins.elem "d /realm/data/captures/machine 0755 root users -" config.systemd.tmpfiles.rules
          && builtins.elem "d /realm/data/captures/machine/experiments 0775 root users -" config.systemd.tmpfiles.rules
          && builtins.elem "d /realm/data/captures/machine/legacy 0775 root users -" config.systemd.tmpfiles.rules
          && builtins.elem "d /persist/backup/machine-telemetry 0700 sinity users -" config.systemd.tmpfiles.rules;
        message = "machine-telemetry tmpfiles ownership must allow system capture plus user experiment manifests";
      }
      {
        assertion =
          lib.hasInfix "sqlite3 /realm/db/machine-telemetry/telemetry.sqlite" backupService.script
          && lib.hasInfix ".backup" backupService.script
          && lib.hasInfix "zstd -T1" backupService.script
          && lib.hasInfix "/persist/backup/machine-telemetry" backupService.script
          && lib.hasInfix "NR > 7" backupService.script
          && backupService.serviceConfig.User == "sinity"
          && backupService.serviceConfig.Group == "users"
          && backupService.serviceConfig.MemoryHigh == "2G"
          && backupService.serviceConfig.MemoryMax == "4G";
        message = "machine-telemetry SQLite must have a compressed logical backup under backed-up /persist";
      }
      {
        assertion =
          backupTimer.OnCalendar == "*-*-* 03:42:00"
          && backupTimer.Persistent == false
          && config.sinnix.runtime.surfaces.machine-telemetry-sqlite-backup.observe.enable
          &&
            config.sinnix.runtime.surfaces.machine-telemetry-sqlite-backup.resourceClass
            == "backup-maintenance";
        message = "machine-telemetry SQLite backup must run daily without catch-up storms";
      }
      {
        assertion =
          lib.hasInfix "network_sample" source
          && lib.hasInfix "--network-interval" service.ExecStart
          && !(config.systemd.services ? network-probe)
          && !(config.systemd.timers ? network-probe);
        message = "machine-telemetry must own network probing without a separate network-probe timer";
      }
    ];
}
