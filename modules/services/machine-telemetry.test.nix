{ mkServiceTest, ... }:
mkServiceTest {
  name = "services-machine-telemetry";
  service = "machine-telemetry";
  assertions =
    config:
    let
      backupService = config.systemd.services.machine-telemetry-sqlite-backup;
      dbScaffold = config.systemd.services.machine-telemetry-db-scaffold;
    in
    [
      {
        assertion =
          dbScaffold.before == [ "machine-telemetry.service" ] && dbScaffold.requires == [ "realm.mount" ];
        message = "machine-telemetry SQLite must live in a nodatacow DB subvolume while preserving the legacy capture-path symlink";
      }
      {
        assertion =
          backupService.serviceConfig.User == "sinity" && backupService.serviceConfig.Group == "users";
        message = "machine-telemetry SQLite must have a compressed logical backup under backed-up /persist";
      }
      {
        assertion =
          config.sinnix.runtime.surfaces.machine-telemetry-sqlite-backup.observe.enable
          &&
            config.sinnix.runtime.surfaces.machine-telemetry-sqlite-backup.resourceClass
            == "backup-maintenance";
        message = "machine-telemetry SQLite backup must run daily without catch-up storms";
      }
      {
        assertion = !(config.systemd.services ? network-probe) && !(config.systemd.timers ? network-probe);
        message = "machine-telemetry must own network probing without a separate network-probe timer";
      }
    ];
}
